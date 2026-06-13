export type Role = "user" | "assistant" | "error";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
}
