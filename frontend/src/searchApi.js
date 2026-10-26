const SEARCH_API_URL =
  "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/media/search/tags";

export async function searchByTags(tags, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before searching.");
  }

  const response = await fetch(SEARCH_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: idToken,
    },
    body: JSON.stringify({ tags }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : data.error?.message || "Search failed.",
    );
  }

  return data;
}

export async function findOriginalByThumbnail(thumbnailUrl, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before searching.");
  }

  if (!thumbnailUrl.trim()) {
    throw new Error("Please enter a thumbnail URL.");
  }

  const response = await fetch(
    "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/media/search/thumbnail",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: idToken,
      },
      body: JSON.stringify({
        thumbnailUrl: thumbnailUrl.trim(),
      }),
    },
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : data.error?.message || "Thumbnail lookup failed.",
    );
  }

  return data;
}

export async function initImageSearch(file, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before searching.");
  }

  if (!["image/jpeg", "image/png"].includes(file.type)) {
    throw new Error("Only JPG and PNG images are supported.");
  }

  const response = await fetch(
    "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/media/search/upload/init",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: idToken,
      },
      body: JSON.stringify({
        contentType: file.type,
      }),
    },
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Could not initialise image search.");
  }

  return data;
}

export async function uploadTemporarySearchImage(file, uploadUrl) {
  if (!uploadUrl) {
    throw new Error("Temporary upload URL is missing.");
  }

  if (file.size === 0 || file.size > 10 * 1024 * 1024) {
    throw new Error("Image must be between 1 byte and 10 MB.");
  }

  const response = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      "Content-Type": file.type,
      "If-None-Match": "*",
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error(`Temporary image upload failed (${response.status}).`);
  }
}

export async function searchByUploadedImage(imageKey, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before searching.");
  }

  if (!imageKey || !imageKey.startsWith("search-temp/")) {
    throw new Error("Invalid temporary image key.");
  }

  const response = await fetch(
    "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/media/search/upload",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: idToken,
      },
      body: JSON.stringify({
        imageKey: imageKey,
      }),
    },
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : data.error?.message || "Image search failed.",
    );
  }

  return data;
}
