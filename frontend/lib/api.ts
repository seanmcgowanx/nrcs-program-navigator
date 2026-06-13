const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// Backstop so a stuck request never leaves the user hanging indefinitely. A
// normal turn (including one bounded scrape) finishes well under this; past it
// we surface a clear message and let the user retry or start over.
const REQUEST_TIMEOUT_MS = 100_000;

interface ChatResponse {
  session_id: string;
  reply: string;
}

/**
 * Send one user message to the agent under a session id and return its reply.
 * The session id is the conversation thread: the backend resumes the same
 * elicitation flow on every call with the same id.
 *
 * Aborts after REQUEST_TIMEOUT_MS so the UI is never stuck. An external `signal`
 * (e.g. starting a new conversation) cancels the request silently by rethrowing
 * an AbortError, which the caller ignores; a timeout or transport failure throws
 * a descriptive Error the caller renders as a retryable error state.
 */
export async function sendChat(
  sessionId: string,
  message: string,
  signal?: AbortSignal,
): Promise<string> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  // Forward an external cancel (new conversation) onto our controller.
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal: controller.signal,
    });
  } catch (err) {
    if (timedOut) {
      throw new Error(
        "The navigator is taking longer than expected. It may still be finishing in the background. Try again, or start a new conversation.",
      );
    }
    if ((err as Error).name === "AbortError") {
      throw err; // external cancel; the caller ignores AbortError
    }
    throw new Error(
      "Could not reach the navigator service. Check your connection and try again.",
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    throw new Error(
      `The navigator service returned an error (${res.status}). Try again in a moment.`,
    );
  }

  const data = (await res.json()) as ChatResponse;
  return data.reply;
}
