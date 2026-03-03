"use client";

/**
 * ConversationList
 * ================
 * Sidebar component showing all conversations with create/delete actions.
 */

import { useEffect, useState } from "react";
import type { ConversationSummary } from "@/lib/types";
import { listConversations, createConversation, deleteConversation } from "@/lib/api";

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  refreshKey: number;
}

export default function ConversationList({ activeId, onSelect, refreshKey }: Props) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchConversations = async () => {
    try {
      const data = await listConversations();
      setConversations(data);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, [refreshKey]);

  const handleCreate = async () => {
    try {
      const conv = await createConversation();
      await fetchConversations();
      onSelect(conv.id);
    } catch (err) {
      console.error("Failed to create conversation:", err);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;

    try {
      await deleteConversation(id);
      await fetchConversations();
      if (activeId === id) {
        onSelect("");
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours < 1) return "Just now";
    if (diffHours < 24) return `${Math.floor(diffHours)}h ago`;
    if (diffHours < 168) return `${Math.floor(diffHours / 24)}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
            Conversations
          </h2>
          <button
            onClick={handleCreate}
            className="p-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition-colors"
            title="New conversation"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="text-center py-8 px-4">
            <p className="text-gray-500 dark:text-gray-400 text-sm">
              No conversations yet.
            </p>
            <button
              onClick={handleCreate}
              className="mt-2 text-primary-600 hover:text-primary-700 text-sm font-medium"
            >
              Start your first trip plan
            </button>
          </div>
        ) : (
          <ul className="py-2">
            {conversations.map((conv) => (
              <li key={conv.id}>
                <button
                  onClick={() => onSelect(conv.id)}
                  className={`w-full text-left px-4 py-3 flex items-start gap-2 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800 group ${
                    activeId === conv.id
                      ? "bg-primary-50 dark:bg-primary-900/30 border-r-2 border-primary-600"
                      : ""
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
                      {conv.title}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      {conv.message_count} messages · {formatDate(conv.updated_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, conv.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded text-gray-400 hover:text-red-500 transition-all"
                    title="Delete"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
