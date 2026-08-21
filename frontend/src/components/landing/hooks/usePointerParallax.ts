import { useEffect, useRef, useState } from "react";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

/**
 * Subtle pointer-position offset for desktop hover parallax. Disabled
 * entirely on coarse/touch pointers and under prefers-reduced-motion --
 * returns a fixed {x:0, y:0} in both cases so callers don't need to branch.
 */
export function usePointerParallax<T extends HTMLElement>(strength = 12) {
  const ref = useRef<T | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const isCoarsePointer = window.matchMedia("(pointer: coarse)").matches;
    if (isCoarsePointer || reducedMotion) {
      setOffset({ x: 0, y: 0 });
      return;
    }

    let frame = 0;
    function handlePointerMove(event: PointerEvent) {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const rect = node!.getBoundingClientRect();
        const relX = (event.clientX - rect.left) / rect.width - 0.5;
        const relY = (event.clientY - rect.top) / rect.height - 0.5;
        setOffset({ x: relX * strength, y: relY * strength });
      });
    }
    function handlePointerLeave() {
      setOffset({ x: 0, y: 0 });
    }

    node.addEventListener("pointermove", handlePointerMove);
    node.addEventListener("pointerleave", handlePointerLeave);
    return () => {
      node.removeEventListener("pointermove", handlePointerMove);
      node.removeEventListener("pointerleave", handlePointerLeave);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [reducedMotion, strength]);

  return { ref, offset };
}
