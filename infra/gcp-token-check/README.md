# GCP Cloud Run: Cognito token check

Verifies AWS Cognito JWTs inside a Cloud Run service (FastAPI). No secrets are
involved: only the pool ID, region and app client ID (all public values).

## Files
- `auth.py`: `get_current_user` dependency. Put `Depends(get_current_user)` on every protected route.
- `main.py`: example service. `/health` is public, `/me` and `/match` are protected.
- `match.py`, `features.py`, `urlcheck.py`: lost-pet matching (`POST /match`, see below).
- `test_match.py`: offline tests for `/match` (no network, no Cloud Vision).
- `chat.py`, `test_chat.py`: chatbot route `POST /chat` (Dialogflow ES) and its offline tests.
- `test_auth.py`: offline tests (valid ID/access token, expired, wrong issuer/client/signature, alg=none, garbage).

## Run tests locally
```
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest httpx
pytest -q
```

## Deploy (GCP project ecoguard-g11-14145)
```
gcloud config set project ecoguard-g11-14145
gcloud services enable vision.googleapis.com run.googleapis.com cloudbuild.googleapis.com
gcloud run deploy ecoguard-api \
  --source . \
  --region australia-southeast1 \
  --service-account ecoguard-api-sa@ecoguard-g11-14145.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --min-instances 0 \
  --memory 512Mi --timeout 60 \
  --set-env-vars COGNITO_REGION=ap-southeast-2,COGNITO_USER_POOL_ID=ap-southeast-2_WI1ngaH1k,COGNITO_APP_CLIENT_ID=5tv0jne3t88vcrc5408vrtnl6s,ALLOWED_ORIGINS=http://localhost:5173
```
`--allow-unauthenticated` only means Cloud Run itself does not require a Google
identity. Access is still enforced by the Cognito check in the code, so every
route except `/health` must use `Depends(get_current_user)`.
`--min-instances 0` keeps cost at zero when idle.

## Test with a real token
1. Sign up and log in through the Cognito Hosted UI (or the frontend).
2. Get a token from the CLI for a confirmed test user. Needs a client that allows
   `ALLOW_USER_PASSWORD_AUTH`; otherwise copy the `id_token` from the browser after login:
```
curl https://<service-url>/health                      # 200, public
curl https://<service-url>/me                          # 401, no token
curl -H "Authorization: Bearer <ID_TOKEN>" https://<service-url>/me   # 200, your email
```
Expected: 401 without a token or with an expired/tampered one.

## Notes for the report / demo
- RS256 signature verified against the pool's JWKS (keys cached in memory).
- Checks `iss`, `exp`, `token_use` and the app client ID (`aud` for ID tokens, `client_id` for access tokens).
- Only RS256 is accepted, so `alg: none` and HS256 tokens are rejected.
- No credentials in code or the frontend. Config comes from environment variables.

## POST /match (lost-pet matching)
The AWS search Lambda picks the candidate images, signs S3 GET URLs and calls this
route with the user's own Cognito ID token (`Authorization: Bearer <ID token>`).

Request:
```json
{"query_url": "https://<bucket host>/search-temp/<id>.jpg?...",
 "candidates": [{"file_id": "<sha256>", "url": "https://<bucket host>/thumbnails/<sha256>.jpg?..."}]}
```
Response 200, best first, score 0 to 1 (candidates below `MIN_SCORE`, default 0.25, are left out; at most `MAX_RESULTS`, default 10):
```json
{"matches": [{"file_id": "<sha256>", "score": 0.82}], "skipped": 0}
```
`skipped` counts candidates that could not be downloaded or decoded.
Errors: 400 bad request or rejected URL, 401 bad or missing token, 502 Vision failed.

How it scores: 60% Cloud Vision label similarity (weighted Jaccard) + 40% colour
histogram similarity computed locally with Pillow. This finds animals of the same kind
and colouring; it cannot recognise an individual animal.

Security: URLs must be https on our bucket host (`ALLOWED_S3_HOSTS`), under
`/search-temp/` (query) or `/thumbnails/`, `/uploads/` (candidates, named after their
`file_id`). Redirects are not followed, so the service cannot be used to reach other hosts.
The service holds no S3 credentials. Max 20 candidates and 10 MB per image.

Cost: Cloud Vision label detection is 1 unit per image analysed, first 1,000 units per month
free, then about US$1.50 per 1,000. One request with 20 uncached candidates is 21 units.
Candidate results are cached in memory per image, so repeat searches mostly cost 1 unit.
Keep test loops small.

Setup: enable the Vision API (see Deploy). If the first call returns 403, grant the service
account `roles/serviceusage.serviceUsageConsumer`.

## POST /chat (chatbot)
The frontend sends the user's message with their Cognito ID token (`Authorization: Bearer <ID token>`).
Cloud Run verifies the token, then calls the Dialogflow ES agent with its own service account, so the
browser never holds a Google key.

Request: `{"message": "show me foxes"}` (1 to 256 characters).
Response 200:
```json
{"reply": "<agent's fulfillment text>", "intent": "<intent display name or null>",
 "confidence": 0.93, "parameters": {"animal": ["fox"]}}
```
Errors: 400 bad message, 401 bad or missing token, 502 Dialogflow failed.

The Dialogflow session id is the user's Cognito `sub`, taken from the verified token, so users cannot
read or continue each other's conversations. The frontend uses `intent` and `parameters` to decide what
to do next (for example, call the AWS tag search with `parameters.animal`).

Setup: the agent lives in project `ecoguard-g11-14145` (override with `DIALOGFLOW_PROJECT_ID`,
`DIALOGFLOW_LANGUAGE`). Grant the service account the Dialogflow API Client role:
```
gcloud services enable dialogflow.googleapis.com
gcloud projects add-iam-policy-binding ecoguard-g11-14145 \
  --member=serviceAccount:ecoguard-api-sa@ecoguard-g11-14145.iam.gserviceaccount.com \
  --role=roles/dialogflow.client
```
