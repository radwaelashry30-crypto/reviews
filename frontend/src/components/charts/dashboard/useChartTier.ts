import { useEffect, useState } from "react";

export type ChartTier = "mobile" | "tablet" | "desktop";

function computeTier(): ChartTier {
  if (typeof window === "undefined") return "desktop";
  const w = window.innerWidth;
  if (w < 640) return "mobile";
  if (w < 1024) return "tablet";
  return "desktop";
}

/**
 * Viewport tier for the 6 dashboard-exclusive charts to branch their tick
 * density, font size, and chart height on -- container queries would need a
 * ResizeObserver per chart; a single window-width hook is simpler and
 * accurate enough since every chart panel spans close to full column width.
 */
export function useChartTier(): ChartTier {
  const [tier, setTier] = useState<ChartTier>(computeTier);
  useEffect(() => {
    function onResize() {
      setTier(computeTier());
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return tier;
}
