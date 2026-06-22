const API_BASE_URL = "http://127.0.0.1:8000";

export interface ChatbotResponse {
  answer: string;
  mode: string;
}

export async function sendChatMessage(appId: string, question: string): Promise<ChatbotResponse> {
  const response = await fetch(`${API_BASE_URL}/chatbot`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      app_id: appId,
      question
    })
  });

  if (!response.ok) {
    throw new Error(`Chatbot API failed with status ${response.status}`);
  }

  return response.json();
}