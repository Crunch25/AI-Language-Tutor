"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, UserRound } from "lucide-react";

import { ApiError, userApi } from "@/lib/api/client";
import type { UserRead } from "@/lib/types/api";
import { getAccessToken } from "@/lib/auth/tokenStorage";
import styles from "./page.module.css";

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserRead | null>(null);
  const [fullName, setFullName] = useState("");
  const [nativeLanguage, setNativeLanguage] = useState("English");
  const [targetLanguage, setTargetLanguage] = useState("Spanish");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    let cancelled = false;
    void userApi.getMe()
      .then((user) => {
        if (cancelled) return;
        setProfile(user);
        setFullName(user.full_name ?? "");
        setNativeLanguage(user.native_language);
        setTargetLanguage(user.target_language);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? err.message
            : "Unable to load your profile. Please try again."
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSaving) return;

    setIsSaving(true);
    setError(null);
    setSaved(false);
    try {
      const updatedProfile = await userApi.updateMe({
        full_name: fullName.trim() || null,
        native_language: nativeLanguage,
        target_language: targetLanguage,
      });
      setProfile(updatedProfile);
      setFullName(updatedProfile.full_name ?? "");
      setSaved(true);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to save your profile. Please try again."
      );
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <Link href="/dashboard" className={styles.backLink}>
          <ArrowLeft size={17} />
          Back to conversations
        </Link>
        <span className={styles.brand}><UserRound size={18} /> Language Tutor</span>
      </header>

      <section className={styles.content}>
        <div className={styles.heading}>
          <span className={styles.eyebrow}>Your learning account</span>
          <h1>Profile settings</h1>
          <p>Update your details and choose the languages you want to practice.</p>
        </div>

        {error && <div className={styles.error} role="alert">{error}</div>}
        {saved && (
          <div className={styles.success} role="status">
            <Check size={17} /> Your profile has been saved.
          </div>
        )}

        <form className={styles.card} onSubmit={handleSubmit}>
          <div className={styles.cardHeading}>
            <div className={styles.avatar}>
              {(fullName || profile?.email || "L").slice(0, 1).toUpperCase()}
            </div>
            <div>
              <h2>Personal details</h2>
              <p>Your email address is used to sign in.</p>
            </div>
          </div>

          {isLoading ? (
            <p className={styles.loading}>Loading your profile...</p>
          ) : (
            <>
              <div className={styles.fields}>
                <label className={styles.field}>
                  <span>Full name</span>
                  <input
                    autoComplete="name"
                    maxLength={150}
                    value={fullName}
                    onChange={(event) => setFullName(event.target.value)}
                    placeholder="Your name"
                    disabled={isSaving}
                  />
                </label>

                <label className={styles.field}>
                  <span>Email address</span>
                  <input value={profile?.email ?? ""} readOnly disabled />
                </label>

                <label className={styles.field}>
                  <span>Native language</span>
                  <input
                    value={nativeLanguage}
                    onChange={(event) => setNativeLanguage(event.target.value)}
                    disabled={isSaving}
                  />
                </label>

                <label className={styles.field}>
                  <span>Language to practice</span>
                  <input
                    value={targetLanguage}
                    onChange={(event) => setTargetLanguage(event.target.value)}
                    disabled={isSaving}
                  />
                  <small>New conversations will use this language.</small>
                </label>
              </div>

              <div className={styles.actions}>
                <Link href="/dashboard" className={styles.cancelButton}>Cancel</Link>
                <button type="submit" disabled={isSaving} className={styles.saveButton}>
                  {isSaving ? "Saving..." : "Save changes"}
                </button>
              </div>
            </>
          )}
        </form>
      </section>
    </main>
  );
}
