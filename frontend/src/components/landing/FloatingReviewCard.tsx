import type { CSSProperties } from "react";
import { StatusPill } from "../ui/Badge";
import type { DemoReview } from "./demoData";

const TONE: Record<DemoReview["sentiment"], "positive" | "negative" | "warning"> = {
  positive: "positive",
  negative: "negative",
  mixed: "warning",
};

const LABEL: Record<DemoReview["sentiment"], string> = {
  positive: "Positive",
  negative: "Negative",
  mixed: "Mixed",
};

export function FloatingReviewCard({ review, className, style }: { review: DemoReview; className?: string; style?: CSSProperties }) {
  return (
    <div className={className ? `bsr-lp-review-card ${className}` : "bsr-lp-review-card"} style={style}>
      <div className="bsr-lp-review-card__head">
        <StatusPill tone={TONE[review.sentiment]}>{LABEL[review.sentiment]}</StatusPill>
        <span className="bsr-caption">{review.aspect}</span>
      </div>
      <p className="bsr-sm bsr-lp-review-card__text">&ldquo;{review.text}&rdquo;</p>
    </div>
  );
}
