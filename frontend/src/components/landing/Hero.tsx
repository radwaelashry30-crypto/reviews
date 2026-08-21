import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Button } from "../ui/Button";
import { DemoVideoModal } from "./DemoVideoModal";
import { HeroDashboardCluster } from "./HeroDashboardCluster";
import { usePointerParallax } from "./hooks/usePointerParallax";

export function Hero() {
  const [videoModalOpen, setVideoModalOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const { ref: parallaxRef, offset } = usePointerParallax<HTMLDivElement>(10);

  // Reveal the headline/CTAs a beat after mount rather than on first paint.
  useEffect(() => {
    const timer = requestAnimationFrame(() => setLoaded(true));
    return () => cancelAnimationFrame(timer);
  }, []);

  // Pause the background video while the tab isn't visible.
  useEffect(() => {
    function handleVisibility() {
      const video = videoRef.current;
      if (!video) return;
      if (document.hidden) video.pause();
      else if (!videoModalOpen) video.play().catch(() => undefined);
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [videoModalOpen]);

  return (
    <section id="top" className="bsr-lp-hero" ref={parallaxRef}>
      <div className="bsr-lp-hero__media" aria-hidden="true">
        <video
          ref={videoRef}
          className="bsr-lp-hero__video"
          src="/assets/baseera-hero.mp4"
          poster="/assets/baseera-hero-poster.jpg"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
        />
        <div className="bsr-lp-hero__overlay-navy" />
        <div className="bsr-lp-hero__overlay-gradient" />
        <div className="bsr-lp-hero__overlay-glow" />
        <div className="bsr-lp-hero__overlay-gold" />
        <div className="bsr-lp-hero__overlay-noise" />
      </div>

      <div className="bsr-lp-container bsr-lp-hero__grid">
        <div className={loaded ? "bsr-lp-hero__content bsr-lp-hero__content--in" : "bsr-lp-hero__content"}>
          <img src="/assets/baseera-logo-mark.png" alt="Baseera" width={56} height={56} className="bsr-lp-hero__logo" />
          <span className="bsr-lp-eyebrow bsr-label">AI-Powered Review Intelligence</span>
          <h1 className="bsr-text-display bsr-lp-hero__headline">
            Turn Every Review Into
            <br />
            A Smarter Business Decision
          </h1>
          <p className="bsr-body-lg bsr-lp-hero__copy">
            Baseera transforms scattered customer feedback into clear sentiment, actionable insights, and confident decisions.
          </p>
          <div className="bsr-lp-hero__actions">
            <Button variant="primary" to="/sentiment">
              Analyze Your Reviews
            </Button>
            <Button variant="secondary" onClick={() => setVideoModalOpen(true)}>
              Watch How It Works
            </Button>
          </div>
          <p className="bsr-caption bsr-lp-hero__honesty">Built on historical Olist review data · Demonstration platform</p>
        </div>

        <div
          className="bsr-lp-hero__visual"
          style={{ "--parallax-x": `${offset.x}px`, "--parallax-y": `${offset.y}px` } as CSSProperties}
        >
          <HeroDashboardCluster />
        </div>
      </div>

      <DemoVideoModal open={videoModalOpen} onClose={() => setVideoModalOpen(false)} />
    </section>
  );
}
