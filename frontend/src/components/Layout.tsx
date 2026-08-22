import { useEffect, useRef, useState } from "react";
import type { ComponentType, SVGProps } from "react";
import { createPortal } from "react-dom";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Logo } from "./Logo";
import { Modal } from "./ui/Modal";
import { IconButton } from "./ui/IconButton";
import { DemoDataBadge } from "./ui/DemoDataBadge";
import {
  AnalyzerIcon, CollapseIcon, CustomersIcon, ExternalLinkIcon, GeographyIcon,
  MenuIcon, ModelIcon, OverviewIcon, ProductsIcon, SellersIcon, UploadIcon,
} from "./app-shell/icons";
import { APP_NAME, APP_TAGLINE } from "../utils/constants";
import "../styles/app-shell.css";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;
interface NavItem { to: string; label: string; icon: IconComponent; end?: boolean }
interface NavGroup { label: string; items: NavItem[] }

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Intelligence",
    items: [
      { to: "/", label: "Overview", icon: OverviewIcon, end: true },
      { to: "/sentiment", label: "Review Analyzer", icon: AnalyzerIcon },
      { to: "/batch-upload", label: "Batch Upload", icon: UploadIcon },
    ],
  },
  {
    label: "Marketplace",
    items: [
      { to: "/customers", label: "Customers", icon: CustomersIcon },
      { to: "/sellers", label: "Sellers", icon: SellersIcon },
      { to: "/products", label: "Products", icon: ProductsIcon },
      { to: "/geography", label: "Geography", icon: GeographyIcon },
    ],
  },
  {
    label: "System",
    items: [{ to: "/model-info", label: "Model", icon: ModelIcon }],
  },
];

const PAGE_META: Record<string, { title: string; context: string }> = {
  "/": { title: "Overview", context: "Marketplace performance across orders, revenue, customers, and reviews." },
  "/sentiment": { title: "Review Analyzer", context: "Score a single review's sentiment, aspects, and confidence." },
  "/batch-upload": { title: "Batch Upload", context: "Analyze a CSV of reviews in one pass." },
  "/customers": { title: "Customers", context: "Spend, repeat-purchase, and RFM segmentation." },
  "/sellers": { title: "Sellers", context: "Seller performance and delivery reliability." },
  "/products": { title: "Products", context: "Category performance by revenue." },
  "/geography": { title: "Geography", context: "State-level delivery performance." },
  "/model-info": { title: "Model", context: "Loaded model status and details." },
};

/**
 * Collapsed-rail-only variant: adds `aria-label` (a reliable accessible
 * name, unlike relying on `title`) and a portaled tooltip shown on hover
 * *and* keyboard focus (native `title` tooltips generally don't appear on
 * focus). See the `.bsr-app-sidebar-tooltip` comment in app-shell.css for
 * why this has to be a portal rather than a plain CSS `::after`.
 */
function CollapsedNavLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const linkRef = useRef<HTMLAnchorElement>(null);
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number } | null>(null);

  function show() {
    const rect = linkRef.current?.getBoundingClientRect();
    if (rect) setTooltipPos({ top: rect.top + rect.height / 2, left: rect.right + 10 });
  }
  function hide() {
    setTooltipPos(null);
  }

  return (
    <>
      <NavLink
        ref={linkRef}
        to={item.to}
        end={item.end}
        onClick={onNavigate}
        aria-label={item.label}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        className={({ isActive }) => (isActive ? "bsr-app-nav-link bsr-app-nav-link--active" : "bsr-app-nav-link")}
      >
        <item.icon className="bsr-app-nav-link__icon" aria-hidden="true" />
      </NavLink>
      {tooltipPos &&
        createPortal(
          <span className="bsr-app-sidebar-tooltip" style={{ top: tooltipPos.top, left: tooltipPos.left }}>
            {item.label}
          </span>,
          document.body,
        )}
    </>
  );
}

