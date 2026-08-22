import type { ChartTier } from "./useChartTier";

/**
 * How many x-axis ticks a chart can show without crowding, given its own
 * rendered pixel width (from recharts' `ResponsiveContainer onResize`, not
 * `window.innerWidth`). A wide viewport doesn't mean every chart card is
 * wide -- Monthly orders sits in a narrower column than Monthly revenue at
 * every desktop breakpoint, so the two need different tick counts even
 * though they're on the same screen.
 *
 * `tier` (from `useChartTier`, viewport-based) still governs font size
 * separately, and doubles as an intentional upper cap here: mobile always
 * gets exactly first/mid/last regardless of measured width (its larger
 * font needs the extra room more than it needs more labels), and tablet is
 * deliberately kept sparser than a same-width desktop chart would be.
 */
function ticksBudget(containerWidth: number, tier: ChartTier): number {
  if (tier === "mobile") return 3;

  // Rough per-label footprint at this chart's tick font size ("2018-09" plus
  // breathing room), and the axis/margin chrome that isn't plotting area.
  const usablePlotWidth = Math.max(containerWidth - 80, 60);
  const approxLabelWidth = 58;
  const widthBasedMax = Math.floor(usablePlotWidth / approxLabelWidth) + 1;

  const tierCap = tier === "tablet" ? 6 : 10;
  return Math.min(tierCap, Math.max(4, widthBasedMax));
}

/**
 * Picks an explicit tick subset for a category XAxis instead of relying on
 * recharts' own overlap-avoidance. Explicit `ticks` always includes the
 * first and last value, so the final label is never dropped/clipped, and
 * the set never changes shape once computed, so nothing can overlap. The
 * Tooltip is unaffected -- recharts reads the hovered data point directly,
 * not the drawn ticks, so every date/value is still available on hover
 * regardless of which labels are visible.
 */
export function pickTicks(values: string[], containerWidth: number, tier: ChartTier): string[] {
  const lastIndex = values.length - 1;
  if (lastIndex <= 0) return values;

  const targetCount = Math.min(ticksBudget(containerWidth, tier), lastIndex + 1);

  // Evenly distribute `targetCount` indices across [0, lastIndex] by
  // construction (i=0 always lands on 0, i=targetCount-1 always lands on
  // lastIndex), rather than stepping forward and patching up the end
  // afterward -- that always keeps every gap close to the same size, so
  // there's no separate "is the last gap too small" case to handle.
  const indices = Array.from({ length: targetCount }, (_, i) =>
    Math.round((i * lastIndex) / (targetCount - 1 || 1)),
  );
  const unique = Array.from(new Set(indices));
  return unique.map((i) => values[i]);
}
