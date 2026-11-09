import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api.js";
import Icon from "./icons.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import DataEntry from "./pages/DataEntry.jsx";
import Forecast from "./pages/Forecast.jsx";
import Recommendations from "./pages/Recommendations.jsx";

const ROLE_LABEL = { admin: "Administrator", manager: "Manager", store_officer: "Store Officer" };

// Sidebar entries. `analyse` pages are only for admin/manager (SRS NFR4).
const PAGES = [
  { id: "dashboard", label: "Dashboard", icon: "grid", analyse: true,
    title: "Procurement overview", sub: "Monitor spend, inventory demand and supplier activity." },
  { id: "inventory", label: "Inventory", icon: "box",
    title: "Inventory", sub: "Items, suppliers, supplier prices and current stock." },
  { id: "transactions", label: "Transactions", icon: "card",
    title: "Transactions", sub: "Record purchases, consumption and stock counts (FR3)." },
  { id: "forecast", label: "Demand forecast", icon: "forecast", analyse: true,
    title: "Demand forecast", sub: "Next-month demand per item with an error range (FR9)." },
  { id: "recs", label: "Recommendations", icon: "file", analyse: true,
    title: "Procurement recommendations", sub: "What to buy, when and from whom, with reasons (FR11)." },
];

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(!!getToken());
  const [page, setPage] = useState(null);
  const [query, setQuery] = useState("");
  const [help, setHelp] = useState(false);

  // Restore the session if a token is stored.
  useEffect(() => {
    if (!getToken()) return;
    api("/auth/me/")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setChecking(false));
  }, []);

  function onAuth({ token, user }) {
    setToken(token);
    setUser(user);
    setPage(null);
  }

  async function logout() {
    try { await api("/auth/logout/", { method: "POST" }); } catch { /* token may already be invalid */ }
    setToken(null);
    setUser(null);
    setQuery("");
  }

  if (checking) return <p className="center muted">Loading…</p>;
  if (!user) return <AuthPage onAuth={onAuth} />;

  const canAnalyse = user.role === "admin" || user.role === "manager";
  const visible = PAGES.filter((p) => !p.analyse || canAnalyse);
  const current = visible.find((p) => p.id === page) || visible[0];
  const initials = user.username.slice(0, 2).toUpperCase();
  const today = new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
  const go = (id) => { setPage(id); setQuery(""); };
  const searchable = current.id === "inventory" || current.id === "transactions";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo"><Icon name="grid" size={20} /></span>
          <div><strong>ACE Procure</strong><small>INTELLIGENCE</small></div>
        </div>
        <div className="side-label">WORKSPACE</div>
        <nav>
          {visible.map((p) => (
            <button key={p.id} className={current.id === p.id ? "nav-item active" : "nav-item"}
                    onClick={() => go(p.id)}>
              <Icon name={p.icon} />{p.label}
            </button>
          ))}
        </nav>
        <div className="side-user">
          <span className="avatar">{initials}</span>
          <div className="who"><strong>{user.username}</strong><small>{ROLE_LABEL[user.role]}</small></div>
          <button className="icon-btn" onClick={logout} title="Log out" aria-label="Log out">
            <Icon name="logout" size={18} />
          </button>
        </div>
      </aside>

      <div className="content">
        <div className="topbar">
          <label className="search">
            <Icon name="search" size={18} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} disabled={!searchable}
                   placeholder={searchable ? "Search items, suppliers, records…" : "Search is available in Inventory and Transactions"} />
          </label>
          <div className="top-actions">
            <button className="icon-btn" title="Help" aria-label="Help" onClick={() => setHelp(!help)}>
              <Icon name="help" />
            </button>
            <button className="icon-btn" title="Risk alerts" aria-label="Risk alerts"
                    onClick={() => canAnalyse && go("dashboard")}>
              <Icon name="bell" />{canAnalyse && <span className="bell-dot" />}
            </button>
            <span className="avatar big" title={user.organization.name}>{initials}</span>
          </div>
          {help && (
            <div className="popover" role="dialog">
              <strong>{user.organization.name}</strong>
              <p className="muted">Record data under Inventory and Transactions. Managers get the dashboard,
                forecasts and recommendations. Click a recommendation row to see why it was suggested.</p>
            </div>
          )}
        </div>
        <main>
          <div className="page-head">
            <div>
              <div className="date">{today}</div>
              <h1 className="page-title">{current.title}</h1>
              <p className="muted page-sub">{current.sub}</p>
            </div>
          </div>
          {current.id === "dashboard" && <Dashboard onNavigate={go} />}
          {current.id === "inventory" && <DataEntry section="inventory" query={query} />}
          {current.id === "transactions" && <DataEntry section="transactions" query={query} />}
          {current.id === "forecast" && <Forecast />}
          {current.id === "recs" && <Recommendations />}
        </main>
      </div>
    </div>
  );
}
