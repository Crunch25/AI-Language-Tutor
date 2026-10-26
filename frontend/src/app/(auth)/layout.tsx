// app/(auth)/layout.tsx

import React from "react";
import { Sparkles, MessageCircle, PenTool } from "lucide-react";
import styles from "./layout.module.css";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={styles.authLayout}>
      {/* Left Panel - Branding (Hidden on mobile/tablet) */}
      <div className={styles.brandPanel}>
        <div className={styles.brandContent}>
          <h1>
            Master a new language naturally.
          </h1>
          <p>
            Practice conversational skills with an AI tutor that adapts to your CEFR level and provides real-time pedagogical feedback.
          </p>

          <div className={styles.featureList}>
            <span className={styles.feature}>
              <MessageCircle size={16} /> Authentic Conversations
            </span>
            <span className={styles.feature}>
              <PenTool size={16} /> Real-time Grammar Feedback
            </span>
            <span className={styles.feature}>
              <Sparkles size={16} /> Spaced Repetition Memory
            </span>
          </div>
        </div>

        {/* Abstract Background Decorations */}
        <div className={styles.orbOne} />
        <div className={styles.orbTwo} />
      </div>

      {/* Right Panel - Auth Forms Container */}
      <div className={styles.formPanel}>
        <div className={styles.formCard}>
          {children}
        </div>
      </div>
    </div>
  );
}