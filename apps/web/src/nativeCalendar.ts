import { registerPlugin } from "@capacitor/core";
import type { CalendarEvent } from "./calendarAgenda";
export type CalendarPermission = "GRANTED" | "NEEDS_PERMISSION" | "DENIED";
const calendar = registerPlugin<{
  request(): Promise<{ permission: CalendarPermission }>;
  read(): Promise<{
    permission: CalendarPermission;
    events: CalendarEvent[];
    partial: boolean;
  }>;
}>("AdexCalendar");
export const requestCalendarPermission = () => calendar.request();
export const readNativeCalendar = () => calendar.read();
