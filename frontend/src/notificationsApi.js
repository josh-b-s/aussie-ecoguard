const NOTIFICATIONS_API =
  "https://sn6wpy8jd9.execute-api.ap-southeast-2.amazonaws.com/prod/notifications/subscribe";

export async function subscribeToAlerts(selectedAnimals, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before subscribing.");
  }

  if (selectedAnimals.length === 0) {
    throw new Error("Please select at least one animal.");
  }

  const animalTags = selectedAnimals.map((animal) =>
    animal.trim().toLowerCase(),
  );

  const response = await fetch(NOTIFICATIONS_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: idToken,
    },
    body: JSON.stringify({
      animal_tags: animalTags,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.error === "string"
        ? data.error
        : data.error?.message || "Subscription failed.",
    );
  }

  return data;
}
