import { native } from "./platform";
import { readNativeCalendar } from "./nativeCalendar";
import { request } from "./api";
import type { Connection } from "./assistantApi";
import type { CalendarEvent } from "./calendarAgenda";
import { createReadResource } from "./readResource";

/** Read-only, session-local projection; no calendar data is persisted on the device. */
export const calendarResource = createReadResource(
  async (signal) => {
    if (native) {
      const result = await readNativeCalendar();
      return {
        events: result.events,
        connected: result.permission === "GRANTED",
        partial: result.partial,
        blocked: false,
        permission: result.permission,
      };
    }
    const connections = await request<{
      items: Connection[];
      availability: string;
    }>("/connectors", "GET", undefined, undefined, { signal });
    const connection = connections.items.find(
      (c) => c.service === "calendar" && c.status === "ACTIVE",
    );
    if (!connection)
      return {
        events: [] as CalendarEvent[],
        connected: false,
        partial: false,
        blocked: connections.availability === "BLOCKED_EXTERNAL",
        permission: undefined,
      };
    const now = new Date();
    const result = await request<{
      events: CalendarEvent[];
      partial?: boolean;
      warnings?: unknown[];
    }>(
      `/connectors/${connection.id}/query`,
      "POST",
      {
        start: now.toISOString(),
        end: new Date(now.getTime() + 7 * 86400000).toISOString(),
      },
      undefined,
      { signal },
    );
    if (!Array.isArray(result.events))
      throw new Error("INVALID_CALENDAR_RESPONSE");
    return {
      events: result.events,
      connected: true,
      partial: !!result.partial || !!result.warnings?.length,
      blocked: false,
      permission: undefined,
    };
  },
  { freshMs: 30000 },
);
window.addEventListener("adex:session-changed", () => calendarResource.reset());
