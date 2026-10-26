"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, LogOut, Plus, SquareSquare, MessageSquare, Trash2, UserRound } from "lucide-react";

import { useChatStream } from "@/hooks/useChatStream";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { ChatInput } from "@/components/chat/ChatInput";
import { FeedbackSidebar } from "@/components/chat/FeedbackSidebar";
import { removeTokens, getAccessToken } from "@/lib/auth/tokenStorage";
import { chatApi, userApi, type ChatSessionRead } from "@/lib/api/client";
import styles from "./page.module.css";

export default function DynamicDashboardPage() {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);

  // Dynamic Session State
  const [sessions, setSessions] = useState<ChatSessionRead[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(true);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<string | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  // Initialize Chat Stream only if a session is selected
  const {
    messages,
    isStreaming,
    isLoadingMessages,
    streamingMessage,
    vocabHints,
    grammarFeedback,
    error,
    sendMessage,
    abortStream,
  } = useChatStream(activeSessionId || "");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [userHasScrolledUp, setUserHasScrolledUp] = useState(false);

  // Fetch historical sessions on mount
  useEffect(() => {
    setMounted(true);
    if (!getAccessToken()) {
      router.push("/login");
      return;
    }

    let cancelled = false;
    const loadDashboard = async () => {
      const [sessionsResult, userResult] = await Promise.allSettled([
        chatApi.getSessions(),
        userApi.getMe(),
      ]);
      if (cancelled) return;

      const loadErrors: string[] = [];
      if (sessionsResult.status === "fulfilled") {
        setSessions(sessionsResult.value);
        if (sessionsResult.value.length > 0) {
          setActiveSessionId(sessionsResult.value[0].id);
        }
      } else {
        loadErrors.push(
          sessionsResult.reason instanceof Error
            ? sessionsResult.reason.message
            : "Failed to load conversations."
        );
      }

      if (userResult.status === "fulfilled") {
        setTargetLanguage(userResult.value.target_language);
      } else {
        loadErrors.push(
          userResult.reason instanceof Error
            ? userResult.reason.message
            : "Failed to load your profile."
        );
      }
      if (loadErrors.length > 0) setDashboardError(loadErrors.join(" "));
      setIsLoadingSessions(false);
    };

    void loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleCreateNewSession = async () => {
    if (isCreatingSession || isLoadingSessions || !targetLanguage) return;
    setIsCreatingSession(true);
    setDashboardError(null);
    try {
      const newSession = await chatApi.createSession(targetLanguage);
      setSessions((currentSessions) => [newSession, ...currentSessions]);
      setActiveSessionId(newSession.id);
    } catch (err) {
      setDashboardError(
        err instanceof Error ? err.message : "Failed to create a conversation."
      );
    } finally {
      setIsCreatingSession(false);
    }
  };

  const handleDeleteSession = async (session: ChatSessionRead) => {
    if (deletingSessionId || !window.confirm(`Delete this ${session.target_language} conversation? This cannot be undone.`)) {
      return;
    }

    setDeletingSessionId(session.id);
    setDashboardError(null);
    try {
      await chatApi.deleteSession(session.id);
      const remainingSessions = sessions.filter((item) => item.id !== session.id);
      setSessions(remainingSessions);
      setActiveSessionId((currentActiveId) =>
        currentActiveId === session.id
          ? remainingSessions[0]?.id ?? null
          : currentActiveId
      );
    } catch (err) {
      setDashboardError(
        err instanceof Error ? err.message : "Failed to delete the conversation."
      );
    } finally {
      setDeletingSessionId(null);
    }
  };

  const handleScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const isScrolledUp = scrollHeight - scrollTop - clientHeight > 50;
    setUserHasScrolledUp(isScrolledUp);
  };

  useEffect(() => {
    if (!userHasScrolledUp && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, streamingMessage, userHasScrolledUp]);

  useEffect(() => {
    setUserHasScrolledUp(false);
  }, [activeSessionId]);

  const handleLogout = () => {
    removeTokens();
    router.push("/login");
  };

  if (!mounted) return null;

  return (
    <div className={styles.dashboard}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <div className={styles.brand}>
            <div className={styles.brandMark}>AI</div>
            <span>Language Tutor</span>
          </div>
          <div className={styles.headerActions}>
            {targetLanguage && (
              <span className={styles.learningLanguage}>
                Learning {targetLanguage}
              </span>
            )}
            <button
              onClick={handleCreateNewSession}
              disabled={isLoadingSessions || isCreatingSession || !targetLanguage}
              className={`${styles.button} ${styles.mobileNewChat}`}
            >
              <Plus size={16} />
              New chat
            </button>
            <button onClick={handleLogout} className={`${styles.button} ${styles.logout}`}>
              <LogOut size={16} />
              <span className={styles.logoutLabel}>Sign out</span>
            </button>
            <Link href="/profile" className={`${styles.button} ${styles.profileLink}`}>
              <UserRound size={16} />
              <span className={styles.profileLabel}>Profile</span>
            </Link>
          </div>
        </div>
      </header>

      {sessions.length > 0 && (
        <div className={styles.mobileSessionPicker}>
          <label className={styles.srOnly} htmlFor="mobile-session-select">Conversation</label>
          <select
            id="mobile-session-select"
            value={activeSessionId ?? ""}
            onChange={(event) => setActiveSessionId(event.target.value)}
            className={styles.sessionSelect}
          >
            {sessions.map((session) => (
              <option key={session.id} value={session.id}>
                {new Date(session.created_at).toLocaleDateString()} - {session.target_language}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.deleteSessionButton}
            onClick={() => {
              const session = sessions.find((item) => item.id === activeSessionId);
              if (session) void handleDeleteSession(session);
            }}
            disabled={!activeSessionId || deletingSessionId !== null}
            aria-label="Delete selected conversation"
            title="Delete selected conversation"
          >
            <Trash2 size={17} />
          </button>
        </div>
      )}

      <div className={styles.workspace}>
        {/* Left Sidebar: Session List */}
        <aside className={styles.sessionSidebar}>
          <div className={styles.sidebarHeader}>
            <button
              onClick={handleCreateNewSession}
              disabled={isLoadingSessions || isCreatingSession || !targetLanguage}
              className={`${styles.button} ${styles.primaryButton}`}
            >
              <Plus size={16} />
              {isCreatingSession ? "Creating..." : "New Conversation"}
            </button>
          </div>
          <div className={styles.sessionList}>
            {isLoadingSessions ? (
              <p className={styles.sidebarMessage}>Loading sessions...</p>
            ) : sessions.length === 0 ? (
              <p className={styles.sidebarMessage}>No past conversations.</p>
            ) : (
              sessions.map((session) => (
                <div className={styles.sessionRow} key={session.id}>
                  <button
                    onClick={() => setActiveSessionId(session.id)}
                    className={`${styles.sessionButton} ${
                      activeSessionId === session.id
                        ? styles.sessionButtonActive
                        : ""
                    }`}
                  >
                    <MessageSquare size={16} />
                    <div className={styles.sessionLabel}>
                      {new Date(session.created_at).toLocaleDateString()} - {session.target_language}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDeleteSession(session)}
                    disabled={deletingSessionId !== null}
                    className={styles.deleteSessionButton}
                    aria-label={`Delete ${session.target_language} conversation`}
                    title="Delete conversation"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>

        {/* Main Chat Workspace */}
        <main className={styles.chatPanel}>
          {dashboardError && (
            <div className={styles.alert} role="alert">
              <AlertCircle size={16} />
              {dashboardError}
            </div>
          )}
          {!activeSessionId ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}><MessageSquare size={26} /></div>
              <p className={styles.emptyTitle}>
                {isLoadingSessions ? "Loading conversations..." : "Start a conversation"}
              </p>
              {!isLoadingSessions && (
                <button
                  onClick={handleCreateNewSession}
                  disabled={isCreatingSession || !targetLanguage}
                  className={`${styles.button} ${styles.primaryButton}`}
                >
                  <Plus size={16} />
                  {isCreatingSession ? "Creating..." : "New conversation"}
                </button>
              )}
            </div>
          ) : (
            <>
              {error && (
                <div className={styles.alert}>
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}

              <div ref={scrollContainerRef} onScroll={handleScroll} className={styles.messageScroller}>
                <div className={styles.messageList}>
                  {isLoadingMessages && (
                    <p className={styles.loadingMessages}>Loading messages...</p>
                  )}
                  {messages.length === 0 && !isStreaming && (
                    <div className={styles.chatEmpty}>
                      <div className={styles.emptyIcon}><MessageSquare size={24} /></div>
                      <p className={styles.emptyTitle}>Start your practice session!</p>
                      <p>Say hello in your target language to begin.</p>
                    </div>
                  )}
                  {messages.map((msg) => (
                    <MessageBubble key={msg.id} message={msg} />
                  ))}
                  {isStreaming && streamingMessage && (
                    <MessageBubble
                      isStreaming={true}
                      message={{
                        id: "temp-streaming",
                        role: "assistant",
                        content: streamingMessage,
                        createdAt: new Date().toISOString(),
                      }}
                    />
                  )}
                  <div ref={messagesEndRef} className={styles.scrollAnchor} />
                </div>
              </div>

              {isStreaming && (
                <div className={styles.stopButtonPosition}>
                  <button onClick={abortStream} className={styles.stopButton}>
                    <SquareSquare size={14} /> Stop Generating
                  </button>
                </div>
              )}

              <div className={styles.composer}>
                <div className={styles.composerInner}>
                  <ChatInput onSend={sendMessage} isStreaming={isStreaming || isLoadingMessages} />
                </div>
              </div>
            </>
          )}
        </main>

        <FeedbackSidebar vocabHints={vocabHints} grammarFeedback={grammarFeedback} />
      </div>
    </div>
  );
}