"use client";

/**
 * MessageBubble
 * =============
 * Renders a single message in the chat with Markdown support.
 * User messages align right, assistant messages align left with agent name badge.
 */

import ReactMarkdown from "react-markdown";
import type { MessageResponse } from "@/lib/types";

interface Props {
  message: MessageResponse;
}

const AGENT_COLORS: Record<string, string> = {
  Researcher: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  WeatherAnalyst: "bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300",
  Planner: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300",
};

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-primary-600 text-white rounded-br-md"
            : "bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 shadow-sm border border-gray-100 dark:border-gray-700 rounded-bl-md"
        }`}
      >
        {/* Agent name badge */}
        {!isUser && message.author_name && (
          <div className="mb-1.5">
            <span
              className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${
                AGENT_COLORS[message.author_name] ||
                "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300"
              }`}
            >
              {message.author_name}
            </span>
          </div>
        )}

        {/* Content */}
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        ) : (
          <div className="markdown-content text-sm">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Timestamp */}
        <p
          className={`text-xs mt-1.5 ${
            isUser ? "text-primary-200" : "text-gray-400 dark:text-gray-500"
          }`}
        >
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}
