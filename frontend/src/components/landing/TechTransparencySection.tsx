import { Badge } from "../ui/Badge";
import { SectionHeader } from "../ui/SectionHeader";

const STACK = [
  { name: "FastAPI", note: "Backend API" },
  { name: "React + TypeScript", note: "Frontend" },
  { name: "BERT", note: "Fine-tuned sentiment model" },
  { name: "CNN2D", note: "From-scratch sentiment model" },
  { name: "RFM segmentation", note: "K-Means customer segments" },
];

export function TechTransparencySection() {
  return (
    <section className="bsr-lp-section bsr-lp-section--tight bsr-lp-tech-section">
      <div className="bsr-lp-container">
        <SectionHeader eyebrow="Technology & model transparency" title="Built with what's actually in the repository" description="No claimed technology beyond what ships in the codebase today." />
        <div className="bsr-lp-tech-row">
          {STACK.map((item) => (
            <Badge key={item.name} tone="blue" className="bsr-lp-tech-pill">
              {item.name} <span className="bsr-lp-tech-pill__note">· {item.note}</span>
            </Badge>
          ))}
        </div>
      </div>
    </section>
  );
}
