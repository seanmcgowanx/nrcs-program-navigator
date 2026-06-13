const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

interface ChatResponse {
  session_id: string;
  reply: string;
}

/**
 * Send one user message to the agent under a session id and return its reply.
 * The session id is the conversation thread: the backend resumes the same
 * elicitation flow on every call with the same id. Throws on transport or
 * server error so the caller can render an inline error state.
 */
export async function sendChat(
  sessionId: string,
  message: string,
  signal?: AbortSignal,
): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal,
    });
  } catch {
    throw new Error(
      "Could not reach the navigator service. Check that the backend is running.",
    );
  }

  if (!res.ok) {
    throw new Error(
      `The navigator service returned an error (${res.status}). Try again in a moment.`,
    );
  }

  const data = (await res.json()) as ChatResponse;
  return data.reply;
}
