import { useEffect, useState } from "react";
import { api } from "../api.js";

// Simple SVG chart: history bars, then the forecast bar with its error range.
function Chart({ history, forecast }) {
  const W = 720, H = 280, PAD = { l: 48, r: 16, t: 16, b: 48 };
  const bars = [...history.map((h) => ({ label: h.month.slice(2), value: h.quantity })),
                { label: "next", value: forecast.forecast, forecast: true }];
  const max = Math.max(forecast.upper, ...history.map((h) => h.quantity)) * 1.1 || 1;
  const bw = (W - PAD.l - PAD.r) / bars.length;
  const y = (v) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / max);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Monthly consumption and forecast">
      {[0, 0.25, 0.5, 0.75, 1].map((p) => (
        <g key={p}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(max * p)} y2={y(max * p)} className="grid-line" />
          <text x={PAD.l - 6} y={y(max * p) + 4} textAnchor="end" className="axis">{Math.round(max * p)}</text>
        </g>
      ))}
      {bars.map((b, i) => {
        const x = PAD.l + i * bw + bw * 0.15;
        return (
          <g key={i}>
            <rect x={x} y={y(b.value)} width={bw * 0.7} height={y(0) - y(b.value)}
                  className={b.forecast ? "bar forecast" : "bar"} />
            <text x={x + bw * 0.35} y={H - PAD.b + 16} textAnchor="middle" className="axis">{b.label}</text>
            {b.forecast && (<g>
              <line x1={x + bw * 0.35} x2={x + bw * 0.35} y1={y(forecast.upper)} y2={y(forecast.lower)} className="whisker" />
              <line x1={x + bw * 0.2} x2={x + bw * 0.5} y1={y(forecast.upper)} y2={y(forecast.upper)} className="whisker" />
              <line x1={x + bw * 0.2} x2={x + bw * 0.5} y1={y(forecast.lower)} y2={y(forecast.lower)} className="whisker" />
            </g>)}
          </g>
        );
      })}
    </svg>
  );
}

const MODEL_LABEL = {
  moving_average: "3-month moving average (ML model selected by backtest)",
  linear_trend: "Linear trend regression (ML model selected by backtest)",
  simple_average_fallback: "Simple average of recent months (cold-start fallback)",
};

export default function Forecast() {
  const [items, setItems] = useState([]);
  const [itemId, setItemId] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { api("/items/").then(setItems).catch((e) => setError(e.message)); }, []);

  async function load(id) {
    setItemId(id); setResult(null); setError("");
    if (!id) return;
    setLoading(true);
    try { setResult(await api(`/forecast/?item=${id}`)); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  const f = result?.forecast;
  return (
    <div className="card">
      <h3>Next-month demand forecast</h3>
      <label>Item
        <select value={itemId} onChange={(e) => load(e.target.value)}>
          <option value="">Select an item…</option>
          {items.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
        </select>
      </label>
      {loading && <p className="muted">Calculating…</p>}
      {error && <p className="err box">{error}</p>}
      {result && (<>
        <div className="stats">
          <div><span className="muted">Forecast</span><strong>{f.forecast} {result.item.unit}</strong></div>
          <div><span className="muted">Error range (~80%)</span><strong>{f.lower} – {f.upper}</strong></div>
          <div><span className="muted">Backtest MAE</span><strong>{f.mae ?? "n/a"}</strong></div>
          <div><span className="muted">Confidence</span>
            <strong className={f.confidence === "low" ? "badge warn" : "badge good"}>{f.confidence}</strong></div>
        </div>
        <p className="muted">Model used: {MODEL_LABEL[f.model]} · based on {f.history_months} month(s) of history.</p>
        {f.confidence === "low" && <p className="err box">Low confidence: fewer than 6 months of history, so a simple average was used.</p>}
        <Chart history={result.history} forecast={f} />
        <p className="muted">Bars: monthly consumption. Last bar: forecast with error range.</p>
      </>)}
    </div>
  );
}
