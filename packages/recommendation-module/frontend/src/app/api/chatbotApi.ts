const API_BASE_URL = "http://127.0.0.1:8000";

export interface ChatbotResponse {
  answer: string;
  mode: "advisory" | "diagnostic";
  sources?: string[];
}

export async function sendChatMessage(
  appId: string,
  question: string
): Promise<ChatbotResponse> {
  const response = await fetch(`${API_BASE_URL}/chatbot`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      app_id: appId || "1",
      question,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("Chatbot backend error:", errorText);
    throw new Error(`Chatbot API failed with status ${response.status}`);
  }

  return response.json();
}

export async function getChatSessions(appId: string) {
  const response = await fetch(
    `${API_BASE_URL}/chat/sessions/${appId}`
  );

  if (!response.ok) {
    throw new Error("Failed to load sessions");
  }

  return response.json();
}

export async function getChatMessages(sessionId: string) {
  const response = await fetch(
    `${API_BASE_URL}/chat/messages/${sessionId}`
  );

  if (!response.ok) {
    throw new Error("Failed to load messages");
  }

  return response.json();
}