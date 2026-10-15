# File processing and ML

Upload, deduplication, thumbnails, video frame extraction and species tagging for EcoGuard. Everything here runs on AWS in `ap-southeast-2`, defined in one SAM template (`template.yaml`).

## Layout

```
template.yaml        bucket, table, topic, API, Lambdas, roles, layer, model config
upload_init/         POST /upload/init: dedup check and presigned upload URL
thumbnailer/         resizes images into thumbnails
tagger/              runs Rekognition, extracts video frames, saves tags
layers/              script that builds the OpenCV layer
scripts/e2e_test.py  uploads one file and prints the resulting record
```

## How a file moves through

1. The browser computes the file's SHA-256 and calls `POST /upload/init` with a Cognito ID token.
2. `upload_init` inserts a `pending` record keyed by the hash. A conditional put makes this atomic, so a second upload of the same bytes is rejected. A duplicate gets `{"duplicate": true}`. Otherwise the response contains a presigned PUT URL valid for 5 minutes.
3. The browser PUTs the file to `uploads/<sha256>.<ext>`. Presigned URLs avoid API Gateway's 10 MB payload limit.
4. S3 publishes the upload to an SNS topic. Both the thumbnailer and the tagger subscribe to it. S3 allows only one notification per prefix and event type, which is why the topic sits in between.
5. The thumbnailer writes `thumbnails/<sha256>.jpg` and sets `thumbnail_key` on the record (images only).
6. The tagger detects species, then sets `tags` and `status: done` on the record. On any error it sets `status: failed` and re-raises.

Accepted types: `image/jpeg`, `image/png`, `video/mp4`.

### Upload init API

Request (header `Authorization: <Cognito ID token>`):

```json
{"contentType": "image/jpeg", "sha256": "<64 lowercase hex characters>"}
```

Response:

```json
{"duplicate": false, "fileId": "<sha256>", "uploadUrl": "https://..."}
```

or `{"duplicate": true, "fileId": "<sha256>"}`. The PUT to `uploadUrl` must send the same `Content-Type` header.

## Data contract

DynamoDB, partition key `file_id` (the SHA-256). Other members' APIs read and write these fields.

| Field | Meaning |
|---|---|
| `file_id` | SHA-256 of the file |
| `file_type` | `image` or `video` |
| `original_key` | S3 key, `uploads/<file_id>.<ext>` |
| `thumbnail_key` | S3 key, `thumbnails/<file_id>.jpg`. Images only, set after the thumbnail exists |
| `tags` | Map of tag to count, e.g. `{"fox": 2, "cat": 1}` |
| `uploaded_by` | Cognito `sub` of the uploader |
| `uploaded_at` | UTC ISO timestamp |
| `status` | `pending`, `done` or `failed` |

Only S3 keys are stored. Build URLs when responding (presigned GET). The bucket is private. To delete a file, remove `original_key`, `thumbnail_key` (if present) and the record.

## Tagging

- Images go to Rekognition `DetectLabels` by S3 reference.
- Videos are downloaded to `/tmp` and one frame is taken every 10 seconds, starting at 0 s, with OpenCV. Each frame is detected separately and results are merged by taking the highest count per tag.
- Rekognition's species labels are reliable but the labels on its bounding boxes are not (a photo of foxes can come back with boxes labelled Dog, Cat and Pig). The tagger therefore reads species from the image-level labels and counts every box whose label has `Animal` as a parent. When one species is present it gets that total. When several are present each gets its own boxes, which can undercount.

### Model config

The label map and thresholds live in the SSM parameter `/ecoguard/model-config`, read on every invocation:

```json
{
  "min_confidence": 85,
  "label_map": {"Fox": "fox", "Pig": "feral pig", "Toad": "cane toad"},
  "drop_if_present": {"dog": ["fox"], "cat": ["fox"]}
}
```

- `label_map`: Rekognition label to stored tag. Labels not listed are ignored.
- `min_confidence`: minimum confidence for a species label.
- `drop_if_present`: drop the first tag when any listed tag is also present.

Editing the parameter in the console applies to the next upload with no redeploy. A redeploy resets it to the value in `template.yaml`, so make lasting changes there.

## Deploy

Needs AWS CLI and SAM CLI. CloudShell has both (`pip install aws-sam-cli` if `sam` is missing).

```
cd functions
bash layers/build_opencv.sh
sam build
sam deploy --guided
```

Stack name `ecoguard-pipeline`, region `ap-southeast-2`. Parameters:

- `BucketName`: globally unique bucket name
- `UserPoolArn`: ARN of the Cognito user pool
- `FrontendOrigin`: allowed CORS origin, default `http://localhost:5173`
- `ConfigParamName`: default `/ecoguard/model-config`

Later deploys: `sam build && sam deploy`. Stack outputs (API URL, bucket, table):

```
aws cloudformation describe-stacks --stack-name ecoguard-pipeline --query "Stacks[0].Outputs"
```

The layer is about 205 MB unzipped, close to Lambda's 250 MB limit for code plus layers. Do not add large libraries to the thumbnailer or tagger.

## Test

```
python3 scripts/e2e_test.py --api <ApiUrl> --table <TableName> --token "$TOKEN" fox.jpg
```

It hashes the file, calls init, uploads, waits for the record to finish and prints it. Running it twice with the same file prints `duplicate: True`. Logs:

```
sam logs --stack-name ecoguard-pipeline --name TaggerFunction --tail
```

## Permissions

Each function has its own role:

| Function | Allowed |
|---|---|
| UploadInit | `s3:PutObject` on `uploads/*`, `dynamodb:PutItem` on the table |
| Thumbnail | `s3:GetObject` on `uploads/*`, `s3:PutObject` on `thumbnails/*`, `dynamodb:UpdateItem` |
| Tagger | `s3:GetObject` on `uploads/*`, `dynamodb:UpdateItem`, `ssm:GetParameter` on the config parameter, `rekognition:DetectLabels` |

`rekognition:DetectLabels` does not support resource-level permissions, so its resource is `*`.

## Known limits

- Dedup uses the hash the client sends. The server does not recompute it, so a client can claim a hash that does not match the bytes.
- Init replaces a record that is `failed`, or `pending` for more than 10 minutes, so an abandoned or failed upload can be retried. The retrying user becomes the owner of the new record.
- Rekognition cannot tell a cane toad from other toads, or a feral cat from a pet cat.
- Other animals in frame add to the count of a single detected species.
- Rekognition rejects frame images over 5 MB. Very high resolution video may need downscaling in `tagger/frames.py`.
- Weak real detections below `min_confidence` are dropped.
