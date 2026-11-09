import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";

const RISK = { shortage: "Shortage risk", overstock: "Overstock risk", ok: "OK" };
const RISK_CLASS = { shortage: "badge bad", overstock: "badge warn", ok: "badge good" };
const TREND = { up: "↑", down: "↓", stable: "→", unknown: "" };

export default function Recommendations() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(null);

  useEffect(() => { api("/recommendations/").then(setData).catch((e) => setError(e.message)); }, []);

  if (error) return <p className="err box">{error}</p>;
  if (!data) return <p className="muted">Loading recommendations…</p>;

  return (
    <div className="card">
      <h3>Procurement recommendations</h3>
      <p className="muted">
        Recommendations only: nothing is purchased automatically. Click a row to see the reasoning.
      </p>
      <table>
        <thead><tr><th>Item</th><th>Risk</th><th className="num">Stock</th><th className="num">Forecast</th>
          <th className="num">Buy qty</th><th>Order by</th><th>Supplier</th><th>Price trend</th></tr></thead>
        <tbody>
          {data.recommendations.map((r) => (<Fragment key={r.item_id}>
            <tr className="click" onClick={() => setOpen(open === r.item_id ? null : r.item_id)}>
              <td>{r.item}</td>
              <td><span className={RISK_CLASS[r.risk]}>{RISK[r.risk]}</span></td>
              <td className="num">{r.current_stock}</td>
              <td className="num">{r.forecast.forecast}{r.forecast.confidence === "low" ? " *" : ""}</td>
              <td className="num"><strong>{r.recommended_quantity}</strong> {r.unit}</td>
              <td>{r.order_by ?? "—"}</td>
              <td>{r.supplier ? `${r.supplier.name} (${r.supplier.unit_price})` : "No price data"}</td>
              <td>{TREND[r.price_trend.direction]} {r.price_trend.change_pct !== null ? `${r.price_trend.change_pct}%` : ""}</td>
            </tr>
            {open === r.item_id && (
              <tr className="why"><td colSpan="8">
                <strong>Why this recommendation</strong>
                <ul>{r.reasoning.map((line, i) => <li key={i}>{line}</li>)}</ul>
              </td></tr>
            )}
          </Fragment>))}
          {!data.recommendations.length && <tr><td colSpan="8" className="muted">No items have consumption history yet.</td></tr>}
        </tbody>
      </table>
      <p className="muted">* low confidence (fewer than 6 months of history).</p>
      {data.items_without_history.length > 0 &&
        <p className="muted">No history yet for: {data.items_without_history.join(", ")}.</p>}
    </div>
  );
}
