const CHAT_API_URL =
  "https://ecoguard-api-334103023207.australia-southeast1.run.app/chat";

export async function sendChatMessage(message, idToken) {
  if (!idToken) {
    throw new Error("Please sign in before using the chatbot.");
  }

  const cleanMessage = message.trim();

  if (!cleanMessage || cleanMessage.length > 256) {
    throw new Error("Message must be between 1 and 256 characters.");
  }

  const response = await fetch(CHAT_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${idToken}`,
    },
    body: JSON.stringify({
      message: cleanMessage,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Chatbot request failed.",
    );
  }

  return data;
}
