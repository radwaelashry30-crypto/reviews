import { DemoDataBadge } from "../ui/DemoDataBadge";
import { SectionHeader } from "../ui/SectionHeader";
import { useInView } from "./hooks/useInView";
import { SENTIMENT_SPLIT } from "./demoData";

const ROWS: Array<{ key: keyof typeof SENTIMENT_SPLIT; label: string; tone: "positive" | "warning" | "negative"; description: string }> = [
  { key: "positive", label: "Positive", tone: "positive", description: "Clear satisfaction -- praise for quality, service, or value." },
  { key: "neutral", label: "Neutral", tone: "warning", description: "Mixed or matter-of-fact language, no strong sentiment either way." },
  { key: "negative", label: "Negative", tone: "negative", description: "Explicit dissatisfaction the business should act on." },
];

/**
 * Full-width segmented bar + oversized figures, replacing what used to be
 * three identical bordered cards -- the same three numbers, but as one
 * visualization instead of a repeated card pattern.
 */
export function SentimentIntelligenceSection() {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <section className="bsr-lp-section bsr-lp-section--tight">
      <div className="bsr-lp-container">
        <SectionHeader eyebrow="Sentiment intelligence" title="Positive, neutral, negative — explained, not just labeled" action={<DemoDataBadge kind="demo" />} />

        <div ref={ref} className="bsr-lp-sentiment-bar">
          {ROWS.map((row) => (
            <div
              key={row.key}
              className={`bsr-lp-sentiment-bar__segment bsr-lp-sentiment-bar__segment--${row.tone}`}
              style={{ width: inView ? `${SENTIMENT_SPLIT[row.key]}%` : 0 }}
            />
          ))}
        </div>

        <div className="bsr-lp-sentiment-figures">
          {ROWS.map((row) => (
            <div key={row.key} className="bsr-lp-sentiment-figure">
              <span className={`bsr-lp-sentiment-figure__value bsr-mono bsr-lp-sentiment-figure__value--${row.tone}`}>
                {SENTIMENT_SPLIT[row.key]}%
              </span>
              <span className="bsr-h6">{row.label}</span>
              <p className="bsr-sm">{row.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
