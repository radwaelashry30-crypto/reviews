import { useState } from "react";
import {
  Badge,
  Button,
  DemoDataBadge,
  EmptyState,
  ErrorState,
  GlassCard,
  IconButton,
  LoadingState,
  Modal,
  PageContainer,
  SectionHeader,
  StatusPill,
  SurfaceCard,
} from "../components/ui";
import "./DesignSystemPreviewPage.css";

const COLOR_TOKENS: Array<{ name: string; varName: string; hex: string }> = [
  { name: "Background", varName: "--bsr-bg", hex: "#030712" },
  { name: "Surface", varName: "--bsr-surface", hex: "#081225" },
  { name: "Elevated", varName: "--bsr-elevated", hex: "#0D1B2E" },
  { name: "Electric blue", varName: "--bsr-blue", hex: "#23C7FF" },
  { name: "Cyan", varName: "--bsr-cyan", hex: "#39E7F5" },
  { name: "Gold", varName: "--bsr-gold", hex: "#F4B942" },
  { name: "Soft white", varName: "--bsr-text", hex: "#F4F7FB" },
  { name: "Muted text", varName: "--bsr-text-muted", hex: "#91A4BD" },
  { name: "Positive", varName: "--bsr-positive", hex: "#3DDC97" },
  { name: "Negative", varName: "--bsr-negative", hex: "#FF667A" },
  { name: "Warning", varName: "--bsr-warning", hex: "#F5B942" },
];

const TYPE_ROWS: Array<{ tag: string; className: string; sample: string }> = [
  { tag: "display", className: "bsr-text-display", sample: "Turn feedback into decisions" },
  { tag: "h1", className: "bsr-h1", sample: "Sentiment intelligence" },
  { tag: "h2", className: "bsr-h2", sample: "Pain points this month" },
  { tag: "h3", className: "bsr-h3", sample: "Delivery delay is the top complaint" },
  { tag: "h4", className: "bsr-h4", sample: "Upload reviews" },
  { tag: "h5", className: "bsr-h5", sample: "Model status" },
  { tag: "h6", className: "bsr-h6", sample: "Recent analyses" },
  { tag: "body large", className: "bsr-body-lg", sample: "Baseera transforms scattered feedback into confident decisions." },
  { tag: "body", className: "bsr-body", sample: "Every chart reads a static processed snapshot, not a live feed." },
  { tag: "small", className: "bsr-sm", sample: "46 tests, all pass when artifacts are present." },
  { tag: "caption", className: "bsr-caption", sample: "Demonstration data — sample reviews, not a live production feed." },
  { tag: "label", className: "bsr-label", sample: "Sentiment" },
];

