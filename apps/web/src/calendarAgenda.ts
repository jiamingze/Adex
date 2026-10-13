/** Read-only agenda projection. Date-only calendar days stay nominal local dates. */
export type CalendarEvent = {
  id: string;
  summary?: string | null;
  status?: string | null;
  start?: { dateTime?: string; date?: string; timeZone?: string } | null;
  end?: { dateTime?: string; date?: string; timeZone?: string } | null;
};
export type AgendaItem = {
  id: string;
  title: string;
  start: number;
  end: number;
  allDay: boolean;
  date: string | null;
  ongoing: boolean;
};
function dayTimestamp(value?: string) {
  const match = value && /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return NaN;
  const date = new Date(+match[1], +match[2] - 1, +match[3]);
  return date.getFullYear() === +match[1] &&
    date.getMonth() === +match[2] - 1 &&
    date.getDate() === +match[3]
    ? date.getTime()
    : NaN;
}
function instant(value?: string) {
  return value && /(Z|[+-]\d{2}:\d{2})$/.test(value) ? Date.parse(value) : NaN;
}
export function upcomingAgenda(
  events: CalendarEvent[],
  now = new Date(),
  until = new Date(now.getTime() + 7 * 86400000),
) {
  let invalid = 0;
  const items: AgendaItem[] = [];
  for (const event of events) {
    if (event.status === "cancelled") continue;
    const allDay = !!event.start?.date && !!event.end?.date;
    const start = allDay
      ? dayTimestamp(event.start?.date)
      : instant(event.start?.dateTime);
    const end = allDay
      ? dayTimestamp(event.end?.date)
      : instant(event.end?.dateTime);
    if (
      !event.id ||
      !Number.isFinite(start) ||
      !Number.isFinite(end) ||
      end <= start
    ) {
      invalid++;
      continue;
    }
    if (end <= now.getTime() || start >= until.getTime()) continue;
    items.push({
      id: event.id,
      title: event.summary?.trim() || "未命名安排",
      start,
      end,
      allDay,
      date: allDay ? event.start!.date! : null,
      ongoing: !allDay && start <= now.getTime(),
    });
  }
  return { items: items.sort((a, b) => a.start - b.start), invalid };
}
export function agendaTime(item: AgendaItem) {
  if (item.allDay) return `${item.date} · 全天`;
  const date = new Date(item.start);
  return `${date.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}–${new Date(item.end).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}${item.ongoing ? " · 进行中" : ""}`;
}
