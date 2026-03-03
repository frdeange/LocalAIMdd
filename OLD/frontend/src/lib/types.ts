/**
 * TypeScript interfaces mirroring the API schemas.
 */

// ── Conversation ─────────────────────────────────────────────

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface MessageResponse {
  id: string;
  role: "user" | "assistant";
  author_name: string | null;
  content: string;
  step_number: number;
  created_at: string;
}

export interface ConversationResponse {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: MessageResponse[];
}

// ── SSE Events ───────────────────────────────────────────────

export type SSEEventType =
  | "workflow_started"
  | "agent_started"
  | "agent_completed"
  | "workflow_completed"
  | "error";

export interface WorkflowStartedEvent {
  type: "workflow_started";
  workflow: string;
}

export interface AgentStartedEvent {
  type: "agent_started";
  agent: string;
  step: number;
}

export interface AgentCompletedEvent {
  type: "agent_completed";
  agent: string;
  step: number;
  output: string;
}

export interface WorkflowCompletedEvent {
  type: "workflow_completed";
  final_output: string;
}

export interface WorkflowErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent =
  | WorkflowStartedEvent
  | AgentStartedEvent
  | AgentCompletedEvent
  | WorkflowCompletedEvent
  | WorkflowErrorEvent;

// ── Agent Pipeline ───────────────────────────────────────────

export type AgentStatus = "pending" | "running" | "completed" | "error";

export interface AgentState {
  name: string;
  displayName: string;
  status: AgentStatus;
  output?: string;
}

export const AGENT_PIPELINE: { name: string; displayName: string }[] = [
  { name: "Researcher", displayName: "Researcher" },
  { name: "WeatherAnalyst", displayName: "Weather Analyst" },
  { name: "Planner", displayName: "Planner" },
];
