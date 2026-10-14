import { useLayoutEffect, useRef } from "react";
const positions = new Map<string, number>();
window.addEventListener("adex:session-changed", () => positions.clear());
/** Presentation-only session state; not browser history or durable user data. */
export function usePageScroll<T extends HTMLElement>(key: string) {
  const ref = useRef<T>(null);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    element.scrollTop = positions.get(key) ?? 0;
    const record = () => {
      positions.set(key, element.scrollTop);
    };
    element.addEventListener("scroll", record, { passive: true });
    return () => {
      element.removeEventListener("scroll", record);
    };
  }, [key]);
  return ref;
}
