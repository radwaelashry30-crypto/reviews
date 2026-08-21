import { GlassCard } from "../ui/GlassCard";
import { SectionHeader } from "../ui/SectionHeader";
import { Reveal } from "./Reveal";
import { CAPABILITIES, PRIMARY_CAPABILITY_COUNT } from "./demoData";

export function CapabilitiesSection() {
  const primary = CAPABILITIES.slice(0, PRIMARY_CAPABILITY_COUNT);
  const secondary = CAPABILITIES.slice(PRIMARY_CAPABILITY_COUNT);

  return (
    <section className="bsr-lp-section bsr-lp-section--tight">
      <div className="bsr-lp-container">
        <SectionHeader eyebrow="Core capabilities" title="What's actually running under the hood" description="Real functionality, shipped in the current backend -- not a roadmap slide." />

        <div className="bsr-lp-capabilities-primary">
          {primary.map((capability, idx) => (
            <Reveal key={capability.title} delayMs={idx * 90}>
              <GlassCard glow={idx === 0 ? "blue" : "none"} className="bsr-lp-capability-primary">
                <span className="bsr-lp-capability-primary__index bsr-mono">{String(idx + 1).padStart(2, "0")}</span>
                <p className="bsr-h4">{capability.title}</p>
                <p className="bsr-body">{capability.description}</p>
              </GlassCard>
            </Reveal>
          ))}
        </div>

        <Reveal delayMs={120}>
          <div className="bsr-lp-capabilities-secondary">
            <span className="bsr-label bsr-lp-capabilities-secondary__label">Also included</span>
            <div className="bsr-lp-capabilities-secondary__grid">
              {secondary.map((capability) => (
                <div key={capability.title} className="bsr-lp-capabilities-secondary__row">
                  <p className="bsr-h6">{capability.title}</p>
                  <p className="bsr-caption">{capability.description}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
