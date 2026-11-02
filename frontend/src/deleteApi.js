const DELETE_API_BASE =
  "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/media";

export async function deleteMediaFile(fileId, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before deleting files.");
  }

  if (!/^[0-9a-f]{64}$/.test(fileId)) {
    throw new Error("Invalid file ID.");
  }

  const response = await fetch(
    `${DELETE_API_BASE}/${encodeURIComponent(fileId)}`,
    {
      method: "DELETE",
      headers: {
        Authorization: idToken,
      },
    },
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : data.error?.message || "File deletion failed.",
    );
  }

  return data;
}