function NavList({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  return (
    <>
      {NAV_GROUPS.map((group) => (
        <div className="bsr-app-sidebar__group" key={group.label}>
          {!collapsed && <span className="bsr-app-sidebar__group-label bsr-label">{group.label}</span>}
          {group.items.map((item) =>
            collapsed ? (
              <CollapsedNavLink key={item.to} item={item} onNavigate={onNavigate} />
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                className={({ isActive }) => (isActive ? "bsr-app-nav-link bsr-app-nav-link--active" : "bsr-app-nav-link")}
              >
                <item.icon className="bsr-app-nav-link__icon" aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            ),
          )}
        </div>
      ))}
    </>
  );
}

export function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  // A route change from inside the drawer should close it -- otherwise the
  // panel stays open over the newly-navigated page.
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const meta = PAGE_META[location.pathname] ?? { title: APP_NAME, context: APP_TAGLINE };

  return (
    <div className={collapsed ? "bsr-app bsr-app--collapsed" : "bsr-app"}>
      <a href="#main-content" className="bsr-app-skip-link">
        Skip to content
      </a>

      <aside className="bsr-app-sidebar">
        <div className="bsr-app-sidebar__brand">
          <NavLink to="/" className="bsr-app-sidebar__brand-link">
            <Logo size={32} />
            {!collapsed && <span className="bsr-app-sidebar__wordmark">{APP_NAME}</span>}
          </NavLink>
          <IconButton
            icon={<CollapseIcon style={{ transform: collapsed ? "rotate(180deg)" : undefined, transition: "transform var(--bsr-duration-base) var(--bsr-ease-standard)" }} />}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            variant="ghost"
            size="sm"
            className="bsr-app-sidebar__collapse-btn"
            onClick={() => setCollapsed((c) => !c)}
          />
        </div>

        <nav className="bsr-app-sidebar__nav" aria-label="Primary">
          <NavList collapsed={collapsed} />
        </nav>

        <div className="bsr-app-sidebar__foot">
          <a href="/landing-preview" className="bsr-app-sidebar__landing-link" title={collapsed ? "View landing page" : undefined}>
            <ExternalLinkIcon className="bsr-app-nav-link__icon" aria-hidden="true" />
            {!collapsed && <span>View landing page</span>}
          </a>
          {!collapsed && (
            <div className="bsr-app-sidebar__status">
              <DemoDataBadge kind="historical" label="Historical Olist data" />
              <p className="bsr-caption">Jan 2017 – Aug 2018 · Demonstration project</p>
            </div>
          )}
        </div>
      </aside>

      <div className="bsr-app-body">
        <header className="bsr-app-header">
          <IconButton
            icon={<MenuIcon />}
            aria-label="Open navigation menu"
            variant="ghost"
            className="bsr-app-header__menu-btn"
            onClick={() => setMobileOpen(true)}
          />
          <div className="bsr-app-header__title">
            <h1 className="bsr-h5">{meta.title}</h1>
            <p className="bsr-caption bsr-app-header__context">{meta.context}</p>
          </div>
          <DemoDataBadge kind="historical" label="Historical Olist data · Jan 2017 – Aug 2018" className="bsr-app-header__badge" />
        </header>

        <main className="bsr-app-main" id="main-content">
          <Outlet />
        </main>

        <footer className="bsr-app-footer">
          <span>{APP_NAME} · {APP_TAGLINE}</span>
        </footer>
      </div>

      <Modal
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        title={`${APP_NAME} navigation`}
        hideHeader
        closeOnBackdropClick
        className="bsr-app-drawer"
      >
        <div className="bsr-app-drawer__head">
          <span className="bsr-app-drawer__brand">
            <Logo size={30} />
            <span className="bsr-app-sidebar__wordmark">{APP_NAME}</span>
          </span>
          <IconButton icon="✕" aria-label="Close menu" variant="ghost" onClick={() => setMobileOpen(false)} />
        </div>

        <nav className="bsr-app-drawer__nav" aria-label="Primary">
          <NavList collapsed={false} onNavigate={() => setMobileOpen(false)} />
        </nav>

        <a href="/landing-preview" className="bsr-app-sidebar__landing-link">
          <ExternalLinkIcon className="bsr-app-nav-link__icon" aria-hidden="true" />
          <span>View landing page</span>
        </a>
      </Modal>
    </div>
  );
}
