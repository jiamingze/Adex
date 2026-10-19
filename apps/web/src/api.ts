import { nativeJsonRead } from "./nativeJsonRead";
import { uploadDeadline } from "./uploadTimeout";
import { saveSession, clearSession, loadSession, native } from "./platform";
import { CapacitorHttp } from "@capacitor/core";
import type { components } from "../../../packages/contracts/core.generated";
export type Conversation = { id: string; title: string; created_at: string };
export type Message = {
  id: string;
  seq: number;
  role: "user" | "assistant";
  content: string;
  cards?: import("./Cards").Card[];
};
export type Memory = { id: string; content: string; revision: number };
export type Schedule = {
  task_request?: {notification_policy?: string; notification_condition?: components["schemas"]["NotificationCondition"]};
  id: string;
  title: string;
  instruction: string;
  kind: string;
  status: string;
  timezone: string;
  next_fire_at: string | null;
  revision: number;
  origin_conversation_id: string;
};
export type Run = {
  schedule_id?: string | null;
  id: string;
  instruction: string;
  status: string;
  error_code: string | null;
  created_at: string;
  checkpoint_ref: string | null;
  origin_conversation_id: string;
};
export type Notification = {
  event_id?: string;
  run_id?: string | null;
  id: string;
  title: string;
  body: string;
  read: boolean;
  conversation_id: string;
  created_at: string;
};
export type Snapshot = {
  items: Message[];
  turns: { id: string; status: string; error_code: string | null }[];
  event_seq: number;
  partial?: string;
  progress?: string;
};
let token = "";
let sessionGeneration = 0;
function setToken(value: string) {
  if (value === token) return;
  token = value;
  sessionGeneration++;
  window.dispatchEvent(new Event("adex:session-changed"));
}
const apiBase = import.meta.env.VITE_ADEX_API_BASE || "";
if (apiBase && !apiBase.startsWith("https://"))
  throw new Error("Native API endpoint must use HTTPS");
