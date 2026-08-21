import { useEffect, useRef, useState } from "react";

/**
 * Reports once an element has entered the viewport, then stops observing.
 * Powers scroll-triggered section reveals and defers mounting the heavier
 * chart sections until they're about to be scrolled into view -- a cheap,
 * dependency-free stand-in for real code-splitting (see landing README note
 * in LandingPreviewPage.tsx for why full route-level splitting is out of
 * scope for this phase).
 */
export function useInView<T extends HTMLElement>(options?: IntersectionObserverInit) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: "120px 0px", threshold: 0.1, ...options },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [options]);

  return { ref, inView };
}
