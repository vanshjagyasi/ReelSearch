import type {
  ReelListResponse,
  ReelDetail,
  ReelResponse,
  ReelStatus,
  SearchResponse,
  EntityResponse,
  EntityWithReels,
  RelatedEntity,
} from "../types";

const BASE = "";

// --- Token management ---

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// --- Core request helper ---

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  const res = await fetch(`${BASE}${url}`, { ...init, headers });

  // If 401, try refreshing the token once
  if (res.status === 401 && accessToken) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${accessToken}`;
      const retry = await fetch(`${BASE}${url}`, { ...init, headers });
      if (!retry.ok) {
        const body = await retry.text().catch(() => "");
        throw new Error(body || `${retry.status} ${retry.statusText}`);
      }
      if (retry.status === 204) return undefined as T;
      return retry.json() as Promise<T>;
    }
    // Refresh failed — redirect to login
    window.location.href = "/login";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return false;
    const data = await res.json();
    accessToken = data.access_token;
    return true;
  } catch {
    return false;
  }
}

// --- Reels ---

export function saveReel(url: string) {
  return request<ReelResponse>("/api/reels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export function listReels() {
  return request<ReelListResponse>("/api/reels");
}

export function getReel(id: string) {
  return request<ReelDetail>(`/api/reels/${id}`);
}

export function deleteReel(id: string) {
  return request<void>(`/api/reels/${id}`, { method: "DELETE" });
}

export function getReelStatus(id: string) {
  return request<ReelStatus>(`/api/reels/${id}/status`);
}

// --- Search ---

export function searchReels(query: string, limit = 20) {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });
}

// --- Entities ---

export function listEntities(type?: string, limit = 50) {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  params.set("limit", String(limit));
  return request<EntityResponse[]>(`/api/entities?${params}`);
}

export function getEntity(id: string) {
  return request<EntityWithReels>(`/api/entities/${id}`);
}

export function getRelatedEntities(id: string) {
  return request<RelatedEntity[]>(`/api/entities/${id}/related`);
}
