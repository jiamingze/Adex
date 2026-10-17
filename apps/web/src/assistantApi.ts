import { request } from "./api";
import { matrixResource } from "./matrixResource";
export type Connection = {
  id: string;
  service: "calendar" | "gmail";
  status: string;
  scopes: string[];
};
export type Action = {
  id: string;
  kind: string;
  connection_id: string;
  state: string;
  request_hash: string;
  expires_at: string;
  request: {
    origin_conversation_id: string;
    payload: Record<string, unknown>;
    before?: Record<string, unknown>;
    summary?: {kind:string;page_url:string;fields:{label:string;value:string}[];facts:string[]};
  };
  result?: Record<string, unknown>;
};
export type Signal = {
  id: string;
  kind: string;
  importance: number;
  suggestion: string;
  reasons: string[];
  correlation_key: string;
  conversation_id: string;
  run_id: string;
  evidence: Record<string, unknown>;
};
export type MatrixTask = {
  id: string;
  title: string;
  important: boolean;
  urgent: boolean;
  status: "TODO" | "DONE";
  revision: number;
  due_at: string | null;
  run_id: string | null;
  conversation_id: string | null;
  quadrant?: string;
};
export type NotificationPreferences = {
  enabled: boolean;
  push_enabled: boolean;
  min_importance: number;
  quiet_start: string | null;
  quiet_end: string | null;
  timezone: string;
};
export const assistantApi = {
  connections: () =>
    request<{ items: Connection[]; availability: string }>("/connectors"),
  authorize: (service: string, access: string) =>
    request<{ authorization_url: string; requested_scopes: string[] }>(
      "/connectors/google/authorize",
      "POST",
      { service, access },
    ),
  revokeConnection: (id: string) =>
    request<{ status: string }>(`/connectors/${id}/revoke`, "POST", {}),
  query: (id: string, query: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/connectors/${id}/query`, "POST", query),
  sync: (id: string, conversation: string, query: Record<string, unknown>) =>
    request<{ id: string }>(`/connectors/${id}/sync`, "POST", {
      origin_conversation_id: conversation,
      query,
      idempotency_key: crypto.randomUUID(),
    }),
  watch: (id: string, conversation: string) =>
    request<{ id: string }>(`/connectors/${id}/watch`, "POST", {
      origin_conversation_id: conversation,
      idempotency_key: crypto.randomUUID(),
    }),
  actions: () => request<{ items: Action[] }>("/actions"),
  draft: (body: Record<string, unknown>) =>
    request<Action>("/actions", "POST", body),
  decide: (action: Action, decision: string) =>
    request<Record<string, unknown>>(
      `/actions/${action.id}/${decision}`,
      "POST",
      { request_hash: action.request_hash },
    ),
  signals: () => request<{ items: Signal[] }>("/signals"),
  preferences: () =>
    request<NotificationPreferences>("/notification-preferences"),
  savePreferences: (body: NotificationPreferences) =>
    request<NotificationPreferences>("/notification-preferences", "PUT", body),
  tasks: () => request<{ items: MatrixTask[] }>("/matrix"),
  saveTask: (
    body: Omit<MatrixTask, "id" | "revision"> & {
      id?: string;
      revision?: number;
    },
  ) =>
    request<MatrixTask>(
      body.id ? `/matrix/${body.id}` : "/matrix",
      body.id ? "PATCH" : "POST",
      {
        title: body.title,
        important: body.important,
        urgent: body.urgent,
        due_at: body.due_at,
        status: body.status,
        run_id: body.run_id,
        conversation_id: body.conversation_id,
        ...(body.revision ? { revision: body.revision } : {}),
      },
    ).then((task) => {
      matrixResource.invalidate(true);
      return task;
    }),
  deleteTask: (id: string) =>
    request(`/matrix/${id}`, "DELETE").then((result) => {
      matrixResource.invalidate(true);
      return result;
    }),
  registerPush: (token: string, environment: "sandbox" | "production") =>
    request<{ id: string; availability: string }>("/push/devices", "POST", {
      token,
      environment,
    }),
  revokePush: (id: string) => request(`/push/devices/${id}`, "DELETE"),
  resume: (id: string) =>
    request<{
      conversation_id: string;
      run?: { id: string; status: string };
      action_id: string | null;
    }>(`/notifications/${id}/resume`),
};
