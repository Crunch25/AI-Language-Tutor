"use client";

import React from "react";
import { BookOpen, PenTool } from "lucide-react";
import styles from "./chat.module.css";

interface FeedbackSidebarProps {
  vocabHints: string[];
  grammarFeedback: string[];
}

export function FeedbackSidebar({ vocabHints, grammarFeedback }: FeedbackSidebarProps) {
  if (vocabHints.length === 0 && grammarFeedback.length === 0) {
    return (
      <div className={styles.feedbackEmpty}>
        <BookOpen size={34} />
        <p>Start chatting! Vocabulary hints and grammar corrections will appear here.</p>
      </div>
    );
  }

  return (
    <aside className={styles.feedbackPanel}>
      <div className={styles.feedbackHeader}>
        <h2>Session feedback</h2>
      </div>

      <div className={styles.feedbackBody}>
        {/* Grammar Section */}
        {grammarFeedback.length > 0 && (
          <section>
            <h3 className={`${styles.feedbackSection} ${styles.grammarTitle}`}>
              <PenTool size={14} />
              Grammar Notes
            </h3>
            <ul className={styles.feedbackList}>
              {grammarFeedback.map((feedback, idx) => (
                <li key={idx} className={styles.grammarItem}>
                  {feedback}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Vocabulary Section */}
        {vocabHints.length > 0 && (
          <section>
            <h3 className={styles.feedbackSection}>
              <BookOpen size={14} />
              Vocabulary Targets
            </h3>
            <ul className={styles.feedbackList}>
              {vocabHints.map((hint, idx) => (
                <li key={idx} className={styles.vocabItem}>
                  <span className={styles.vocabDot} />
                  {hint}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </aside>
  );
}