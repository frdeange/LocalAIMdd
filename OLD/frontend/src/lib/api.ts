/**
 * API Client
 * ==========
 * REST client for the Travel Planner API.
 * Uses NEXT_PUBLIC_API_URL for the base URL (defaults to http://localhost:8000/api).
 */

import type { ConversationResponse, ConversationSummary } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

// ── Conversations ────────────────────────────────────────────

export async function createConversation(
  title?: string
): Promise<ConversationResponse> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title || "New Conversation" }),
  });
  if (!res.ok) throw new Error(`Failed to create conversation: ${res.status}`);
  return res.json();
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/conversations`);
  if (!res.ok) throw new Error(`Failed to list conversations: ${res.status}`);
  return res.json();
}

export async function getConversation(
  id: string
): Promise<ConversationResponse> {
  const res = await fetch(`${API_BASE}/conversations/${id}`);
  if (!res.ok) {
    if (res.status === 404) throw new Error("Conversation not found");
    throw new Error(`Failed to get conversation: ${res.status}`);
  }
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete conversation: ${res.status}`);
}

// ── Messages (SSE) ───────────────────────────────────────────

/**
 * Send a message and return the SSE Response for streaming.
 * The caller is responsible for reading the stream.
 */
export async function sendMessage(
  conversationId: string,
  content: string
): Promise<Response> {
  const res = await fetch(
    `${API_BASE}/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    }
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Failed to send message: ${res.status} — ${text}`);
  }
  return res;
}
