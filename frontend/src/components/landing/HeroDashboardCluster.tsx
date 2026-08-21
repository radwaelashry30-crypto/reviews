import type { CSSProperties } from "react";
import { DemoDataBadge } from "../ui/DemoDataBadge";
import { GlassCard } from "../ui/GlassCard";
import { StatusPill } from "../ui/Badge";
import { FloatingReviewCard } from "./FloatingReviewCard";
import { DEMO_REVIEWS, DEMO_KPIS, PAIN_POINTS, RULE_BASED_RECOMMENDATION, SENTIMENT_SPLIT } from "./demoData";

const topPainPoint = PAIN_POINTS[0];

/**
 * The hero's right-side "layered interactive glass UI" -- real HTML/CSS,
 * not text baked into the video. Kept intentionally lightweight (no
 * recharts mount here) since it renders above the fold alongside the
 * video; the full chart-driven dashboard preview lives further down the
 * page in DashboardPreviewSection and only mounts once scrolled near.
 */
export function HeroDashboardCluster() {
  return (
    <div className="bsr-lp-hero-cluster" aria-label="Example Baseera dashboard, demonstration data">
      {/* Right-aligned column, in normal flow -- height comes from real
          content so nothing below has to guess it and collide. */}
      <div className="bsr-lp-hero-cluster__stack">
        <GlassCard glow="blue" className="bsr-lp-hero-card bsr-lp-hero-card--dashboard">
          <div className="bsr-lp-hero-card__head">
            <span className="bsr-label">Sentiment overview</span>
            <DemoDataBadge kind="demo" />
          </div>
          <div className="bsr-lp-mini-ring" style={{ "--ring-pct": `${SENTIMENT_SPLIT.positive}%` } as CSSProperties}>
            <span className="bsr-h4">{SENTIMENT_SPLIT.positive}%</span>
            <span className="bsr-caption">Positive</span>
          </div>
          <div className="bsr-lp-mini-legend">
            <span><i className="bsr-lp-dot bsr-lp-dot--positive" />Positive {SENTIMENT_SPLIT.positive}%</span>
            <span><i className="bsr-lp-dot bsr-lp-dot--warning" />Neutral {SENTIMENT_SPLIT.neutral}%</span>
            <span><i className="bsr-lp-dot bsr-lp-dot--negative" />Negative {SENTIMENT_SPLIT.negative}%</span>
          </div>
          <div className="bsr-lp-hero-card__foot">
            <span className="bsr-caption">{DEMO_KPIS.totalReviews.toLocaleString()} reviews analyzed</span>
          </div>
        </GlassCard>

        <GlassCard glow="none" className="bsr-lp-hero-card bsr-lp-hero-card--pain">
          <div className="bsr-lp-hero-card__head">
            <span className="bsr-label">Top pain point</span>
          </div>
          <p className="bsr-h5" style={{ marginTop: "0.35rem" }}>{topPainPoint.category}</p>
          <div className="bsr-lp-bar-track">
            <div className="bsr-lp-bar-fill bsr-lp-bar-fill--negative" style={{ width: `${topPainPoint.negativeMentionPct}%` }} />
          </div>
          <span className="bsr-caption">{topPainPoint.negativeMentionPct}% of negative mentions</span>
        </GlassCard>

        <GlassCard glow="gold" className="bsr-lp-hero-card bsr-lp-hero-card--recommendation">
          <div className="bsr-lp-hero-card__head">
            <StatusPill tone="gold" dot={false}>Rule-based</StatusPill>
          </div>
          <p className="bsr-sm" style={{ marginTop: "0.5rem" }}>{RULE_BASED_RECOMMENDATION.text}</p>
        </GlassCard>
      </div>

      {/* Left gutter -- positioned so review cards never overlap the stack. */}
      <div className="bsr-lp-hero-reviews">
        {DEMO_REVIEWS.map((review, idx) => (
          <FloatingReviewCard key={review.id} review={review} className={`bsr-lp-hero-review-${idx}`} />
        ))}
        <DemoDataBadge kind="demo" label="Demonstration review content" className="bsr-lp-hero-reviews__badge" />
      </div>

      {/* Decorative connective tissue -- purely visual, hidden from assistive tech. */}
      <svg className="bsr-lp-hero-lines" aria-hidden="true" viewBox="0 0 600 700" preserveAspectRatio="none">
        <path d="M 190 100 C 260 140, 280 170, 330 190" className="bsr-lp-hero-line" />
        <path d="M 190 340 C 260 350, 280 360, 330 380" className="bsr-lp-hero-line" />
        <path d="M 190 560 C 260 540, 290 530, 340 520" className="bsr-lp-hero-line bsr-lp-hero-line--gold" />
      </svg>
    </div>
  );
}