export function DesignSystemPreviewPage() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="dsp-page">
      <div className="dsp-banner" role="note">
        Internal preview — Phase 1 verification only. Not part of the Baseera product; not linked from any nav.
      </div>

      <PageContainer wide>
        <header className="dsp-header">
          <span className="bsr-label" style={{ color: "var(--bsr-gold)" }}>
            Design system
          </span>
          <h1 className="bsr-h1">Baseera design foundation</h1>
          <p className="bsr-body-lg" style={{ color: "var(--bsr-text-muted)" }}>
            Every token, primitive, and state built in Phase 1. Existing application pages are unchanged — this page exists only to verify the
            foundation before Phase 2/3 build on top of it.
          </p>
        </header>

        {/* ---------------- Colors ---------------- */}
        <section className="dsp-section" aria-labelledby="colors-heading">
          <SectionHeader eyebrow="01 — Tokens" title="Color" />
          <div className="dsp-swatch-grid" id="colors-heading">
            {COLOR_TOKENS.map((token) => (
              <div key={token.varName}>
                <div className="dsp-swatch-chip" style={{ background: `var(${token.varName})` }} />
                <div className="dsp-swatch-label">{token.name}</div>
                <div className="dsp-swatch-hex">{token.hex}</div>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------- Typography ---------------- */}
        <section className="dsp-section" aria-labelledby="type-heading">
          <SectionHeader eyebrow="02 — Tokens" title="Typography scale" description="Sora for display/headings, Inter for everything read at length." />
          <SurfaceCard>
            <div id="type-heading">
              {TYPE_ROWS.map((row) => (
                <div className="dsp-type-row" key={row.tag}>
                  <span className="dsp-type-tag">{row.tag}</span>
                  <span className={row.className}>{row.sample}</span>
                </div>
              ))}
            </div>
          </SurfaceCard>
        </section>

        {/* ---------------- Buttons ---------------- */}
        <section className="dsp-section" aria-labelledby="buttons-heading">
          <SectionHeader eyebrow="03 — Components" title="Buttons" description="Default, hover/active (try it live), focus-visible (tab to them), disabled, and loading." />
          <SurfaceCard>
            <div id="buttons-heading">
              <div className="dsp-btn-row">
                <span className="dsp-btn-row-label">Primary</span>
                <Button variant="primary" leftIcon="↻">Analyze Reviews</Button>
                <Button variant="primary" loading loadingLabel="Analyzing review">Analyze Reviews</Button>
                <Button variant="primary" disabled>Analyze Reviews</Button>
              </div>
              <div className="dsp-btn-row">
                <span className="dsp-btn-row-label">Premium (gold)</span>
                <Button variant="premium" rightIcon="→">Upgrade Plan</Button>
                <Button variant="premium" disabled>Upgrade Plan</Button>
              </div>
              <div className="dsp-btn-row">
                <span className="dsp-btn-row-label">Secondary</span>
                <Button variant="secondary" onClick={() => setModalOpen(true)}>Watch Demo</Button>
                <Button variant="secondary" disabled>Watch Demo</Button>
              </div>
              <div className="dsp-btn-row">
                <span className="dsp-btn-row-label">Ghost</span>
                <Button variant="ghost">Learn more</Button>
                <Button variant="ghost" to="/">Back to Overview (real link)</Button>
              </div>
              <div className="dsp-btn-row">
                <span className="dsp-btn-row-label">Destructive</span>
                <Button variant="destructive">Delete upload</Button>
                <Button variant="destructive" disabled>Delete upload</Button>
              </div>
              <div className="dsp-btn-row">
                <span className="dsp-btn-row-label">Icon-only</span>
                <IconButton icon="↻" aria-label="Refresh" variant="secondary" />
                <IconButton icon="⋯" aria-label="More options" variant="ghost" />
                <IconButton icon="✕" aria-label="Dismiss (disabled example)" variant="destructive" disabled />
                <IconButton icon="↻" aria-label="Loading example" variant="primary" loading />
              </div>
              <div className="dsp-btn-row">
                <span className="dsp-btn-row-label">Full width</span>
                <div style={{ flex: 1 }}>
                  <Button variant="primary" fullWidth>Upload Reviews (full width)</Button>
                </div>
              </div>
            </div>
          </SurfaceCard>
        </section>

        {/* ---------------- Cards ---------------- */}
        <section className="dsp-section" aria-labelledby="cards-heading">
          <SectionHeader eyebrow="04 — Components" title="Cards" />
          <div className="dsp-grid-2" id="cards-heading">
            <GlassCard glow="blue">
              <span className="bsr-label" style={{ color: "var(--bsr-blue)" }}>Glass card · blue glow</span>
              <p className="bsr-h4" style={{ marginTop: "var(--bsr-space-2)" }}>For content over imagery/video</p>
              <p className="bsr-sm" style={{ marginTop: "var(--bsr-space-2)" }}>Translucent, blurred — used for hero panels and floating review cards.</p>
            </GlassCard>
            <SurfaceCard interactive>
              <span className="bsr-label">Surface card · interactive</span>
              <p className="bsr-h4" style={{ marginTop: "var(--bsr-space-2)" }}>For dense data</p>
              <p className="bsr-sm" style={{ marginTop: "var(--bsr-space-2)" }}>Opaque — used for KPI tiles, tables, and forms where legibility matters most. Hover to see the lift.</p>
            </SurfaceCard>
          </div>
        </section>

        {/* ---------------- Badges ---------------- */}
        <section className="dsp-section" aria-labelledby="badges-heading">
          <SectionHeader eyebrow="05 — Components" title="Badges & status pills" />
          <div className="dsp-pill-row" id="badges-heading">
            <StatusPill tone="positive">Positive</StatusPill>
            <StatusPill tone="negative">Negative</StatusPill>
            <StatusPill tone="warning">Needs review</StatusPill>
            <StatusPill tone="blue">In progress</StatusPill>
            <StatusPill tone="neutral">Neutral</StatusPill>
            <Badge tone="gold">247 reviews</Badge>
            <DemoDataBadge kind="demo" />
            <DemoDataBadge kind="historical" />
          </div>
        </section>

        {/* ---------------- Modal ---------------- */}
        <section className="dsp-section" aria-labelledby="modal-heading">
          <SectionHeader eyebrow="06 — Components" title="Modal" description="Keyboard-operable: Tab cycles inside, Escape closes, focus returns to the trigger." />
          <div id="modal-heading">
            <Button variant="secondary" onClick={() => setModalOpen(true)}>
              Open example modal
            </Button>
          </div>
          <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Watch how it works" description="Example modal — stands in for the landing page's demo-video dialog.">
            <p className="bsr-sm">This is the accessible modal primitive: focus is trapped while it's open, Escape closes it, and focus returns to the button that opened it.</p>
            <div style={{ marginTop: "var(--bsr-space-4)", display: "flex", gap: "var(--bsr-space-3)" }}>
              <Button variant="primary" onClick={() => setModalOpen(false)}>Got it</Button>
              <Button variant="ghost" onClick={() => setModalOpen(false)}>Cancel</Button>
            </div>
          </Modal>
        </section>

        {/* ---------------- States ---------------- */}
        <section className="dsp-section" aria-labelledby="states-heading">
          <SectionHeader eyebrow="07 — Components" title="Loading, empty, error & demo states" />
          <div className="dsp-grid-3" id="states-heading">
            <SurfaceCard>
              <span className="bsr-label">Loading</span>
              <LoadingState label="Loading reviews…" />
            </SurfaceCard>
            <SurfaceCard>
              <span className="bsr-label">Empty</span>
              <EmptyState title="No reviews uploaded yet" description="Upload a CSV or analyze a single review to see results here." action={<Button variant="secondary">Upload Reviews</Button>} />
            </SurfaceCard>
            <SurfaceCard>
              <span className="bsr-label">Error</span>
              <ErrorState code="MODEL_NOT_AVAILABLE" message="BERT is not loaded on this deployment." onRetry={() => undefined} />
            </SurfaceCard>
          </div>
        </section>
      </PageContainer>
    </div>
  );
}
