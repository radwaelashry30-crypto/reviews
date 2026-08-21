import { useEffect } from "react";
import { CapabilitiesSection } from "../components/landing/CapabilitiesSection";
import { DashboardPreviewSection } from "../components/landing/DashboardPreviewSection";
import { FinalCtaSection } from "../components/landing/FinalCtaSection";
import { Hero } from "../components/landing/Hero";
import { HowItWorksSection } from "../components/landing/HowItWorksSection";
import { JourneySection } from "../components/landing/JourneySection";
import { LandingFooter } from "../components/landing/LandingFooter";
import { LandingNav } from "../components/landing/LandingNav";
import { PainPointSection } from "../components/landing/PainPointSection";
import { RecommendationsSection } from "../components/landing/RecommendationsSection";
import { ResponsibleAiSection } from "../components/landing/ResponsibleAiSection";
import { SentimentIntelligenceSection } from "../components/landing/SentimentIntelligenceSection";
import { TechTransparencySection } from "../components/landing/TechTransparencySection";
import { TrendsSection } from "../components/landing/TrendsSection";
import "../styles/landing.css";

/**
 * Phase 2 cinematic landing page -- built entirely on Phase 1 tokens/
 * components (no second design system). Routed at /landing-preview only;
 * "/" still serves the existing DashboardPage untouched until this is
 * promoted after visual approval.
 *
 * Perf note: this project has no route-level code splitting today (a
 * single ~700KB JS bundle covers every page, confirmed in the Phase 1
 * build output) -- adding it here alone wouldn't shrink what a visitor to
 * *this* page downloads, since recharts etc. are already forced into the
 * shared bundle by the existing app pages. Real code-splitting is a
 * repo-wide build-config change, out of scope for "Phase 2 only." What
 * this page does do: defer *mounting* (not just rendering behind CSS) the
 * chart-heavy sections below the fold via IntersectionObserver
 * (`useInView`), so their render work doesn't compete with the hero video
 * on first paint.
 */
export function LandingPreviewPage() {
  // A React Router SPA renders its DOM after the browser's own "scroll to
  // the URL hash on load" moment has already passed, so a direct link like
  // /landing-preview#insights lands at the top instead of the section --
  // this replays that scroll once the target actually exists.
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    const target = document.getElementById(hash);
    target?.scrollIntoView();
  }, []);

  return (
    <div className="bsr-landing">
      <LandingNav />
      <Hero />
      <JourneySection />
      <CapabilitiesSection />
      <DashboardPreviewSection />
      <SentimentIntelligenceSection />
      <PainPointSection />
      <TrendsSection />
      <RecommendationsSection />
      <HowItWorksSection />
      <ResponsibleAiSection />
      <TechTransparencySection />
      <FinalCtaSection />
      <LandingFooter />
    </div>
  );
}
