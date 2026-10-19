import { native } from "./platform";
import { calendarResource } from "./calendarResource";
import { upcomingAgenda } from "./calendarAgenda";
export type ClientCalendar = {
  source: "device";
  observed_at: string;
  timezone: string;
  partial: boolean;
  events: {
    title: string;
    start: string;
    end: string;
    all_day: boolean;
    location: string;
    organizer: string;
  }[];
};
/** A relevant user request uses only previously granted OS access; never requests permission here. */
export async function chatCalendar(
  content: string,
): Promise<ClientCalendar | undefined> {
  if (
    !native ||
    !/日历|日程|会议|安排|今天.*做|明天.*做|优先.*事/.test(content)
  )
    return;
  try {
    const value = await calendarResource.load(true);
    if (!value.connected) return;
    const now = new Date(),
      start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const end = new Date(start);
    end.setDate(end.getDate() + 7);
    const agenda = upcomingAgenda(value.events, start, end);
    return {
      source: "device",
      observed_at: now.toISOString(),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      partial: value.partial || agenda.invalid > 0 || agenda.items.length > 40,
      events: agenda.items.slice(0, 40).map((e) => ({
        title: e.title.slice(0, 200),
        start: new Date(e.start).toISOString(),
        end: new Date(e.end).toISOString(),
        all_day: e.allDay,
        location: (e.location ?? "").slice(0, 300),
        organizer: (e.organizer ?? "").slice(0, 200),
      })),
    };
  } catch {
    return;
  } // Unknown calendar must not block sending the user's message.
}
