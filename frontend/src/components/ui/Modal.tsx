import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  /** Closing via a backdrop click; on for confirmations/info, off for anything with unsaved input. */
  closeOnBackdropClick?: boolean;
}

/**
 * Accessible dialog: traps Tab focus inside while open, restores focus to
 * the trigger on close, closes on Escape, locks body scroll, and is
 * portaled to document.body so it always sits above page content
 * regardless of where it's mounted.
 */
export function Modal({ open, onClose, title, description, children, closeOnBackdropClick = true }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descId = useId();

  useEffect(() => {
    if (!open) return;

    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const node = dialogRef.current;
    const focusable = node?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    (focusable && focusable.length > 0 ? focusable[0] : node)?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !node) return;
      const items = node.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("keydown", handleKeyDown, true);
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="bsr-modal-backdrop"
      onMouseDown={(event) => {
        if (closeOnBackdropClick && event.target === event.currentTarget) onClose();
      }}
    >
      <div ref={dialogRef} className="bsr-modal" role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description ? descId : undefined} tabIndex={-1}>
        <div className="bsr-modal__header">
          <h2 id={titleId} className="bsr-h4">
            {title}
          </h2>
          <button type="button" className="bsr-icon-btn bsr-icon-btn--ghost bsr-icon-btn--sm" onClick={onClose} aria-label="Close dialog">
            <span className="bsr-icon-btn__glyph" aria-hidden="true">
              ✕
            </span>
          </button>
        </div>
        {description && (
          <p id={descId} className="bsr-sm bsr-modal__description">
            {description}
          </p>
        )}
        <div className="bsr-modal__body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
