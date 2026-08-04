import { NavLink, Outlet } from "react-router-dom";
import { APP_NAME } from "../utils/constants";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/sentiment", label: "Sentiment" },
  { to: "/customers", label: "Customers" },
  { to: "/sellers", label: "Sellers" },
  { to: "/products", label: "Products" },
  { to: "/geography", label: "Geography" },
  { to: "/model-info", label: "Model Info" },
];

export function Layout() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">{APP_NAME}</div>
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
    </div>
  );
}
