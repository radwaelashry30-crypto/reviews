import { useEffect, useRef } from "react";
import { Modal } from "../ui/Modal";

export interface DemoVideoModalProps {
  open: boolean;
  onClose: () => void;
}

/** "Watch How It Works" -- the same hero cinematic, this time with native
 * controls, inside the Phase 1 Modal (focus-trapped, Escape-to-close). */
export function DemoVideoModal({ open, onClose }: DemoVideoModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (!open) {
      videoRef.current?.pause();
    }
  }, [open]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Watch how Baseera works"
      description="A cinematic walkthrough of the review-intelligence journey: collect, analyze, understand, decide."
    >
      <video
        ref={videoRef}
        className="bsr-lp-modal-video"
        src="/assets/baseera-hero.mp4"
        poster="/assets/baseera-hero-poster.jpg"
        controls
        playsInline
        preload="metadata"
        autoPlay={open}
      >
        <track kind="captions" />
      </video>
      <p className="bsr-caption" style={{ marginTop: "var(--bsr-space-3)" }}>
        Cinematic sequence produced for Baseera. No audio narration — captions are not required for this silent sequence.
      </p>
    </Modal>
  );
}
