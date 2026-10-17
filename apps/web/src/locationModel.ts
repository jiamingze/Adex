export type ClientLocation = { source: "device" | "manual"; label: string; latitude?: number; longitude?: number; observed_at: string };
export type LocationMode = "device" | "manual" | "off";
export const locationRelevant = (text: string) => /天气|下雨|气温|附近|周边|我这边|我这里|我在哪|当前位置/.test(text);
export function freshLocation(fix: ClientLocation, now = Date.now()) {
  const age = now - Date.parse(fix.observed_at);
  return Number.isFinite(age) && age >= -60000 && age <= 300000 &&
    (fix.source === "manual" ? !!fix.label.trim() :
      typeof fix.latitude === "number" && Number.isFinite(fix.latitude) && Math.abs(fix.latitude) <= 90 &&
      typeof fix.longitude === "number" && Number.isFinite(fix.longitude) && Math.abs(fix.longitude) <= 180);
}
