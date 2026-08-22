/**
 * Maps real RFM segment NAMES (not array position) to Baseera colors.
 * `segment_summary` from the API is alphabetically sorted, not by cluster
 * id, so a positional color array would silently mismatch if that order
 * ever shifts -- this looks up by the actual `Segment` string instead.
 *
 * Deliberately avoids `--bsr-negative` (red) for "At Risk" -- a customer
 * simply not having ordered recently is an expected e-commerce pattern the
 * backend itself names, not a system failure, so it gets restrained gold
 * (a "needs attention" tone) rather than an alarm color. Only the segment
 * names the real backend can actually return are mapped; an unmapped name
 * falls back to neutral gray rather than guessing.
 */
export const SEGMENT_COLORS: Record<string, string> = {
  "Loyal Customer": "var(--bsr-positive)",
  "Champion": "var(--bsr-positive)",
  "Recent / Promising": "var(--bsr-blue)",
  "Big Spender (Lapsing)": "var(--bsr-cyan)",
  "At Risk": "var(--bsr-gold)",
  "Needs Attention": "var(--bsr-gold)",
};

export function colorForSegment(segment: string): string {
  return SEGMENT_COLORS[segment] ?? "var(--bsr-neutral)";
}

/** Builds a `colors` array for SegmentChart's existing `colors?` prop,
 * matching `data`'s actual order (name-based, not a hardcoded position). */
export function colorsForSegments(data: { Segment: string }[]): string[] {
  return data.map((row) => colorForSegment(row.Segment));
}
