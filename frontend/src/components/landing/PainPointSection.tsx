import { Badge } from "../ui/Badge";
import { SectionHeader } from "../ui/SectionHeader";
import { SurfaceCard } from "../ui/SurfaceCard";
import { useInView } from "./hooks/useInView";
import { PAIN_POINTS } from "./demoData";

export function PainPointSection() {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <section className="bsr-lp-section bsr-lp-section--story">
      <div className="bsr-lp-container">
        <div className="bsr-lp-story-rail bsr-lp-story-rail--first">
          <span className="bsr-lp-story-rail__line" aria-hidden="true" />
          <span className="bsr-lp-story-rail__node bsr-mono" aria-hidden="true">1</span>
          <SectionHeader
            eyebrow="Pain-point discovery"
            title="Aspect-level scoring finds where to focus"
            description="Categories below are a demonstration set for this preview, not a literal export of the backend's aspect model."
            action={<Badge tone="warning">Demonstration categories</Badge>}
          />
          <SurfaceCard>
            <div ref={ref} className="bsr-lp-bar-list bsr-lp-bar-list--spacious">
              {PAIN_POINTS.map((row) => (
                <div key={row.category} className="bsr-lp-bar-row bsr-lp-bar-row--large">
                  <span className="bsr-body">{row.category}</span>
                  <div className="bsr-lp-bar-track bsr-lp-bar-track--tall">
                    <div className="bsr-lp-bar-fill bsr-lp-bar-fill--negative" style={{ width: inView ? `${row.negativeMentionPct}%` : "0%" }} />
                  </div>
                  <span className="bsr-mono bsr-sm">{row.negativeMentionPct}% of negative mentions</span>
                </div>
              ))}
            </div>
          </SurfaceCard>
        </div>
      </div>
    </section>
  );
}
