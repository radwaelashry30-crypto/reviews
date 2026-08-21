const PLATFORM_LINKS = [
  { href: "#platform", label: "Platform" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "#insights", label: "Insights" },
  { href: "#responsible-ai", label: "Responsible AI" },
];

const PROJECT_LINKS = [
  { href: "https://github.com/radwaelashry30-crypto/reviews", label: "GitHub repository" },
];

export function LandingFooter() {
  return (
    <footer className="bsr-lp-footer">
      <div className="bsr-lp-container bsr-lp-footer__grid">
        <div className="bsr-lp-footer__brand">
          <img src="/assets/baseera-logo-mark.png" alt="Baseera" width={40} height={40} />
          <p className="bsr-h6">BASEERA</p>
          <p className="bsr-sm">See Beyond. Understand Deeper. Decide Smarter.</p>
        </div>

        <div>
          <span className="bsr-label">Platform</span>
          <ul className="bsr-lp-footer__links">
            {PLATFORM_LINKS.map((link) => (
              <li key={link.href}><a href={link.href}>{link.label}</a></li>
            ))}
          </ul>
        </div>

        <div>
          <span className="bsr-label">Project</span>
          <ul className="bsr-lp-footer__links">
            {PROJECT_LINKS.map((link) => (
              <li key={link.href}><a href={link.href} target="_blank" rel="noopener noreferrer">{link.label}</a></li>
            ))}
          </ul>
        </div>
      </div>

      <div className="bsr-lp-container bsr-lp-footer__bottom">
        <p className="bsr-caption">Academic and portfolio demonstration project. Built on the historical Olist Brazilian e-commerce dataset (Jan 2017–Aug 2018).</p>
      </div>
    </footer>
  );
}
