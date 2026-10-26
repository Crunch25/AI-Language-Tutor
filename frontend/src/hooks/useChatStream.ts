// hooks/useChatStream.ts

import { useState, useRef, useCallback, useEffect } from "react";
import { getAccessToken, getRefreshToken, setTokens, removeTokens } from "@/lib/auth/tokenStorage";
import { chatApi } from "@/lib/api/client";
import type {
  ChatMessage,
  AIStreamChunk,
  TokenResponse,
  TokenRefreshRequest,
} from "@/lib/types/api";
import type { ChatMessageRead } from "@/lib/api/client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";
const EMPTY_MESSAGES: ChatMessage[] = [];

function getConversationFeedback(messages: ChatMessageRead[]): {
  grammar: string[];
  vocabulary: string[];
} {
  const grammar: string[] = [];
  const vocabulary = new Set<string>();

  for (const message of messages) {
    if (message.role !== "user") continue;
    const metadata = message.audio_metadata;
    const analysis = metadata?.grammar_analysis;
    if (!analysis || typeof analysis !== "object") continue;

    if ("corrections" in analysis && Array.isArray(analysis.corrections)) {
      for (const correction of analysis.corrections) {
        if (!correction || typeof correction !== "object") continue;
        const original = "original" in correction ? correction.original : undefined;
        const replacement = "replacement" in correction ? correction.replacement : undefined;
        const explanation = "explanation" in correction ? correction.explanation : undefined;
        if (
          typeof original === "string" &&
          typeof replacement === "string" &&
          typeof explanation === "string"
        ) {
          grammar.push(`${original} → ${replacement}: ${explanation}`);
        }
      }
    }

    if ("vocabulary_hints" in analysis && Array.isArray(analysis.vocabulary_hints)) {
      for (const hint of analysis.vocabulary_hints) {
        if (typeof hint === "string" && hint.trim()) vocabulary.add(hint.trim());
      }
    }
  }

  return { grammar, vocabulary: Array.from(vocabulary) };
}

export interface UseChatStreamReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  isLoadingMessages: boolean;
  streamingMessage: string;
  vocabHints: string[];
  grammarFeedback: string[];
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  abortStream: () => void;
}

