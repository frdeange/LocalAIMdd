"use client";

/**
 * Home Page
 * =========
 * Root page composing the sidebar (ConversationList) and main area (Chat).
 * Manages the active conversation state.
 */

import { useState } from "react";
import ConversationList from "@/components/ConversationList";
import Chat from "@/components/Chat";

export default function Home() {
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const handleMessageSent = () => {
    // Trigger conversation list refresh after new messages are sent
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="flex h-screen bg-white dark:bg-gray-900">
      {/* Mobile sidebar toggle */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-3 left-3 z-50 p-2 rounded-lg bg-white dark:bg-gray-800 shadow-md border border-gray-200 dark:border-gray-700"
      >
        <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {sidebarOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } lg:translate-x-0 fixed lg:relative z-40 w-72 h-full transition-transform duration-200 ease-in-out`}
      >
        <ConversationList
          activeId={activeConversationId}
          onSelect={(id) => {
            setActiveConversationId(id || null);
            // Close sidebar on mobile after selection
            if (window.innerWidth < 1024) setSidebarOpen(false);
          }}
          refreshKey={refreshKey}
        />
      </div>

      {/* Overlay for mobile sidebar */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/50"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0">
        <Chat conversationId={activeConversationId} onMessageSent={handleMessageSent} />
      </main>
    </div>
  );
}
