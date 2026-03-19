import type { TokenResponse, UserResponse } from "../types";

const BASE = "";

export async function register(
  username: string,
  password: string,
  displayName?: string,
): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password, display_name: displayName || null }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(body.detail || "Registration failed");
  }
  return res.json();
}

export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(body.detail || "Invalid username or password");
  }
  return res.json();
}

export async function refreshToken(): Promise<TokenResponse | null> {
  try {
    const res = await fetch(`${BASE}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function getMe(token: string): Promise<UserResponse> {
  const res = await fetch(`${BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}