export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
  ) {
    super(code);
  }
}
export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
  key?: string,
  options?: { signal?: AbortSignal },
): Promise<T> {
  const requestSession = sessionGeneration;
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: "Bearer " + token } : {}),
    ...(key ? { "Idempotency-Key": key } : {}),
  };
  const r = native && method === "GET"
    ? await nativeJsonRead(apiBase + "/api/v1" + path, headers, options?.signal, CapacitorHttp)
    : await fetch(apiBase + "/api/v1" + path, {
    method,
    signal: options?.signal,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...(key ? { "Idempotency-Key": key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let code = "REQUEST_FAILED";
    try {
      code = (await r.json()).code || code;
    } catch {}
    if (r.status === 401 && requestSession === sessionGeneration) {
      setToken("");
      window.dispatchEvent(new Event("adex:unauthorized"));
    }
    throw new ApiError(code, r.status);
  }
  return r.json();
}
export const api = {
  capabilities: () =>
    request<{
      chat_model: string;
      music_provider: string;
      video_provider: string;
      music_model: string;
      music_max_seconds: number;
    }>("/capabilities"),
  restore: async () => {
    setToken(await loadSession());
    try {
      await request("/me");
      const r = await request<{
        token: string;
        username: string;
        is_guest: boolean;
      }>("/auth/guest", "POST");
      setToken(r.token);
      await saveSession(token);
      return r;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) return null;
      throw e;
    }
  },
  guest: async () => {
    const r = await request<{
      token: string;
      username: string;
      is_guest: boolean;
    }>("/auth/guest", "POST");
    setToken(r.token);
    await saveSession(token);
    return r;
  },
  register: async (input: { username: string; password: string }) => {
    const r = await request<{
      token: string;
      username: string;
      is_guest: boolean;
    }>("/auth/register", "POST", input);
    setToken(r.token);
    await saveSession(token);
    return r;
  },
  login: async (input: components["schemas"]["Login"]) => {
    const r = await request<{
      token: string;
      username: string;
      is_guest: boolean;
    }>("/auth/login", "POST", input);
    setToken(r.token);
    await saveSession(token);
    return r;
  },
  logout: async () => {
    try {
      const device = localStorage.getItem("adex.pushDevice");
      if (device) await request(`/push/devices/${device}`, "DELETE").catch(() => {});
      await request("/auth/logout", "POST");
    } finally {
      localStorage.removeItem("adex.pushDevice");
      setToken("");
      await clearSession();
    }
  },
  conversations: () => request<{ items: Conversation[] }>("/conversations"),
  createConversation: (title: string) =>
    request<Conversation>("/conversations", "POST", { title }),
  messages: (id: string, after = 0, latest = false) =>
    request<Snapshot>(
      `/conversations/${id}/messages?after_seq=${after}&limit=200&latest=${latest}`,
    ),
  send: (
    id: string,
    input: components["schemas"]["MessageInput"] & { file_ids?: string[] },
  ) =>
    request<{ message_id: string; status: string }>(
      `/conversations/${id}/messages`,
      "POST",
      input,
    ),
  memories: () => request<{ items: Memory[] }>("/memories"),
  remember: (content: string) =>
    request<Memory>("/memories", "POST", { content }),
  correctMemory: (id: string, content: string) =>
    request<Memory>(`/memories/${id}`, "PATCH", { content }),
  forget: (id: string) => request(`/memories/${id}`, "DELETE"),
  scheduleDraft: (body: components["schemas"]["ScheduleDraftInput"]) =>
    request<
      Partial<components["schemas"]["ScheduleInput"]> & {
        clarification?: string;
      }
    >("/automations/draft", "POST", body),
  schedules: () => request<{ items: Schedule[] }>("/automations"),
  createSchedule: (body: components["schemas"]["ScheduleInput"], key: string) =>
    request<Schedule>("/automations", "POST", body, key),
  deleteSchedule: (s: Schedule) => request<{ok:boolean;id:string}>(`/automations/${s.id}?revision=${s.revision}`, "DELETE"),
  updateSchedule: (s: Schedule, status: string) =>
    request<Schedule>(`/automations/${s.id}`, "PATCH", {
      status,
      revision: s.revision,
    }),
  runs: (signal?:AbortSignal) => request<{ items: Run[] }>("/tasks", "GET", undefined, undefined, {signal}),
  cancelRun: (id: string) => request(`/tasks/${id}/cancel`, "POST"),
  notifications: () => request<{ items: Notification[] }>("/notifications"),
  readNotification: (id: string) =>
    request(`/notifications/${id}/read`, "POST"),
  stream: async (
    id: string,
    after: number,
    signal: AbortSignal,
    onEvent: (type: string, data: Record<string, unknown>, seq: number) => void,
  ) => {
    const webFetch =
      (window as unknown as { CapacitorWebFetch?: typeof fetch })
        .CapacitorWebFetch || fetch;
    const r = await webFetch(
      `${apiBase}/api/v1/conversations/${id}/events?after_seq=${after}`,
      {
        credentials: "include",
        headers: token ? { Authorization: "Bearer " + token } : {},
        signal,
      },
    );
    if (!r.ok) throw new ApiError("STREAM_UNAVAILABLE", r.status);
    const reader = r.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let end;
        while ((end = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, end).replace(/\r/g, "");
          buffer = buffer.slice(end + 2);
          let type = "",
            data = "",
            seq = after;
          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) type = line.slice(6).trim();
            if (line.startsWith("id:")) seq = Number(line.slice(3));
            if (line.startsWith("data:")) data += line.slice(5).trim();
          }
          if (type && data) {
            onEvent(type, JSON.parse(data), seq);
            after = seq;
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};
export type StoredFile = {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
};
export type Artifact = {
  id: string;
  title: string;
  kind: string;
  revision: number;
};
export type ArtifactVersion = {
  id: string;
  revision: number;
  file_id: string | null;
  source: {
    content?: string;
    media?: { mock?: boolean; model_id?: string };
    [key: string]: unknown;
  };
};
export const workspaceApi = {
  files: () => request<{ items: StoredFile[] }>("/files"),
  upload: async (file: File, key: string) =>
    uploadDeadline(
      (async () => {
        if (!file.size || file.size > 25 * 1024 * 1024)
          throw new ApiError("FILE_SIZE_LIMIT", 413);
        const headers = {
          ...(token ? { Authorization: "Bearer " + token } : {}),
          "Idempotency-Key": key,
        };
        if (native) {
          const encoded = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1]);
            reader.onerror = () => reject(new Error("图片读取失败"));
            reader.readAsDataURL(file);
          });
          const r = await CapacitorHttp.request({
            url: apiBase + "/api/v1/files",
            method: "POST",
            headers: {
              ...headers,
              "Content-Type": "multipart/form-data; boundary=Adex" + key,
            },
            dataType: "formData",
            connectTimeout: 10000,
            readTimeout: 30000,
            responseType: "json",
            data: [
              {
                key: "file",
                value: encoded,
                type: "base64File",
                contentType: file.type || "application/octet-stream",
                fileName: file.name,
              },
            ],
          });
          if (r.status >= 400)
            throw new ApiError(r.data?.code || "UPLOAD_FAILED", r.status);
          return r.data as StoredFile;
        }
        const body = new FormData();
        body.append("file", file);
        const r = await fetch(apiBase + "/api/v1/files", {
          method: "POST",
          credentials: "include",
          headers,
          body,
        });
        if (!r.ok)
          throw new ApiError(
            (await r.json()).code || "UPLOAD_FAILED",
            r.status,
          );
        return r.json() as Promise<StoredFile>;
      })(),
    ),
  playback: async (id: string) => {
    const r = await request<{ url: string }>(`/files/${id}/playback`, "POST");
    return apiBase + r.url;
  },
  blob: async (id: string) => {
    const r = await fetch(`${apiBase}/api/v1/files/${id}/content`, {
      credentials: "include",
      headers: token ? { Authorization: "Bearer " + token } : {},
    });
    if (!r.ok) throw new ApiError("DOWNLOAD_FAILED", r.status);
    return r.blob();
  },
  removeFile: (id: string) => request(`/files/${id}`, "DELETE"),
  registerExport: (
    id: string,
    version_id: string,
    file_id: string,
    format: string,
  ) =>
    request(`/artifacts/${id}/exports`, "POST", {
      version_id,
      file_id,
      format,
    }),
  removeArtifact: (id: string) => request(`/artifacts/${id}`, "DELETE"),
  preview: (id: string) =>
    request<{ url: string }>(`/artifacts/${id}/preview`, "POST").then(
      (r) => apiBase + r.url,
    ),
  share: (id: string) =>
    request<{ url: string }>(`/artifacts/${id}/share`, "POST").then(
      (r) => apiBase + r.url,
    ),
  revokeShare: (id: string) => request(`/artifacts/${id}/share`, "DELETE"),
  artifacts: () => request<{ items: Artifact[] }>("/artifacts"),
  versions: (id: string) =>
    request<{ items: ArtifactVersion[] }>(`/artifacts/${id}/versions`),
  save: (
    id: string,
    revision: number,
    source: object,
    file_id: string | null,
  ) =>
    request(`/artifacts/${id}/versions`, "POST", {
      expected_revision: revision,
      source,
      file_id,
    }),
  task: (body: object, key: string) =>
    request<Run>("/tasks", "POST", body, key),
};
export type MusicTrack = {
  provider: string;
  track_id: string;
  title: string;
  artists: string[];
  source_url: string;
  availability: string;
  album?: string;
  duration_ms?: number;
  artwork_url?: string;
};
export type Approval = {
  id: string;
  state: string;
  expires_at: string;
  request: { title: string; start: string; end: string };
};
export const toolsApi = {
  music: (query: string) =>
    request<{ items: MusicTrack[] }>("/music/search", "POST", { query }),
  approvals: () => request<{ items: Approval[] }>("/approvals"),
  approval: (body: object) => request<Approval>("/approvals", "POST", body),
  act: (id: string, action: string) =>
    request(`/approvals/${id}/${action}`, "POST"),
};
export const accountApi = {
  search: (q: string) =>
    request<{
      items: {
        id: string;
        conversation_id: string;
        content: string;
        title: string;
      }[];
    }>(`/search?q=${encodeURIComponent(q)}`),
  settings: () =>
    request<{
      settings: {
        memory_enabled: boolean;
        email_notifications: boolean;
        email?: string;
      };
    }>("/settings"),
  save: (settings: object) => request("/settings", "PATCH", settings),
  usage: () =>
    request<{
      model: unknown;
      storage: { used_bytes: number; quota_bytes: number };
    }>("/usage"),
  revoke: () => request("/security/revoke-sessions", "POST"),
  rename: (id: string, title: string) =>
    request(`/conversations/${id}`, "PATCH", { title }),
  remove: (id: string) => request(`/conversations/${id}`, "DELETE"),
  stop: (id: string) => request(`/conversations/${id}/stop`, "POST"),
  monitors: () =>
    request<{
      items: { id: string; query: string; keyword: string; active: boolean }[];
    }>("/monitors"),
  monitor: (body: object) => request("/monitors", "POST", body),
  cancelMonitor: (id: string) => request(`/monitors/${id}`, "DELETE"),
};
