import type { Action } from "./assistantApi";
import { request } from "./api";
export type BrowserSession = {
  id: string;
  run_id: string;
  conversation_id: string;
  status: string;
  current_url: string;
  action_id: string | null;
  revision: number;
};
export type BrowserView = BrowserSession & {
  url?: string;
  dialog?: { id: string; type: string; message: string; url: string };
  tabs?: { id: string; url: string; active: boolean }[];
  run_status?: string;
  profile_revision?: number;
  observation_id?: string;
  login_form?: {
    origin: string;
    observation_id: string;
    fields: { id: string; label: string; secret: boolean; type: string }[];
    buttons: { id: string; label: string }[];
    notices: string[];
  } | null;
  progress_events?: { step: number; at: string; text: string }[];
  business_receipts?: Record<string, unknown>[];
  title?: string;
  screenshot?: string;
  nodes?: { id?: string; role: string; name: string; protected?: boolean }[];
  pending?: { preview: Record<string, unknown>; gesture: string };
  receipt?: Record<string, unknown>;
};
export type BrowserRun = {
  run_id: string;
  conversation_id: string;
  status: string;
  error_code?: string;
  session: BrowserView | null;
  action?: Action;
  result?: { artifact?: { receipts?: Record<string, unknown>[] } };
};
export const browserApi = {
  run: (id: string) => request<BrowserRun>(`/browser/runs/${id}`),
  accounts: () =>
    request<{ items: { id: string; host: string; expires_at: string }[] }>(
      "/browser/accounts",
    ),
  revokeAccount: (id: string) =>
    request(`/browser/accounts/${id}/revoke`, "POST", {}),
  list: () =>
    request<{ items: BrowserSession[]; availability: string }>(
      "/browser/sessions",
    ),
  view: (id: string) => request<BrowserView>(`/browser/sessions/${id}`),
  control: (id: string, body: Record<string, unknown>) =>
    request<BrowserView>(`/browser/sessions/${id}/control`, "POST", body),
  resume: (id: string) => request(`/browser/sessions/${id}/resume`, "POST", {}),
  close: (id: string) => request(`/browser/sessions/${id}/close`, "POST", {}),
  start: (
    conversation: string,
    url: string,
    instruction: string,
    key: string,
  ) =>
    request(
      "/tasks",
      "POST",
      {
        kind: "BROWSER",
        origin_conversation_id: conversation,
        browser_url: url,
        instruction,
      },
      key,
    ),
};
