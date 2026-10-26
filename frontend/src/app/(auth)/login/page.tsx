// app/auth/login/page.tsx

"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, Loader2, AlertCircle } from "lucide-react";

import { loginSchema, type LoginFormData } from "@/lib/validations/auth";
import { authApi, ApiError } from "@/lib/api/client";
import { setTokens } from "@/lib/auth/tokenStorage";
import styles from "./page.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    setIsLoading(true);
    setServerError(null);
    try {
      const response = await authApi.login({
        email: data.email,
        password: data.password,
      });

      setTokens(response.access_token, response.refresh_token);
      router.push("/dashboard");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setServerError(err.message); // E.g., "Incorrect email or password"
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
        <span className={styles.eyebrow}>Your next conversation awaits</span>
        <h2>Welcome back</h2>
        <p>Sign in to continue your learning journey.</p>
      </div>

      {serverError && (
        <div className={styles.serverError} role="alert">
          <AlertCircle size={18} />
          <p>{serverError}</p>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className={styles.form}>
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

        <div className={styles.field}>
          <label htmlFor="password">Password</label>
          <div className={styles.passwordField}>
            <input
              {...register("password")}
              id="password"
              type={showPassword ? "text" : "password"}
              disabled={isLoading}
              autoComplete="current-password"
              aria-invalid={Boolean(errors.password)}
              placeholder="••••••••"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className={styles.passwordToggle}
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          {errors.password && <p className={styles.fieldError}>{errors.password.message}</p>}
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className={styles.submit}
        >
          {isLoading ? <Loader2 size={18} className={styles.spinner} /> : "Sign in"}
        </button>
      </form>

      <p className={styles.footer}>
        Don&apos;t have an account?{" "}
        <Link href="/register">
          Sign up
        </Link>
      </p>
    </div>
  );
}