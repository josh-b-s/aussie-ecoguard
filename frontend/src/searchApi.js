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
