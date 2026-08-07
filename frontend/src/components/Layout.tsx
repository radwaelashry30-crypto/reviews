import { NavLink, Outlet } from "react-router-dom";
import { Logo } from "./Logo";
import { APP_NAME, APP_TAGLINE } from "../utils/constants";

const NAV_ITEMS = [
  { to: "/", label: "Overview" },
  { to: "/sentiment", label: "Review Analyzer" },
  { to: "/customers", label: "Customers" },
  { to: "/sellers", label: "Sellers" },
  { to: "/products", label: "Products" },
  { to: "/geography", label: "Geography" },
  { to: "/model-info", label: "Model" },
];

export function Layout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">
          <NavLink to="/" className="brand-link">
            <Logo />
            <div className="brand-text">
              <span className="brand-name">{APP_NAME}</span>
              <span className="brand-tagline">{APP_TAGLINE}</span>
            </div>
          </NavLink>
        </div>
        <nav className="app-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="app-content">
        <Outlet />
      </main>
      <footer className="app-footer">
        <span>{APP_NAME} · Sentiment intelligence built on real Olist marketplace data</span>
      </footer>
    </div>
  );
}
