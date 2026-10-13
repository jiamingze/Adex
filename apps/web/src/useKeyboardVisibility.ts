import { useEffect, useState } from "react";

/** Native keyboard events are authoritative; mobile Web uses viewport shrinkage. */
export function useKeyboardVisibility() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const viewport = window.visualViewport;
    const native = document.documentElement.classList.contains("native-app");
    let fullHeight = window.innerHeight;
    const show = () => setVisible(true);
    const hide = () => setVisible(false);
    const check = () => {
      if (native) return;
      fullHeight = Math.max(fullHeight, window.innerHeight);
      const editable = document.activeElement?.matches(
        "input, textarea, [contenteditable=true]",
      );
      setVisible(
        !!editable && !!viewport && fullHeight - viewport.height > 150,
      );
    };
    const rotate = () => {
      fullHeight = window.innerHeight;
      check();
    };
    if (native)
      setVisible(document.documentElement.classList.contains("keyboard-open"));
    window.addEventListener("keyboardWillShow", show);
    window.addEventListener("keyboardWillHide", hide);
    window.addEventListener("orientationchange", rotate);
    viewport?.addEventListener("resize", check);
    document.addEventListener("focusin", check);
    document.addEventListener("focusout", check);
    return () => {
      window.removeEventListener("keyboardWillShow", show);
      window.removeEventListener("keyboardWillHide", hide);
      window.removeEventListener("orientationchange", rotate);
      viewport?.removeEventListener("resize", check);
      document.removeEventListener("focusin", check);
      document.removeEventListener("focusout", check);
    };
  }, []);
  return visible;
}
