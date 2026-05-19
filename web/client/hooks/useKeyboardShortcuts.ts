// web/client/hooks/useKeyboardShortcuts.ts
//
// Global keyboard shortcuts for the Feed. Skips events when the user is
// typing in an input/textarea/contenteditable. Centralised here so the
// shortcut table is discoverable in one place.
//
// Shortcuts:
//   j           — focus / move to next card
//   k           — focus / move to previous card
//   Enter       — open drawer for the focused card
//   /           — focus the global search box in the header
//   Escape      — close the open drawer
//   ?           — toggle the shortcut help overlay
import { useEffect } from "react";

export interface ShortcutHandlers {
  onNext?: () => void;
  onPrev?: () => void;
  onOpen?: () => void;
  onFocusSearch?: () => void;
  onClose?: () => void;
  onToggleHelp?: () => void;
}

function isTypingTarget(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  const tag = t.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (t.isContentEditable) return true;
  return false;
}

export function useKeyboardShortcuts(h: ShortcutHandlers): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Always let Escape close the drawer, even from inputs.
      if (e.key === "Escape" && h.onClose) {
        h.onClose();
        return;
      }
      if (isTypingTarget(e.target)) return;
      // Ignore when modifier keys are held — operators expect platform
      // shortcuts (Cmd+R, Ctrl+L, etc) to work normally.
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      switch (e.key) {
        case "j":
          if (h.onNext) { e.preventDefault(); h.onNext(); }
          break;
        case "k":
          if (h.onPrev) { e.preventDefault(); h.onPrev(); }
          break;
        case "Enter":
          if (h.onOpen) { e.preventDefault(); h.onOpen(); }
          break;
        case "/":
          if (h.onFocusSearch) { e.preventDefault(); h.onFocusSearch(); }
          break;
        case "?":
          if (h.onToggleHelp) { e.preventDefault(); h.onToggleHelp(); }
          break;
        default:
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [h]);
}
