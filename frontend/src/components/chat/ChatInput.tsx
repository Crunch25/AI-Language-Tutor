"use client";

import React, { useState, useRef, useEffect, KeyboardEvent } from "react";
import { SendHorizontal, Loader2 } from "lucide-react";
import styles from "./chat.module.css";

interface ChatInputProps {
  onSend: (content: string) => void;
  isStreaming: boolean;
  maxLength?: number;
}

export function ChatInput({ onSend, isStreaming, maxLength = 2000 }: ChatInputProps) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [content]);

  const handleSend = () => {
    const trimmed = content.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setContent("");

    // Reset height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault(); // Prevent newline
      handleSend();
    }
  };

  const remainingChars = maxLength - content.length;

  return (
    <div className={styles.composer}>
      <div className={styles.composerRow}>
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value.slice(0, maxLength))}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder={isStreaming ? "AI is typing..." : "Type a message in your target language..."}
          className={styles.textarea}
          rows={1}
          aria-label="Chat input"
        />

        <button
          onClick={handleSend}
          disabled={!content.trim() || isStreaming}
          className={styles.sendButton}
          aria-label="Send message"
        >
          {isStreaming ? (
            <Loader2 size={20} className={styles.sendSpinner} />
          ) : (
            <SendHorizontal size={20} />
          )}
        </button>
      </div>

      <div className={styles.composerMeta}>
        <span>
          <span className={styles.keyboardHint}>Enter</span> to send, <span className={styles.keyboardHint}>Shift + Enter</span> for newline
        </span>
        <span className={remainingChars < 50 ? styles.charWarning : undefined}>
          {content.length}/{maxLength}
        </span>
      </div>
    </div>
  );
}