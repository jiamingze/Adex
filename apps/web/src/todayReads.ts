import { native } from "./platform";
import { request } from "./api";
import type { Schedule, Run, Notification } from "./api";
import type { Action, Signal, Connection } from "./assistantApi";
import { createReadResource } from "./readResource";
// A cold mobile TLS connection must not mark every section failed after 8 seconds.
const overviewRead = <T>(read: (signal: AbortSignal) => Promise<T>) =>
  createReadResource(read, { timeoutMs: native ? 20000 : 8000 });
export const todayReads = {
  results: overviewRead((signal) =>
    request<{ items: Notification[] }>(
      "/notifications",
      "GET",
      undefined,
      undefined,
      { signal },
    ),
  ),
  schedules: overviewRead((signal) =>
    request<{ items: Schedule[] }>(
      "/automations",
      "GET",
      undefined,
      undefined,
      { signal },
    ),
  ),
  runs: overviewRead((signal) =>
    request<{ items: Run[] }>("/tasks", "GET", undefined, undefined, {
      signal,
    }),
  ),
  actions: overviewRead((signal) =>
    request<{ items: Action[] }>("/actions", "GET", undefined, undefined, {
      signal,
    }),
  ),
  signals: overviewRead((signal) =>
    request<{ items: Signal[] }>("/signals", "GET", undefined, undefined, {
      signal,
    }),
  ),
  connections: overviewRead((signal) =>
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

window.addEventListener("adex:signals-changed", () =>
  todayReads.signals.invalidate(true),
);
