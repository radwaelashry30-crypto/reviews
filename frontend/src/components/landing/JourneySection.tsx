import { Reveal } from "./Reveal";
import { SectionHeader } from "../ui/SectionHeader";
import { JOURNEY_STAGES } from "./demoData";

export function JourneySection() {
  return (
    <section className="bsr-lp-section" id="platform">
      <div className="bsr-lp-container">
        <SectionHeader eyebrow="The review intelligence journey" title="Collect → Analyze → Understand → Decide" description="Every stage runs on functionality that exists in the product today." />
        <div className="bsr-lp-journey">
          {JOURNEY_STAGES.map((stage, idx) => (
            <Reveal key={stage.stage} delayMs={idx * 140} className="bsr-lp-journey__stage">
              <div
                className={[
                  "bsr-lp-journey__rail",
                  idx === 0 && "bsr-lp-journey__rail--first",
                  idx === JOURNEY_STAGES.length - 1 && "bsr-lp-journey__rail--last",
                ].filter(Boolean).join(" ")}
                aria-hidden="true"
              >
                <span className="bsr-lp-journey__node" />
              </div>
              <div className="bsr-lp-journey__body">
                <span className="bsr-mono bsr-lp-journey__index">{String(idx + 1).padStart(2, "0")}</span>
                <span className="bsr-label bsr-lp-journey__stage-label">{stage.stage}</span>
                <p className="bsr-h5">{stage.title}</p>
                <p className="bsr-sm">{stage.description}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
