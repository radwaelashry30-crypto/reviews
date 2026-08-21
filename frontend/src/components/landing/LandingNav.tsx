import { useEffect, useState } from "react";
import { Button } from "../ui/Button";
import { IconButton } from "../ui/IconButton";
import { Modal } from "../ui/Modal";

const LINKS = [
  { href: "#platform", label: "Platform" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "#insights", label: "Insights" },
  { href: "#responsible-ai", label: "Responsible AI" },
];

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    let frame = 0;
    function handleScroll() {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        setScrolled(window.scrollY > 24);
        frame = 0;
      });
    }
    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header className={scrolled ? "bsr-lp-nav bsr-lp-nav--scrolled" : "bsr-lp-nav"}>
      <div className="bsr-lp-container bsr-lp-nav__inner">
        <a href="#top" className="bsr-lp-nav__brand">
          <img src="/assets/baseera-logo-mark.png" alt="Baseera" width={36} height={36} className="bsr-lp-nav__mark" />
          <span className="bsr-lp-nav__wordmark">BASEERA</span>
        </a>

        <nav className="bsr-lp-nav__links" aria-label="Primary">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href} className="bsr-lp-nav__link">
              {link.label}
            </a>
          ))}
        </nav>

        <div className="bsr-lp-nav__actions">
          <Button variant="secondary" to="/">
            Open Dashboard
          </Button>
          <Button variant="primary" to="/sentiment">
            Analyze Reviews
          </Button>
        </div>

        <IconButton
          icon="≡"
          aria-label="Open menu"
          variant="ghost"
          className="bsr-lp-nav__menu-btn"
          onClick={() => setMenuOpen(true)}
        />
      </div>

      <Modal open={menuOpen} onClose={() => setMenuOpen(false)} title="Menu" closeOnBackdropClick>
        <nav className="bsr-lp-mobile-nav" aria-label="Primary">
          {LINKS.map((link) => (
            <a key={link.href} href={link.href} className="bsr-lp-mobile-nav__link" onClick={() => setMenuOpen(false)}>
              {link.label}
            </a>
          ))}
        </nav>
        <div className="bsr-lp-mobile-nav__actions">
          <Button variant="secondary" to="/" fullWidth onClick={() => setMenuOpen(false)}>
            Open Dashboard
          </Button>
          <Button variant="primary" to="/sentiment" fullWidth onClick={() => setMenuOpen(false)}>
            Analyze Reviews
          </Button>
        </div>
      </Modal>
    </header>
  );
}
