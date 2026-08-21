const POINTS = [
  { title: "Historical dataset, clearly labeled", description: "The dataset covers Jan 2017–Aug 2018 Brazilian e-commerce reviews. Every chart on this preview says so; nothing here is presented as live." },
  { title: "No invented integrations", description: "Baseera connects to a manual entry form, a CSV upload, and the historical dataset. No live Shopify/Amazon/Google Reviews connector exists yet." },
  { title: "Model limitations are documented", description: "Sentiment predictions are probabilistic estimates from a specific dataset and time period -- not ground truth about customer intent." },
  { title: "Human decision-making stays essential", description: "Predictions are analytical assistance. Consequential decisions about customers or sellers should always get human review." },
];

/** Split-screen: the claim sits fixed on the left, the four honesty points
 * run as a divided list on the right -- not a fourth grid of cards. */
export function ResponsibleAiSection() {
  return (
    <section className="bsr-lp-section bsr-lp-section--tight" id="responsible-ai">
      <div className="bsr-lp-container bsr-lp-responsible-split">
        <div className="bsr-lp-responsible-split__intro">
          <span className="bsr-lp-eyebrow bsr-label">Responsible AI & data honesty</span>
          <h2 className="bsr-h2">What Baseera will and won't claim</h2>
        </div>
        <ul className="bsr-lp-responsible-list">
          {POINTS.map((point) => (
            <li key={point.title} className="bsr-lp-responsible-list__row">
              <p className="bsr-h6">{point.title}</p>
              <p className="bsr-sm">{point.description}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
