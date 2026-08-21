import { SectionHeader } from "../ui/SectionHeader";
import { Reveal } from "./Reveal";

const STEPS = [
  { title: "Add reviews", description: "Analyze one review by hand, upload a CSV batch, or explore the historical Olist dataset already loaded." },
  { title: "Analyze intelligence", description: "BERT/CNN2D score sentiment; aspect-level scoring shows what part of the experience drove it." },
  { title: "Act on insights", description: "Pain points, trends, and rule-based recommendations turn scattered feedback into a short list of what to fix." },
];

/** Alternating left/right editorial rows with an oversized numeral standing
 * in for imagery -- distinct from the card grids used elsewhere. */
export function HowItWorksSection() {
  return (
    <section className="bsr-lp-section bsr-lp-section--tight" id="how-it-works">
      <div className="bsr-lp-container">
        <SectionHeader eyebrow="How Baseera works" title="Three steps, no black box" />
        <div className="bsr-lp-how-rows">
          {STEPS.map((step, idx) => (
            <Reveal key={step.title} delayMs={idx * 100} className={idx % 2 === 1 ? "bsr-lp-how-row bsr-lp-how-row--reverse" : "bsr-lp-how-row"}>
              <span className="bsr-lp-how-row__numeral bsr-mono" aria-hidden="true">{String(idx + 1).padStart(2, "0")}</span>
              <div className="bsr-lp-how-row__body">
                <p className="bsr-h3">{step.title}</p>
                <p className="bsr-body">{step.description}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
