import { request } from "./api";
import type { Schedule, Run, Notification } from "./api";
import type { Action, Signal, Connection } from "./assistantApi";
import { createReadResource } from "./readResource";
export const todayReads = {
  results: createReadResource((signal) =>
    request<{ items: Notification[] }>(
      "/notifications",
      "GET",
      undefined,
      undefined,
      { signal },
    ),
  ),
  schedules: createReadResource((signal) =>
    request<{ items: Schedule[] }>(
      "/automations",
      "GET",
      undefined,
      undefined,
      { signal },
    ),
  ),
  runs: createReadResource((signal) =>
    request<{ items: Run[] }>("/tasks", "GET", undefined, undefined, {
      signal,
    }),
  ),
  actions: createReadResource((signal) =>
    request<{ items: Action[] }>("/actions", "GET", undefined, undefined, {
      signal,
    }),
  ),
  signals: createReadResource((signal) =>
    request<{ items: Signal[] }>("/signals", "GET", undefined, undefined, {
      signal,
    }),
  ),
  connections: createReadResource((signal) =>
    request<{ items: Connection[]; availability: string }>(
      "/connectors",
      "GET",
      undefined,
      undefined,
      { signal },
    ),
  ),
};
window.addEventListener("adex:session-changed", () =>
  Object.values(todayReads).forEach((resource) => resource.reset()),
);
