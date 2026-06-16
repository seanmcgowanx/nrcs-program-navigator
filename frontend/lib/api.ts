const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

// Idle timeout for the streaming turn: how long to wait for the *next* chunk
// before giving up. Reset on every chunk, so a long turn that keeps emitting
// steps and tokens never trips it; only a genuine stall does.
const STREAM_IDLE_TIMEOUT_MS = 60_000;

// One trace event from POST /chat/stream. Mirrors serving/trace.py.
export type StreamEvent =
  | { type: "step_start"; id: string; label: string }
  | { type: "step_end"; id: string; summary: string }
  | { type: "final"; reply: string }
  | { type: "error"; message: string }
  | { type: "done" };

export interface StreamHandlers {
  onStepStart: (id: string, label: string) => void;
  onStepEnd: (id: string, summary: string) => void;
  onFinal: (reply: string) => void;
}

/**
 * Stream one turn from the agent, invoking handlers as trace events arrive: each
 * tool call (onStepStart) and its abbreviated result (onStepEnd) live, then the
 * complete answer once ready (onFinal). Resolves when the turn completes.
 *
 * The body is newline delimited JSON. An idle watchdog aborts if no chunk
 * arrives for STREAM_IDLE_TIMEOUT_MS; an external `signal` (new conversation)
 * cancels silently by rethrowing AbortError, which the caller ignores. Any
 * transport failure, or a server emitted `error` event, throws a descriptive
 * Error the caller renders as a retryable error state.
 */
export async function streamChat(
  sessionId: string,
  message: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const controller = new AbortController();
  let idledOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const arm = () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      idledOut = true;
      controller.abort();
    }, STREAM_IDLE_TIMEOUT_MS);
  };
  arm();

  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (idledOut) {
      throw new Error(
        "The navigator is taking longer than expected. It may still be finishing in the background. Try again, or start a new conversation.",
      );
    }
    if ((err as Error).name === "AbortError") throw err;
    throw new Error(
      "Could not reach the navigator service. Check your connection and try again.",
    );
  }

  if (!res.ok || !res.body) {
    clearTimeout(timer);
    throw new Error(
      `The navigator service returned an error (${res.status}). Try again in a moment.`,
    );
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handle = (event: StreamEvent) => {
    switch (event.type) {
      case "step_start":
        handlers.onStepStart(event.id, event.label);
        break;
      case "step_end":
        handlers.onStepEnd(event.id, event.summary);
        break;
      case "final":
        handlers.onFinal(event.reply);
        break;
      case "error":
        throw new Error(event.message);
      case "done":
        break;
    }
  };

  try {
    for (;;) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch (err) {
        if (idledOut) {
          throw new Error(
            "The navigator is taking longer than expected. It may still be finishing in the background. Try again, or start a new conversation.",
          );
        }
        if ((err as Error).name === "AbortError") throw err; // external cancel
        throw new Error(
          "The connection to the navigator was interrupted. Try again.",
        );
      }
      arm(); // a chunk arrived; reset the idle watchdog
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      let nl: number;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (line) handle(JSON.parse(line) as StreamEvent);
      }
    }
    const tail = buffer.trim();
    if (tail) handle(JSON.parse(tail) as StreamEvent);
  } finally {
    clearTimeout(timer);
  }
}
