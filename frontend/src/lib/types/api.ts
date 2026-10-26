// --- Auth & User Schemas ---

export interface UserRegister {
  email: string;
  password: string;
  full_name: string;
  target_language: string;
  native_language: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface TokenRefreshRequest {
  refresh_token: string;
}

export interface UserRead {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  native_language: string;
  target_language: string;
  created_at: string;
}

export interface UserUpdate {
  full_name?: string | null;
  native_language?: string;
  target_language?: string;
  is_active?: boolean;
}

// --- Chat & SSE Streaming Schemas ---

export type SSEEvent = "token" | "grammar_correction" | "vocab_hint" | "error" | "done";

export interface AIStreamChunk {
  event: SSEEvent;
  delta: string;
  metadata?: Record<string, unknown> | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export interface ChatSession {
  id: string;
  target_language: string;
  cefr_level: string;
  created_at: string;
}