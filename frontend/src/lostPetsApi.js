import { initImageSearch, uploadTemporarySearchImage } from "./searchApi.js";

const LOST_PET_API_URL =
  "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/media/search/lost-pet";

export async function searchForLostPet(photo, idToken) {
  if (!photo) {
    throw new Error("Please select a photo of your missing pet.");
  }

  if (!idToken) {
    throw new Error("Please sign in before searching.");
  }

  const uploadDetails = await initImageSearch(photo, idToken);

  await uploadTemporarySearchImage(photo, uploadDetails.uploadUrl);

  const response = await fetch(LOST_PET_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: idToken,
    },
    body: JSON.stringify({
      imageKey: uploadDetails.imageKey,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : data.error?.message || "Lost pet search failed.",
    );
  }

  return data;
}
