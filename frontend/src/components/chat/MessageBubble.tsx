"use client";

import React from "react";
import { User, Bot } from "lucide-react";
import type { ChatMessage } from "@/lib/types/api";
import styles from "./chat.module.css";

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`${styles.messageRow} ${isUser ? styles.userRow : ""}`}
      role="listitem"
    >
      <div
        className={`${styles.messageGroup} ${isUser ? styles.userGroup : ""}`}
      >
        {/* Avatar */}
        <div
          className={`${styles.avatar} ${isUser ? styles.userAvatar : ""}`}
          aria-hidden="true"
        >
          {isUser ? <User size={18} /> : <Bot size={18} />}
        </div>

        {/* Message Bubble */}
        <div
          className={`${styles.bubble} ${isUser ? styles.userBubble : ""} ${isStreaming ? styles.streamingBubble : ""}`}
        >
          <div>
            {message.content}
            {isStreaming && (
              <span
                className={styles.cursor}
                aria-label="Generating text..."
              />
            )}
          </div>

          <span
            className={styles.messageTime}
          >
            {new Date(message.createdAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      </div>
    </div>
  );
}