export function useChatStream(
  sessionId: string,
  initialMessages: ChatMessage[] = EMPTY_MESSAGES
): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamingMessage, setStreamingMessage] = useState<string>("");
  const [vocabHints, setVocabHints] = useState<string[]>([]);
  const [grammarFeedback, setGrammarFeedback] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const currentSessionIdRef = useRef(sessionId);
  currentSessionIdRef.current = sessionId;

  /**
   * Cancels any active SSE stream request.
   */
  const abortStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  // Reset session-scoped UI and load the selected conversation's history.
  useEffect(() => {
    let cancelled = false;
    setMessages(initialMessages);
    setVocabHints([]);
    setGrammarFeedback([]);
    setError(null);
    setStreamingMessage("");
    setIsStreaming(false);

    if (sessionId && sessionId !== "undefined") {
      setIsLoadingMessages(true);
      chatApi
        .getMessages(sessionId)
        .then((history) => {
          if (cancelled || currentSessionIdRef.current !== sessionId) return;
          const feedback = getConversationFeedback(history);
          setGrammarFeedback(feedback.grammar);
          setVocabHints(feedback.vocabulary);
          setMessages(
            history
              .flatMap((message) =>
                message.role === "user" || message.role === "assistant"
                  ? [{
                      id: message.id,
                      role: message.role,
                      content: message.content,
                      createdAt: message.created_at,
                    }]
                  : []
              )
          );
        })
        .catch((err: unknown) => {
          if (cancelled || currentSessionIdRef.current !== sessionId) return;
          setError(
            err instanceof Error ? err.message : "Failed to load conversation messages."
          );
        })
        .finally(() => {
          if (!cancelled && currentSessionIdRef.current === sessionId) {
            setIsLoadingMessages(false);
          }
        });
    } else {
      setIsLoadingMessages(false);
    }

    return () => {
      cancelled = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, [sessionId, initialMessages]);

  /**
   * Internal helper to execute the streaming fetch and transparently retry once on 401.
   */
  const executeStreamFetch = async (
    url: string,
    content: string,
    signal: AbortSignal
  ): Promise<Response> => {
    const token = getAccessToken();

    const makeRequest = (authToken: string | null) =>
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({ content }),
        signal,
      });

    let response = await makeRequest(token);

    // If access token expired, attempt a single rotation before streaming
    if (response.status === 401) {
      const refreshTokenStr = getRefreshToken();
      if (!refreshTokenStr) {
        removeTokens();
        if (typeof window !== "undefined") window.location.href = "/login";
        throw new Error("Session expired. Please log in again.");
      }

      const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshTokenStr } as TokenRefreshRequest),
        signal,
      });

      if (!refreshResponse.ok) {
        removeTokens();
        if (typeof window !== "undefined") window.location.href = "/login";
        throw new Error("Authentication expired. Please log in again.");
      }

      const tokenData: TokenResponse = await refreshResponse.json();
      setTokens(tokenData.access_token, tokenData.refresh_token);

      response = await makeRequest(tokenData.access_token);
    }

    return response;
  };

  /**
   * Sends a user message, optimistically updates the timeline, and reads the SSE response stream.
   */
  const sendMessage = useCallback(
    async (content: string): Promise<void> => {
      const trimmed = content.trim();
      if (!trimmed || isStreaming) return;
      if (!sessionId || sessionId === "undefined") {
        setError("Cannot send message: No active chat session.");
        return;
      }
      const requestSessionId = sessionId;

      // Cancel any residual controller and initialize a fresh one
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Reset turn-specific state
      setError(null);
      setStreamingMessage("");
      setIsStreaming(true);

      // 1. Optimistically append user message to conversation timeline
      const optimisticUserMessage: ChatMessage = {
        id: typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `user-${Date.now()}`,
        role: "user",
        content: trimmed,
        createdAt: new Date().toISOString(),
      };

      setMessages((prev) =>
        currentSessionIdRef.current === requestSessionId
          ? [...prev, optimisticUserMessage]
          : prev
      );

      let accumulatedAssistantText = "";

      try {
        const url = `${API_BASE_URL}/sessions/${sessionId}/messages`;
        const response = await executeStreamFetch(url, trimmed, controller.signal);

        if (!response.ok) {
          let errorDetail = `Stream request failed with status ${response.status}`;
          try {
            const errJson = await response.json();
            if (errJson?.detail) {
              errorDetail =
                typeof errJson.detail === "string"
                  ? errJson.detail
                  : JSON.stringify(errJson.detail);
            }
          } catch {
            // Fallback if body is plain text or empty
          }
          throw new Error(errorDetail);
        }

        if (!response.body) {
          throw new Error("ReadableStream is not supported or response body is empty.");
        }

        // 2. Process SSE stream using ReadableStreamDefaultReader & TextDecoder
        const reader: ReadableStreamDefaultReader<Uint8Array> = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let partialBuffer = "";
        let streamDone = false;

        while (!streamDone) {
          const { done, value } = await reader.read();
          if (done) break;
          if (currentSessionIdRef.current !== requestSessionId) break;

          // Decode binary chunk; `{ stream: true }` preserves multi-byte UTF-8 characters split across packets
          partialBuffer += decoder.decode(value, { stream: true });

          // Normalize CRLF to LF and split by SSE frame delimiter (\n\n)
          const normalizedBuffer = partialBuffer.replace(/\r\n/g, "\n");
          const frames = normalizedBuffer.split("\n\n");

          // The last element is either "" (if buffer ended with \n\n) or an incomplete frame
          partialBuffer = frames.pop() ?? "";

          for (const frame of frames) {
            const lines = frame.split("\n");
            for (const line of lines) {
              const trimmedLine = line.trim();
              if (!trimmedLine.startsWith("data:")) continue;

              const rawJson = trimmedLine.slice(5).trim();
              if (!rawJson) continue;

              let chunk: AIStreamChunk;
              try {
                chunk = JSON.parse(rawJson) as AIStreamChunk;
              } catch {
                // Skip malformed JSON frames
                continue;
              }

              switch (chunk.event) {
                case "token": {
                  if (chunk.delta) {
                    accumulatedAssistantText += chunk.delta;
                    if (currentSessionIdRef.current === requestSessionId) {
                      setStreamingMessage(accumulatedAssistantText);
                    }
                  }
                  break;
                }

                case "vocab_hint": {
                  const hint =
                    chunk.delta ||
                    (typeof chunk.metadata?.word === "string" ? chunk.metadata.word : "");
                  if (hint) {
                    if (currentSessionIdRef.current === requestSessionId) {
                      setVocabHints((prev) => (prev.includes(hint) ? prev : [...prev, hint]));
                    }
                  }
                  break;
                }

                case "grammar_correction": {
                  const correction =
                    chunk.delta ||
                    (typeof chunk.metadata?.explanation === "string"
                      ? chunk.metadata.explanation
                      : "");
                  if (correction) {
                    if (currentSessionIdRef.current === requestSessionId) {
                      setGrammarFeedback((prev) => [...prev, correction]);
                    }
                  }
                  break;
                }

                case "error": {
                  if (chunk.delta && currentSessionIdRef.current === requestSessionId) {
                    setError(chunk.delta);
                  }
                  break;
                }

                case "done": {
                  // If backend sends an inline error message on a `done` event when a session is missing
                  if (chunk.delta && !accumulatedAssistantText) {
                    if (currentSessionIdRef.current === requestSessionId) {
                      setError(chunk.delta);
                    }
                  }
                  streamDone = true;
                  break;
                }
              }
            }
          }
        }

        // Flush any remaining decoder bytes
        partialBuffer += decoder.decode();

        // 3. Commit completed assistant response to the message timeline
        if (accumulatedAssistantText.trim().length > 0) {
          const assistantMessage: ChatMessage = {
            id: typeof crypto !== "undefined" && crypto.randomUUID
              ? crypto.randomUUID()
              : `assistant-${Date.now()}`,
            role: "assistant",
            content: accumulatedAssistantText,
            createdAt: new Date().toISOString(),
          };
          if (currentSessionIdRef.current === requestSessionId) {
            setMessages((prev) => [...prev, assistantMessage]);
          }
        }

        if (currentSessionIdRef.current === requestSessionId) {
          setStreamingMessage("");
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          // Preserve partial assistant response if the user manually stopped the stream
          if (
            currentSessionIdRef.current === requestSessionId &&
            accumulatedAssistantText.trim().length > 0
          ) {
            setMessages((prev) => [
              ...prev,
              {
                id: `assistant-aborted-${Date.now()}`,
                role: "assistant",
                content: accumulatedAssistantText,
                createdAt: new Date().toISOString(),
              },
            ]);
          }
          if (currentSessionIdRef.current === requestSessionId) {
            setStreamingMessage("");
          }
        } else {
          const message =
            err instanceof Error ? err.message : "An unexpected streaming error occurred.";
          if (currentSessionIdRef.current === requestSessionId) {
            setError(message);
          }
        }
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
          if (currentSessionIdRef.current === requestSessionId) {
            setIsStreaming(false);
          }
        }
      }
    },
    [sessionId, isStreaming]
  );

  return {
    messages,
    isStreaming,
    isLoadingMessages,
    streamingMessage,
    vocabHints,
    grammarFeedback,
    error,
    sendMessage,
    abortStream,
  };
}