// app/(auth)/register/page.tsx

"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, X, Loader2, AlertCircle } from "lucide-react";

import { registerSchema, type RegisterFormData } from "@/lib/validations/auth";
import { authApi, ApiError } from "@/lib/api/client";
import { setTokens } from "@/lib/auth/tokenStorage";
import styles from "./page.module.css";

const PRESET_LANGUAGES = ["English", "Spanish", "French", "German", "Ukrainian", "Japanese", "Korean", "Mandarin"];

export default function RegisterPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      native_language: "English",
      target_language: "Spanish",
    }
  });

  // Watch password to dynamically update complexity checklist
  const watchPassword = watch("password", "");

  const passwordChecks = [
    { label: "8+ characters", valid: watchPassword.length >= 8 },
    { label: "One uppercase", valid: /[A-Z]/.test(watchPassword) },
    { label: "One lowercase", valid: /[a-z]/.test(watchPassword) },
    { label: "One number", valid: /\d/.test(watchPassword) },
    { label: "One special character", valid: /[@$!%*?&_\-#^~`+=]/.test(watchPassword) },
  ];

  const onSubmit = async (data: RegisterFormData) => {
    setIsLoading(true);
    setServerError(null);
    try {
      // 1. Create the user
      await authApi.register({
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        target_language: data.target_language,
        native_language: data.native_language,
      });

      // 2. Automatically log them in to provision tokens
      const loginResp = await authApi.login({
        email: data.email,
        password: data.password,
      });

      setTokens(loginResp.access_token, loginResp.refresh_token);
      router.push("/dashboard");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setServerError(err.message); // E.g., "A user with this email address already exists."
      } else {
        setServerError("An unexpected network error occurred.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.heading}>
        <span className={styles.eyebrow}>A few details to get started</span>
        <h2>Create an account</h2>
        <p>Join today and start mastering a new language.</p>
      </div>

      {serverError && (
        <div className={styles.serverError} role="alert">
          <AlertCircle size={18} />
          <p>{serverError}</p>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className={styles.form}>
        <div className={styles.field}>
          <label htmlFor="full_name">Full name</label>
          <input
            {...register("full_name")}
            id="full_name"
            disabled={isLoading}
            autoComplete="name"
            aria-invalid={Boolean(errors.full_name)}
            placeholder="Jane Doe"
          />
          {errors.full_name && <p className={styles.fieldError}>{errors.full_name.message}</p>}
        </div>

        <div className={styles.field}>
          <label htmlFor="email">Email address</label>
          <input
            {...register("email")}
            id="email"
            type="email"
            disabled={isLoading}
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
            placeholder="you@example.com"
          />
          {errors.email && <p className={styles.fieldError}>{errors.email.message}</p>}
        </div>

        <div className={styles.languageFields}>
          <div className={styles.field}>
            <label htmlFor="native_language">Native language</label>
            <select
              {...register("native_language")}
              id="native_language"
              disabled={isLoading}
            >
              {PRESET_LANGUAGES.map(lang => <option key={`nat-${lang}`} value={lang}>{lang}</option>)}
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor="target_language">Target language</label>
            <select
              {...register("target_language")}
              id="target_language"
              disabled={isLoading}
            >
              {PRESET_LANGUAGES.map(lang => <option key={`tgt-${lang}`} value={lang}>{lang}</option>)}
            </select>
          </div>
        </div>

        <div className={styles.field}>
          <label htmlFor="password">Password</label>
          <input
            {...register("password")}
            id="password"
            type="password"
            disabled={isLoading}
            autoComplete="new-password"
            aria-invalid={Boolean(errors.password)}
            placeholder="••••••••"
          />

          <div className={styles.passwordChecks}>
            {passwordChecks.map((check) => (
              <div key={check.label} className={check.valid ? styles.validCheck : styles.invalidCheck}>
                {check.valid ? <Check size={14} /> : <X size={14} />}
                <span>{check.label}</span>
              </div>
            ))}
          </div>
          {errors.password && <p className={styles.fieldError}>{errors.password.message}</p>}
        </div>

        <div className={styles.field}>
          <label htmlFor="confirmPassword">Confirm password</label>
          <input
            {...register("confirmPassword")}
            id="confirmPassword"
            type="password"
            disabled={isLoading}
            autoComplete="new-password"
            aria-invalid={Boolean(errors.confirmPassword)}
            placeholder="••••••••"
          />
          {errors.confirmPassword && <p className={styles.fieldError}>{errors.confirmPassword.message}</p>}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className={styles.submit}
        >
          {isLoading ? <Loader2 size={18} className={styles.spinner} /> : "Create account"}
        </button>
      </form>

      <p className={styles.footer}>
        Already have an account?{" "}
        <Link href="/login">
          Sign in
        </Link>
      </p>
    </div>
  );
}