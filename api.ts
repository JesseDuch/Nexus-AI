/** API client for the NexusAI console backend (same-origin FastAPI). */

const TOKEN_KEY = "nexusai_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    setToken(null);
    if (!path.startsWith("/api/auth")) window.location.href = "/auth";
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      (typeof data?.detail === "string" && data.detail) ||
      data?.detail?.error?.message ||
      data?.error?.message ||
      `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data as T;
}

// ---------- types ----------

export interface User {
  id: number;
  email: string;
  name: string;
  is_admin: boolean;
  created_at: string;
}

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  revoked: boolean;
  created_at: string;
  last_used_at: string | null;
  key?: string;
}

export interface Conversation {
  id: number;
  title: string;
  model: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessage {
  id?: number;
  role: "user" | "assistant" | "system";
  content: string;
}

export interface UsageSummary {
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  request_count: number;
  image_count: number;
  video_count: number;
  code_exec_count: number;
  routing: Record<string, number>;
  daily: { date: string; tokens: number; requests: number }[];
}

export interface MediaAsset {
  id: number;
  kind: string;
  prompt: string;
  url: string;
  created_at: string;
}

// ---------- auth ----------

export const api = {
  register: (email: string, password: string, name: string) =>
    request<{ token: string; user: User }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),
  login: (email: string, password: string) =>
    request<{ token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  profile: () => request<User>("/api/user/profile"),
  usage: () => request<UsageSummary>("/api/user/usage"),

  listKeys: () => request<ApiKey[]>("/api/keys"),
  createKey: (name: string) =>
    request<ApiKey>("/api/keys", { method: "POST", body: JSON.stringify({ name }) }),
  revokeKey: (id: number) => request<void>(`/api/keys/${id}`, { method: "DELETE" }),
  resetKey: (id: number) => request<ApiKey>(`/api/keys/${id}/reset`, { method: "POST" }),

  listConversations: () => request<Conversation[]>("/api/conversations"),
  getConversation: (id: number) =>
    request<Conversation & { messages: (ChatMessage & { id: number })[] }>(`/api/conversations/${id}`),
  deleteConversation: (id: number) => request<void>(`/api/conversations/${id}`, { method: "DELETE" }),

  listMedia: () => request<MediaAsset[]>("/api/media"),
  deleteMedia: (id: number) => request<void>(`/api/media/${id}`, { method: "DELETE" }),

  sendFeedback: (rating: number, conversationId?: number | null, comment?: string) =>
    request<{ id: number; rating: number }>("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ rating, conversation_id: conversationId ?? null, comment: comment ?? "" }),
    }),

  adminStats: () => request<AdminStats>("/api/admin/stats"),
  adminUsers: () => request<AdminUser[]>("/api/admin/users"),
  adminKeys: () => request<AdminKey[]>("/api/admin/keys"),
  adminAudit: (limit = 100) => request<AuditRow[]>(`/api/admin/audit?limit=${limit}`),
};

export interface AdminStats {
  users: number;
  api_keys: number;
  requests_total: number;
  tokens_total: number;
  media_total: number;
  routing_logs: number;
  audit_logs: number;
}

export interface AdminUser {
  id: number;
  email: string;
  name: string;
  is_admin: boolean;
  created_at: string;
  api_keys: number;
  tokens: number;
}

export interface AdminKey {
  id: number;
  owner: string;
  name: string;
  prefix: string;
  revoked: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface AuditRow {
  id: number;
  request_id: string;
  user_id: number | null;
  method: string;
  path: string;
  status_code: number;
  latency_ms: number;
  ip: string;
  created_at: string;
}

// ---------- streaming chat ----------

export interface RoutingInfo {
  action: string;
  policy: string;
  reason: string;
  self_reflect?: boolean;
}

export interface StreamCallbacks {
  onMeta?: (conversationId: number) => void;
  onRouting?: (routing: RoutingInfo) => void;
  onStatus?: (status: string) => void;
  onToken?: (text: string) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

/** Streams /api/chat via SSE and dispatches token deltas. */
export async function streamConsoleChat(
  body: {
    conversation_id?: number | null;
    message: string;
    model?: string;
    enable_image?: boolean;
    enable_video?: boolean;
    enable_code_execution?: boolean;
  },
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken();
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ ...body, stream: true }),
    signal,
  });
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data?.detail || data?.error?.message || `Chat request failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const evt of events) {
      const line = evt.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") {
        cb.onDone?.();
        continue;
      }
      try {
        const json = JSON.parse(payload);
        if (json.meta?.conversation_id) cb.onMeta?.(json.meta.conversation_id);
        else if (json.meta?.routing) cb.onRouting?.(json.meta.routing);
        else if (json.meta?.status) cb.onStatus?.(json.meta.status);
        else if (json.error) cb.onError?.(json.error.message || "Upstream error");
        else {
          const delta = json.choices?.[0]?.delta?.content;
          if (delta) cb.onToken?.(delta);
        }
      } catch {
        /* ignore keep-alives */
      }
    }
  }
  cb.onDone?.();
}
