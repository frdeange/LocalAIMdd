/**
 * useSSE Hook
 * ===========
 * Custom React hook that consumes an SSE stream from a fetch Response
 * and dispatches parsed events via a callback.
 *
 * Uses the ReadableStream API (no EventSource needed for POST requests).
 */

import { useCallback, useRef, useState } from "react";
import type { SSEEvent } from "@/lib/types";

interface UseSSEOptions {
  onEvent: (event: SSEEvent) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export function useSSE({ onEvent, onError, onComplete }: UseSSEOptions) {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const startStream = useCallback(
    async (response: Response) => {
      setIsStreaming(true);

      const reader = response.body?.getReader();
      if (!reader) {
        onError?.(new Error("Response body is not readable"));
        setIsStreaming(false);
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE events are separated by double newlines
          const parts = buffer.split("\n\n");
          // Keep the last incomplete part in the buffer
          buffer = parts.pop() || "";

          for (const part of parts) {
            if (!part.trim()) continue;

            let eventType = "";
            let eventData = "";

            for (const line of part.split("\n")) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                eventData = line.slice(6);
              }
            }

            if (eventType && eventData) {
              try {
                const data = JSON.parse(eventData);
                const parsed: SSEEvent = { ...data, type: eventType } as SSEEvent;
                onEvent(parsed);
              } catch {
                console.warn("Failed to parse SSE data:", eventData);
              }
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          onError?.(err);
        }
      } finally {
        reader.releaseLock();
        setIsStreaming(false);
        onComplete?.();
      }
    },
    [onEvent, onError, onComplete]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { isStreaming, startStream, cancel };
}
