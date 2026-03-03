"use client";

/**
 * PipelineStatus
 * ==============
 * Visual indicator showing the progress of the three-agent pipeline.
 * Displays as a horizontal step indicator: Researcher → Weather Analyst → Planner
 */

import type { AgentState } from "@/lib/types";

interface Props {
  agents: AgentState[];
  visible: boolean;
}

const STATUS_STYLES: Record<string, { dot: string; text: string; line: string }> = {
  pending: {
    dot: "bg-gray-300 dark:bg-gray-600",
    text: "text-gray-400 dark:text-gray-500",
    line: "bg-gray-200 dark:bg-gray-700",
  },
  running: {
    dot: "bg-primary-500 animate-pulse ring-4 ring-primary-200 dark:ring-primary-900",
    text: "text-primary-600 dark:text-primary-400 font-medium",
    line: "bg-primary-200 dark:bg-primary-800",
  },
  completed: {
    dot: "bg-emerald-500",
    text: "text-emerald-600 dark:text-emerald-400",
    line: "bg-emerald-300 dark:bg-emerald-700",
  },
  error: {
    dot: "bg-red-500",
    text: "text-red-600 dark:text-red-400",
    line: "bg-red-200 dark:bg-red-800",
  },
};

export default function PipelineStatus({ agents, visible }: Props) {
  if (!visible) return null;

  return (
    <div className="px-4 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-center gap-1">
        {agents.map((agent, i) => {
          const styles = STATUS_STYLES[agent.status];
          return (
            <div key={agent.name} className="flex items-center">
              {/* Step indicator */}
              <div className="flex flex-col items-center">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full transition-all duration-300 ${styles.dot}`}>
                    {agent.status === "completed" && (
                      <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    )}
                  </div>
                  <span className={`text-xs transition-colors duration-300 ${styles.text}`}>
                    {agent.displayName}
                  </span>
                </div>
              </div>

              {/* Connector line */}
              {i < agents.length - 1 && (
                <div
                  className={`w-8 h-0.5 mx-2 transition-colors duration-500 ${
                    agents[i + 1].status !== "pending" ? styles.line : "bg-gray-200 dark:bg-gray-700"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
