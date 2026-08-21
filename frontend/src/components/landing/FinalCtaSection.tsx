import { Button } from "../ui/Button";

export function FinalCtaSection() {
  return (
    <section className="bsr-lp-section bsr-lp-final-cta">
      <span className="bsr-lp-final-cta__noise" aria-hidden="true" />
      <span className="bsr-lp-final-cta__beam" aria-hidden="true" />
      <div className="bsr-lp-container bsr-lp-final-cta__inner">
        <h2 className="bsr-h1">Your Customers Are Already Telling You What To Improve.</h2>
        <div className="bsr-lp-hero__actions">
          <Button variant="primary" to="/sentiment">
            Analyze Your First Review
          </Button>
          <Button variant="secondary" to="/">
            Explore the Dashboard
          </Button>
        </div>
      </div>
    </section>
  );
}
