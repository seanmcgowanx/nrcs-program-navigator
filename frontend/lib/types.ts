export type Role = "user" | "assistant" | "error";

// One tool the agent invoked during a turn, shown in the live trace and then
// collapsed under the answer. `summary` is filled in when the tool returns; it
// is undefined while the step is still running.
export interface TraceStep {
  id: string;
  label: string;
  summary?: string;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  // Present on assistant messages that called tools: the trace of that turn,
  // kept so the work stays inspectable in history.
  steps?: TraceStep[];
}
