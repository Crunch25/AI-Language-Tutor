// lib/api/client.ts

import { getAccessToken, getRefreshToken, setTokens, removeTokens } from "@/lib/auth/tokenStorage";
import type { 
  UserLogin, 
  UserRegister, 
  TokenResponse, 
  TokenRefreshRequest, 
  UserRead, 
  UserUpdate 
} from "@/lib/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

/**
 * Custom typed error class extracting FastAPI's standard error details.
 */
export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export interface ChatSessionRead {
  id: string;
  target_language: string;
  created_at: string;
}

export interface ChatMessageRead {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  audio_metadata?: Record<string, unknown> | null;
}

export const chatApi = {
  async getSessions(): Promise<ChatSessionRead[]> {
    return apiFetch<ChatSessionRead[]>("/sessions", { method: "GET" });
  },
  async getMessages(sessionId: string): Promise<ChatMessageRead[]> {
    return apiFetch<ChatMessageRead[]>(`/sessions/${sessionId}/messages`, {
      method: "GET",
    });
  },
  async deleteSession(sessionId: string): Promise<void> {
    await apiFetch<void>(`/sessions/${sessionId}`, { method: "DELETE" });
  },
  async createSession(targetLanguage: string = "Spanish"): Promise<ChatSessionRead> {
    return apiFetch<ChatSessionRead>("/sessions", {
      method: "POST",
      body: JSON.stringify({ target_language: targetLanguage }),
    });
  },
};

// Concurrency lock variables to prevent multiple simultaneous refresh token requests
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
}

/**
 * Core centralized fetch wrapper with 401 interception, token rotation, and queue locking.
 */
export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();

  const headers = new Headers(options.headers || {});
  
  // Set Content-Type to JSON if not uploading FormData
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // Attach Authorization header if access token exists
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const config: RequestInit = {
    ...options,
    headers,
  };

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  let response = await fetch(url, config);

  // Handle 401 Unauthorized via Token Rotation
  if (response.status === 401 && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/refresh")) {
    const refreshTokenStr = getRefreshToken();

    if (!refreshTokenStr) {
      removeTokens();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new ApiError(401, "Session expired. Please log in again.");
    }

    if (isRefreshing) {
      // If a refresh is already in progress, queue this request until refresh completes
      return new Promise<T>((resolve, reject) => {
        failedQueue.push({
          resolve: (newToken: string) => {
            const retryHeaders = new Headers(options.headers || {});
            retryHeaders.set("Authorization", `Bearer ${newToken}`);
            if (!(options.body instanceof FormData) && !retryHeaders.has("Content-Type")) {
              retryHeaders.set("Content-Type", "application/json");
            }
            apiFetch<T>(endpoint, { ...options, headers: retryHeaders }).then(resolve).catch(reject);
          },
          reject,
        });
      });
    }

    isRefreshing = true;

    try {
      const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshTokenStr } as TokenRefreshRequest),
      });

      if (!refreshResponse.ok) {
        // Refresh failed (token compromised or revoked) -> Clear tokens and redirect
        removeTokens();
        processQueue(new Error("Token refresh failed"), null);
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        throw new ApiError(refreshResponse.status, "Authentication session expired.");
      }

      const tokenData: TokenResponse = await refreshResponse.json();
      setTokens(tokenData.access_token, tokenData.refresh_token);

      isRefreshing = false;
      processQueue(null, tokenData.access_token);

      // Retry original request with new access token
      const retryHeaders = new Headers(options.headers || {});
      retryHeaders.set("Authorization", `Bearer ${tokenData.access_token}`);
      if (!(options.body instanceof FormData) && !retryHeaders.has("Content-Type")) {
        retryHeaders.set("Content-Type", "application/json");
      }

      return apiFetch<T>(endpoint, { ...options, headers: retryHeaders });
    } catch (refreshError) {
      isRefreshing = false;
      removeTokens();
      processQueue(refreshError, null);
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw refreshError;
    }
  }

  // Handle standard error responses
  if (!response.ok) {
    let errorDetail = "An unexpected error occurred.";
    let errorData: unknown = null;
    const responseBody = await response.text();
    try {
      errorData = responseBody ? JSON.parse(responseBody) : null;
    } catch {
      errorData = responseBody;
      if (responseBody) errorDetail = responseBody;
    }
    if (errorData && typeof errorData === "object" && "detail" in errorData) {
      const detail = (errorData as { detail: unknown }).detail;
      if (typeof detail === "string") {
        errorDetail = detail;
      } else if (Array.isArray(detail)) {
        errorDetail = detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item
              ? String(item.msg)
              : JSON.stringify(item)
          )
          .join(", ");
      }
    }
    throw new ApiError(response.status, errorDetail, errorData);
  }

  // Handle 204 No Content responses cleanly
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// --- Dedicated Endpoint Functions ---

export const authApi = {
  async login(data: UserLogin): Promise<TokenResponse> {
    return apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async register(data: UserRegister): Promise<UserRead> {
    return apiFetch<UserRead>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async logout(): Promise<void> {
    const refresh_token = getRefreshToken();
    if (refresh_token) {
      try {
        await apiFetch<void>("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token } as TokenRefreshRequest),
        });
      } finally {
        removeTokens();
      }
    } else {
      removeTokens();
    }
  },
};

export const userApi = {
  async getMe(): Promise<UserRead> {
    return apiFetch<UserRead>("/users/me", {
      method: "GET",
    });
  },

  async updateMe(data: UserUpdate): Promise<UserRead> {
    return apiFetch<UserRead>("/users/me", {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
};