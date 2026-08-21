import { DemoDataBadge } from "../ui/DemoDataBadge";
import { SectionHeader } from "../ui/SectionHeader";
import { SurfaceCard } from "../ui/SurfaceCard";
import { MiniAreaChart } from "./charts/MiniAreaChart";
import { useInView } from "./hooks/useInView";
import { SENTIMENT_TREND } from "./demoData";

export function TrendsSection() {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <section className="bsr-lp-section bsr-lp-section--story">
      <div className="bsr-lp-container">
        <div className="bsr-lp-story-rail">
          <span className="bsr-lp-story-rail__line" aria-hidden="true" />
          <span className="bsr-lp-story-rail__node bsr-mono" aria-hidden="true">2</span>
          <SectionHeader
            eyebrow="Trends & business signals"
            title="One review is an opinion. A hundred is a trend."
            description="The same positive-rate metric, tracked week over week, on the historical dataset."
            action={<DemoDataBadge kind="historical" />}
          />
          <SurfaceCard>
            <div ref={ref}>{inView ? <MiniAreaChart data={SENTIMENT_TREND} height={280} showAxes /> : <div className="bsr-lp-chart-placeholder" style={{ height: 280 }} />}</div>
          </SurfaceCard>
        </div>
      </div>
    </section>
  );
}
