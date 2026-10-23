const ACCESS_TOKEN_KEY = "ai_tutor_access_token";
const REFRESH_TOKEN_KEY = "ai_tutor_refresh_token";

/**
 * Retrieves the access token, guarding against SSR environments.
 */
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

/**
 * Retrieves the refresh token, guarding against SSR environments.
 */
export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

/**
 * Persists both tokens to client storage.
 */
export function setTokens(access_token: string, refresh_token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_TOKEN_KEY, access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh_token);
}

/**
 * Clears all authentication tokens (used during logout or security failures).
 */
export function removeTokens(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/**
 * Decodes the JWT payload to check the `exp` claim.
 * Includes a 15-second buffer to prevent edge-case expirations during network transit.
 */
export function isTokenExpired(token: string): boolean {
  if (!token) return true;

  try {
    const payloadBase64Url = token.split(".")[1];
    if (!payloadBase64Url) return true;

    // Normalize Base64 URL format
    const base64 = payloadBase64Url.replace(/-/g, "+").replace(/_/g, "/");
    
    // Safely decode Base64 ensuring UTF-8 characters don't break `atob`
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );

    const payload = JSON.parse(jsonPayload);
    if (!payload.exp) return true;

    // JWT exp is in seconds; Date.now() is in milliseconds
    const expirationTimeMs = payload.exp * 1000;
    const bufferMs = 15 * 1000; 

    return Date.now() + bufferMs >= expirationTimeMs;
  } catch (error) {
    // Treat malformed tokens as expired/invalid
    return true;
  }
}