const BULK_TAGS_API_URL =
  "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/media/tags/bulk";

const MEDIA_BUCKET = "ecoguard-media-853611856490";

function prepareMediaUrl(originalUrl) {
  let parsedUrl;

  try {
    parsedUrl = new URL(originalUrl);
  } catch {
    throw new Error("Invalid EcoGuard original media URL.");
  }

  const allowedHosts = [
    `${MEDIA_BUCKET}.s3.amazonaws.com`,
    `${MEDIA_BUCKET}.s3.ap-southeast-2.amazonaws.com`,
  ];

  const validPath = /^\/uploads\/[0-9a-f]{64}\.[a-zA-Z0-9]+$/;

  if (
    parsedUrl.protocol !== "https:" ||
    !allowedHosts.includes(parsedUrl.hostname) ||
    parsedUrl.username ||
    parsedUrl.password ||
    parsedUrl.port ||
    !validPath.test(parsedUrl.pathname)
  ) {
    throw new Error("Invalid EcoGuard original media URL.");
  }

  return `https://${MEDIA_BUCKET}.s3.ap-southeast-2.amazonaws.com${parsedUrl.pathname}`;
}

export async function editBulkTags(urls, tags, operation, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before editing tags.");
  }

  const cleanedUrls = [
    ...new Set(
      urls
        .map((url) => url.trim())
        .filter(Boolean)
        .map(prepareMediaUrl),
    ),
  ];

  const cleanedTags = [
    ...new Set(tags.map((tag) => tag.trim().toLowerCase()).filter(Boolean)),
  ];

  if (cleanedUrls.length === 0 || cleanedUrls.length > 50) {
    throw new Error("Select between 1 and 50 media files.");
  }

  if (
    cleanedTags.length === 0 ||
    cleanedTags.length > 20 ||
    cleanedTags.some((tag) => tag.length > 50)
  ) {
    throw new Error("Enter 1 to 20 tags, each up to 50 characters.");
  }

  if (operation !== 0 && operation !== 1) {
    throw new Error("Invalid tag operation.");
  }

  const response = await fetch(BULK_TAGS_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: idToken,
    },
    body: JSON.stringify({
      urls: cleanedUrls,
      tags: cleanedTags,
      operation,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : data.error?.message || "Could not update tags.",
    );
  }

  return data;
}
