import { useLayoutEffect, useRef, type RefObject } from "react";
import { createChatPositions } from "./chatScrollState";
const positions = createChatPositions();
window.addEventListener("adex:session-changed", () => positions.clear());
export function useChatScroll(
  id: string,
  visible: boolean,
  ready: boolean,
  follow: RefObject<boolean>,
) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!visible || !ready || !element) return;
    const saved = positions.get(id);
    follow.current = saved?.bottom ?? true;
    element.scrollTop = follow.current ? element.scrollHeight : saved!.top;
    // Late media/Markdown layout changes follow only while reading the latest.
    const resize = new ResizeObserver(() => {
      if (follow.current) element.scrollTop = element.scrollHeight;
    });
    if (element.firstElementChild) resize.observe(element.firstElementChild);
    return () => resize.disconnect();
  }, [id, visible, ready, follow]);
  const onScroll = () => {
    const element = ref.current;
    if (!visible || !ready || !element) return;
    positions.record(
      id,
      element.scrollTop,
      element.scrollHeight,
      element.clientHeight,
    );
    follow.current = positions.get(id)?.bottom ?? true;
  };
  return { ref, onScroll };
}
