import { Badge, StatusPill } from "../ui/Badge";
import { DemoDataBadge } from "../ui/DemoDataBadge";
import { SectionHeader } from "../ui/SectionHeader";
import { SurfaceCard } from "../ui/SurfaceCard";
import { MiniAreaChart } from "./charts/MiniAreaChart";
import { SentimentDonut } from "./charts/SentimentDonut";
import { useInView } from "./hooks/useInView";
import { DEMO_KPIS, PAIN_POINTS, RECENT_REVIEWS, SENTIMENT_SPLIT, SENTIMENT_TREND, SOURCE_BREAKDOWN } from "./demoData";

const KPI_TILES = [
  { label: "Total reviews", value: DEMO_KPIS.totalReviews.toLocaleString() },
  { label: "Overall sentiment", value: `${DEMO_KPIS.overallPositivePct}% positive` },
  { label: "Top pain point", value: DEMO_KPIS.topPainPoint },
  { label: "Categories tracked", value: String(DEMO_KPIS.categoriesTracked) },
];

export function DashboardPreviewSection() {
  const { ref, inView } = useInView<HTMLDivElement>();

  return (
    <section className="bsr-lp-section" id="insights">
      <div className="bsr-lp-container">
        <SectionHeader
          eyebrow="Interactive dashboard preview"
          title="What your team would actually see"
          description="A live render of the dashboard layout, populated with clearly labeled demonstration data -- not a static screenshot."
        />

        <div className={inView ? "bsr-lp-window bsr-lp-window--in" : "bsr-lp-window"} ref={ref}>
          <div className="bsr-lp-window__chrome">
            <span className="bsr-lp-window__dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span className="bsr-lp-window__title bsr-mono">baseera.app / dashboard</span>
            <DemoDataBadge kind="demo" className="bsr-lp-window__badge" />
          </div>

          <div className="bsr-lp-window__body">
            <div className="bsr-lp-kpi-row">
              {KPI_TILES.map((tile) => (
                <SurfaceCard key={tile.label} className="bsr-lp-kpi-tile">
                  <span className="bsr-label">{tile.label}</span>
                  <span className="bsr-h3 bsr-mono">{tile.value}</span>
                </SurfaceCard>
              ))}
            </div>

            <div className="bsr-lp-dashboard-grid">
          <SurfaceCard className="bsr-lp-dashboard-panel bsr-lp-dashboard-panel--wide">
            <div className="bsr-lp-panel-head">
              <span className="bsr-h6">Sentiment trend</span>
              <Badge tone="neutral">Weekly</Badge>
            </div>
            {inView ? <MiniAreaChart data={SENTIMENT_TREND} height={192} showAxes /> : <div className="bsr-lp-chart-placeholder" style={{ height: 192 }} />}
          </SurfaceCard>

          <SurfaceCard className="bsr-lp-dashboard-panel">
            <div className="bsr-lp-panel-head">
              <span className="bsr-h6">Sentiment distribution</span>
            </div>
            {inView ? (
              <SentimentDonut positive={SENTIMENT_SPLIT.positive} neutral={SENTIMENT_SPLIT.neutral} negative={SENTIMENT_SPLIT.negative} size={152} />
            ) : (
              <div className="bsr-lp-chart-placeholder" style={{ height: 152 }} />
            )}
            <div className="bsr-lp-mini-legend bsr-lp-mini-legend--center">
              <span><i className="bsr-lp-dot bsr-lp-dot--positive" />Positive {SENTIMENT_SPLIT.positive}%</span>
              <span><i className="bsr-lp-dot bsr-lp-dot--warning" />Neutral {SENTIMENT_SPLIT.neutral}%</span>
              <span><i className="bsr-lp-dot bsr-lp-dot--negative" />Negative {SENTIMENT_SPLIT.negative}%</span>
            </div>
          </SurfaceCard>

          <SurfaceCard className="bsr-lp-dashboard-panel">
            <div className="bsr-lp-panel-head">
              <span className="bsr-h6">Review-source breakdown</span>
            </div>
            <div className="bsr-lp-bar-list">
              {SOURCE_BREAKDOWN.map((row) => (
                <div key={row.label} className="bsr-lp-bar-row">
                  <span className="bsr-sm">{row.label}</span>
                  <div className="bsr-lp-bar-track">
                    <div className="bsr-lp-bar-fill bsr-lp-bar-fill--blue" style={{ width: inView ? `${row.pct}%` : "0%" }} />
                  </div>
                  <span className="bsr-mono bsr-caption">{row.pct}%</span>
                </div>
              ))}
            </div>
          </SurfaceCard>

          <SurfaceCard className="bsr-lp-dashboard-panel">
            <div className="bsr-lp-panel-head">
              <span className="bsr-h6">Top pain points</span>
            </div>
            <div className="bsr-lp-bar-list">
              {PAIN_POINTS.slice(0, 4).map((row) => (
                <div key={row.category} className="bsr-lp-bar-row">
                  <span className="bsr-sm">{row.category}</span>
                  <div className="bsr-lp-bar-track">
                    <div className="bsr-lp-bar-fill bsr-lp-bar-fill--negative" style={{ width: inView ? `${row.negativeMentionPct}%` : "0%" }} />
                  </div>
                  <span className="bsr-mono bsr-caption">{row.negativeMentionPct}%</span>
                </div>
              ))}
            </div>
          </SurfaceCard>

          <SurfaceCard className="bsr-lp-dashboard-panel bsr-lp-dashboard-panel--wide">
            <div className="bsr-lp-panel-head">
              <span className="bsr-h6">Recent reviews</span>
            </div>
            <ul className="bsr-lp-recent-list">
              {RECENT_REVIEWS.map((review) => (
                <li key={review.id} className="bsr-lp-recent-row">
                  <StatusPill tone={review.sentiment === "positive" ? "positive" : review.sentiment === "negative" ? "negative" : "warning"}>
                    {review.sentiment === "positive" ? "Positive" : review.sentiment === "negative" ? "Negative" : "Mixed"}
                  </StatusPill>
                  <p className="bsr-sm">&ldquo;{review.text}&rdquo;</p>
                  <span className="bsr-caption">{review.aspect}</span>
                </li>
              ))}
            </ul>
          </SurfaceCard>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
