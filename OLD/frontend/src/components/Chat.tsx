"use client";

/**
 * Chat Component
 * ==============
 * Main chat interface that integrates message display, input, and SSE streaming.
 * Manages the full lifecycle: load conversation → display messages → send → stream → persist.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentState, ConversationResponse, MessageResponse, SSEEvent } from "@/lib/types";
import { AGENT_PIPELINE } from "@/lib/types";
import { getConversation, sendMessage } from "@/lib/api";
import { useSSE } from "@/hooks/useSSE";
import MessageBubble from "./MessageBubble";
import PipelineStatus from "./PipelineStatus";

interface Props {
  conversationId: string | null;
  onMessageSent: () => void;
}

function makeInitialAgentStates(): AgentState[] {
  return AGENT_PIPELINE.map((a) => ({
    ...a,
    status: "pending",
  }));
}

export default function Chat({ conversationId, onMessageSent }: Props) {
  const [conversation, setConversation] = useState<ConversationResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [input, setInput] = useState("");
  const [agentStates, setAgentStates] = useState<AgentState[]>(makeInitialAgentStates());
  const [error, setError] = useState<string | null>(null);
  const [loadingConversation, setLoadingConversation] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, agentStates]);

  // Load conversation when ID changes
  useEffect(() => {
    if (!conversationId) {
      setConversation(null);
      setMessages([]);
      return;
    }

    setLoadingConversation(true);
    setError(null);

    getConversation(conversationId)
      .then((conv) => {
        setConversation(conv);
        setMessages(conv.messages);
      })
      .catch((err) => {
        console.error("Failed to load conversation:", err);
        setError("Failed to load conversation");
      })
      .finally(() => setLoadingConversation(false));
  }, [conversationId]);

  // SSE event handler
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    switch (event.type) {
      case "workflow_started":
        setAgentStates(makeInitialAgentStates());
        break;

      case "agent_started":
        setAgentStates((prev) =>
          prev.map((a) =>
            a.name === event.agent ? { ...a, status: "running" } : a
          )
        );
        break;

      case "agent_completed":
        setAgentStates((prev) =>
          prev.map((a) =>
            a.name === event.agent
              ? { ...a, status: "completed", output: event.output }
              : a
          )
        );
        // Only add a message bubble if the agent produced meaningful output
        if (event.output && event.output.trim().length > 1) {
          setMessages((prev) => [
            ...prev,
            {
              id: `temp-${event.agent}-${Date.now()}`,
              role: "assistant",
              author_name: event.agent,
              content: event.output,
              step_number: event.step,
              created_at: new Date().toISOString(),
            },
          ]);
        }
        break;

      case "workflow_completed":
        // Pipeline is done — all agents should be completed
        break;

      case "error":
        setError(event.message);
        setAgentStates((prev) =>
          prev.map((a) =>
            a.status === "running" ? { ...a, status: "error" } : a
          )
        );
        break;
    }
  }, []);

  const handleComplete = useCallback(() => {
    onMessageSent();
  }, [onMessageSent]);

  const handleError = useCallback((err: Error) => {
    setError(err.message);
  }, []);

  const { isStreaming, startStream } = useSSE({
    onEvent: handleSSEEvent,
    onError: handleError,
    onComplete: handleComplete,
  });

  // Send message handler
  const handleSend = async () => {
    if (!conversationId || !input.trim() || isStreaming) return;

    const content = input.trim();
    setInput("");
    setError(null);

    // Optimistic: add user message locally
    const userMessage: MessageResponse = {
      id: `temp-user-${Date.now()}`,
      role: "user",
      author_name: "User",
      content,
      step_number: 0,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Reset pipeline
    setAgentStates(makeInitialAgentStates());

    try {
      const response = await sendMessage(conversationId, content);
      await startStream(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
    }
  };

  // Handle Enter key (Shift+Enter for newline)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const target = e.target;
    target.style.height = "auto";
    target.style.height = `${Math.min(target.scrollHeight, 150)}px`;
  };

  // ── Empty state ────────────────────────────────────────────

  if (!conversationId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center max-w-md px-4">
          <div className="text-6xl mb-4">🌍</div>
          <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-200 mb-2">
            Travel Planner
          </h2>
          <p className="text-gray-500 dark:text-gray-400 mb-6">
            AI-powered multi-agent travel planning. Create a conversation and describe your dream trip!
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Three AI agents — Researcher, Weather Analyst, and Planner — collaborate
            to create your perfect itinerary.
          </p>
        </div>
      </div>
    );
  }

  // ── Loading state ──────────────────────────────────────────

  if (loadingConversation) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  // ── Chat view ──────────────────────────────────────────────

  return (
    <div className="flex-1 flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <h1 className="text-lg font-semibold text-gray-800 dark:text-gray-200 truncate">
          {conversation?.title || "Conversation"}
        </h1>
      </div>

      {/* Pipeline status */}
      <PipelineStatus agents={agentStates} visible={isStreaming} />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-400 dark:text-gray-500 text-sm">
              Send a message to start planning your trip.
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-4 mb-2 px-4 py-2 rounded-lg bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Input area */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="flex items-end gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Describe your trip... (Enter to send, Shift+Enter for new line)"
            disabled={isStreaming}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 px-4 py-3 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            className="flex-shrink-0 p-3 rounded-xl bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="Send message"
          >
            {isStreaming ? (
              <div className="w-5 h-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19V5m0 0l-7 7m7-7l7 7"
                />
              </svg>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
