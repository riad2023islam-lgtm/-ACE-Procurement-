import { useEffect, useState } from "react";
import { api } from "../api.js";
import Icon from "../icons.jsx";

const money = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 }));

function Kpi({ label, value, note, tone, icon, color }) {
  return (
    <div className="kpi">
      <span className={`kpi-icon ${color}`}><Icon name={icon} /></span>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {note && <span className={`kpi-note ${tone || ""}`}>{note}</span>}
    </div>
  );
}

// Solid line = actual monthly consumption (all items). Dashed segment = next-month forecast.
function DemandChart({ actual, next }) {
  const W = 720, H = 260, P = { l: 48, r: 24, t: 20, b: 36 };
  const pts = actual.map((a) => ({ label: a.month.slice(2), v: a.quantity }));
  const all = [...pts, { label: "next", v: next.forecast, forecast: true }];
  const max = Math.max(...all.map((p) => p.v), 1) * 1.15;
  const x = (i) => P.l + ((W - P.l - P.r) * i) / Math.max(all.length - 1, 1);
  const y = (v) => P.t + (H - P.t - P.b) * (1 - v / max);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.v)}`).join(" ");
  const last = pts.length - 1;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Monthly demand and next-month forecast">
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}>
          <line x1={P.l} x2={W - P.r} y1={y(max * f)} y2={y(max * f)} className="grid-line" strokeDasharray="3 4" />
          <text x={P.l - 8} y={y(max * f) + 4} textAnchor="end" className="axis">{Math.round(max * f)}</text>
        </g>
      ))}
      {all.map((p, i) => (
        <text key={i} x={x(i)} y={H - 10} textAnchor="middle" className="axis">{p.label}</text>
      ))}
      {last >= 0 && <path d={`M${x(last)},${y(pts[last].v)} L${x(all.length - 1)},${y(next.forecast)}`}
                          className="line-forecast" fill="none" />}
      <path d={line} className="line-actual" fill="none" />
      {pts.map((p, i) => <circle key={i} cx={x(i)} cy={y(p.v)} r="4" className="dot" />)}
      <circle cx={x(all.length - 1)} cy={y(next.forecast)} r="5" className="dot forecast" />
    </svg>
  );
}

const SEV = { high: "HIGH", medium: "MEDIUM", low: "LOW" };

export default function Dashboard({ onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api("/dashboard/").then(setData).catch((e) => setError(e.message)); }, []);

  if (error) return <p className="err box">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;

  const { kpis, demand, alerts, recent_purchases: recent } = data;
  const change = kpis.spend_change_pct;

  return (
    <div>
      <div className="kpis">
        <Kpi icon="card" color="blue" label="Total spend (last 6 months)" value={money(kpis.total_spend)}
             note={change === null ? "no earlier period to compare" : `${change > 0 ? "↗" : "↘"} ${Math.abs(change)}% vs previous 6 months`}
             tone={change === null ? "" : change > 0 ? "up" : "down"} />
        <Kpi icon="cart" color="purple" label="Purchase records" value={kpis.purchase_records} note="last 6 months" />
        <Kpi icon="box" color="green" label="Active suppliers" value={kpis.active_suppliers} note={`${kpis.items_tracked} items tracked`} />
        <Kpi icon="trend" color="orange" label="Items at risk" value={kpis.items_at_risk}
             note={`${kpis.shortage_items} shortage risk`} tone={kpis.shortage_items ? "down" : "up"} />
      </div>

      <div className="card">
        <div className="card-head">
          <div><h3>Demand forecast</h3><p className="muted">Monthly consumption across all items, and next month's forecast</p></div>
          <div className="legend"><span><i className="dot-sample actual" />Actual</span><span><i className="dot-sample forecast" />Forecast</span></div>
        </div>
        {demand.actual.length
          ? <DemandChart actual={demand.actual} next={demand.next_month} />
          : <p className="muted">No consumption history yet. Record consumption under Transactions.</p>}
      </div>

      <div className="card">
        <div className="card-head"><div><h3>Risk alerts</h3><p className="muted">Items requiring attention</p></div>
          <span className="count">{alerts.length}</span></div>
        {alerts.length === 0 && <p className="muted">No alerts.</p>}
        {alerts.map((a, i) => (
          <div className="alert-row" key={i}>
            <span className={`alert-icon ${a.severity}`}><Icon name="alert" size={18} /></span>
            <div><strong>{a.title}</strong> <span className={`sev ${a.severity}`}>{SEV[a.severity]}</span>
              <p className="muted">{a.detail}</p></div>
          </div>
        ))}
        <button className="wide-btn" onClick={() => onNavigate?.("recs")}>View all recommendations</button>
      </div>

      <div className="card">
        <div className="card-head"><div><h3>Recent purchases</h3><p className="muted">Latest purchase records in your organization</p></div>
          <button className="link" onClick={() => onNavigate?.("transactions")}>View all records</button></div>
        <table>
          <thead><tr><th>DATE</th><th>ITEM</th><th>SUPPLIER</th><th className="num">QTY</th><th className="num">TOTAL</th></tr></thead>
          <tbody>
            {recent.map((r) => (
              <tr key={r.id}><td>{r.date}</td><td><strong>{r.item}</strong></td><td>{r.supplier || "—"}</td>
                <td className="num">{r.quantity}</td><td className="num">{money(r.total)}</td></tr>
            ))}
            {!recent.length && <tr><td colSpan="5" className="muted">No purchases yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
