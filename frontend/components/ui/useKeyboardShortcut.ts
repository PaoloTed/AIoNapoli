/**
 * @purpose Hook tastiera per scorciatoie deterministiche (es. Ctrl+K chat)
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useEffect } from "react";

export function useKeyboardShortcut(
  keys: { key: string; ctrlOrMeta?: boolean; shift?: boolean },
  handler: () => void,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled) return;

    const listener = (event: KeyboardEvent) => {
      const modifier = keys.ctrlOrMeta ? event.ctrlKey || event.metaKey : true;
      const shift = keys.shift ? event.shiftKey : true;
      if (event.key.toLowerCase() === keys.key.toLowerCase() && modifier && shift) {
        event.preventDefault();
        handler();
      }
    };

    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, [keys.key, keys.ctrlOrMeta, keys.shift, handler, enabled]);
}
