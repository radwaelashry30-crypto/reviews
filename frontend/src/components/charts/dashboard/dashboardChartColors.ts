/**
 * Dashboard-only chart palette, on the Baseera `--bsr-*` tokens -- the
 * shared `utils/chartColors.ts` (brown/gold) stays untouched since it's
 * still used by Sentiment, Batch Upload, and Customers, which aren't
 * reskinned yet. Referencing the CSS custom properties directly (rather
 * than copying hex values) keeps this a single source of truth with the
 * rest of the Baseera system.
 */
export const CHART_BLUE = "var(--bsr-blue)";
export const CHART_CYAN = "var(--bsr-cyan)";
export const CHART_GOLD = "var(--bsr-gold)";
export const CHART_POSITIVE = "var(--bsr-positive)";
export const CHART_NEGATIVE = "var(--bsr-negative)";
export const CHART_WARNING = "var(--bsr-warning)";
export const CHART_AXIS = "var(--bsr-text-muted)";
export const CHART_GRID = "var(--bsr-border)";

/** Ordered scale for multi-series categorical charts (payment methods, etc). */
export const BLUE_SCALE = [
  "var(--bsr-blue)",
  "var(--bsr-gold)",
  "var(--bsr-cyan)",
  "var(--bsr-positive)",
  "var(--bsr-text-muted)",
];
