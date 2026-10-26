const UPLOAD_API =
  "https://cz0bx6ka2i.execute-api.ap-southeast-2.amazonaws.com/prod/upload/init";

export async function uploadFileToS3(file, checksum, idToken, isPrivate) {
  const allowedTypes = [
    "image/jpeg",
    "image/png",
    "video/mp4",
    "video/quicktime",
  ];

  if (!allowedTypes.includes(file.type)) {
    throw new Error("Only JPG, PNG, MP4 and MOV files are supported.");
  }

  if (!idToken) {
    throw new Error("Please sign in before uploading.");
  }

  const response = await fetch(UPLOAD_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: idToken,
    },
    body: JSON.stringify({
      contentType: file.type,
      sha256: checksum,
      visibility: isPrivate ? "private" : "public",
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Could not initialise upload.");
  }

  if (data.duplicate) {
    return { duplicate: true, fileId: data.fileId };
  }

  if (!data.uploadUrl) {
    throw new Error("Upload URL was not returned.");
  }

  const uploadResponse = await fetch(data.uploadUrl, {
    method: "PUT",
    headers: {
      "Content-Type": file.type,
    },
    body: file,
  });

  if (!uploadResponse.ok) {
    throw new Error("Upload to S3 failed.");
  }

  return { duplicate: false, fileId: data.fileId };
}
