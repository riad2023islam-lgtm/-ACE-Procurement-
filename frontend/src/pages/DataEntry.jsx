import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api.js";

const today = () => new Date().toISOString().slice(0, 10);
const KINDS = { purchase: "Purchase", consumption: "Consumption", inventory_count: "Inventory count" };

function useForm(initial) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [note, setNote] = useState("");
  return { values, setValues, errors, setErrors, note, setNote,
           bind: (k) => ({ value: values[k], onChange: (e) => setValues({ ...values, [k]: e.target.value }) }) };
}

function showErrors(form, err) {
  if (err instanceof ApiError) {
    const fe = {};
    for (const [k, v] of Object.entries(err.fields)) fe[k] = Array.isArray(v) ? v.join(" ") : String(v);
    form.setErrors(fe);
    form.setNote(Object.keys(fe).length ? "" : err.message);
  } else form.setNote("Unexpected error.");
}

// section: "inventory" (items, suppliers, prices, stock) | "transactions" (record form + records).
// query: text from the top-bar search box.
export default function DataEntry({ section = "all", query = "" }) {
  const showInventory = section !== "transactions";
  const showTransactions = section !== "inventory";
  const q = query.trim().toLowerCase();
  const [items, setItems] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [txs, setTxs] = useState([]);
  const [filter, setFilter] = useState("");

  const reload = useCallback(async () => {
    const [i, s, t] = await Promise.all([
      api("/items/"), api("/suppliers/"), api(`/transactions/${filter ? `?item=${filter}` : ""}`),
    ]);
    setItems(i); setSuppliers(s); setTxs(t);
  }, [filter]);
  useEffect(() => { reload().catch(() => {}); }, [reload]);

  // ---- forms -------------------------------------------------------------
  const itemForm = useForm({ name: "", unit: "pcs" });
  const supForm = useForm({ name: "", delivery_days: 3 });
  const priceForm = useForm({ item: "", supplier: "", unit_price: "", recorded_on: today() });
  const txForm = useForm({ item: "", kind: "purchase", quantity: "", unit_price: "", supplier: "", department: "", date: today() });

  async function submit(form, path, body, after) {
    form.setErrors({}); form.setNote("");
    try {
      await api(path, { method: "POST", body });
      form.setNote("Saved.");
      after?.();
      await reload();
    } catch (err) { showErrors(form, err); }
  }

  const addItem = (e) => { e.preventDefault();
    if (!itemForm.values.name.trim()) return itemForm.setErrors({ name: "Required." });
    submit(itemForm, "/items/", itemForm.values, () => itemForm.setValues({ name: "", unit: "pcs" })); };

  const addSupplier = (e) => { e.preventDefault();
    if (!supForm.values.name.trim()) return supForm.setErrors({ name: "Required." });
    submit(supForm, "/suppliers/", { ...supForm.values, delivery_days: Number(supForm.values.delivery_days) },
      () => supForm.setValues({ name: "", delivery_days: 3 })); };

  const addPrice = (e) => { e.preventDefault();
    const v = priceForm.values; const errs = {};
    if (!v.item) errs.item = "Choose an item.";
    if (!v.supplier) errs.supplier = "Choose a supplier.";
    if (!(Number(v.unit_price) > 0)) errs.unit_price = "Enter a price above 0.";
    if (Object.keys(errs).length) return priceForm.setErrors(errs);
    submit(priceForm, "/prices/", { ...v, item: Number(v.item), supplier: Number(v.supplier) });
  };

  const addTx = (e) => { e.preventDefault();
    const v = txForm.values; const errs = {};
    const isCount = v.kind === "inventory_count";
    if (!v.item) errs.item = "Choose an item.";
    const q = Number(v.quantity);
    if (v.quantity === "" || !Number.isInteger(q) || q < (isCount ? 0 : 1)) errs.quantity = isCount ? "Whole number, 0 or more." : "Whole number, 1 or more.";
    if (v.kind === "purchase" && !(Number(v.unit_price) > 0)) errs.unit_price = "Price required for a purchase.";
    if (!v.date) errs.date = "Required.";
    if (Object.keys(errs).length) return txForm.setErrors(errs);
    submit(txForm, "/transactions/", {
      item: Number(v.item), kind: v.kind, quantity: q, date: v.date, department: v.department,
      unit_price: v.kind === "purchase" ? v.unit_price : null,
      supplier: v.kind === "purchase" && v.supplier ? Number(v.supplier) : null,
    }, () => txForm.setValues({ ...v, quantity: "", unit_price: "" }));
  };

  async function editQty(t) {
    const input = window.prompt(`New quantity for ${t.item_name} (${KINDS[t.kind]}, ${t.date}):`, t.quantity);
    if (input === null) return;
    try {
      await api(`/transactions/${t.id}/`, { method: "PATCH", body: { quantity: Number(input) } });
      await reload();
    } catch (err) { window.alert(err.message); }
  }
  async function remove(t) {
    if (!window.confirm("Delete this record?")) return;
    try { await api(`/transactions/${t.id}/`, { method: "DELETE" }); await reload(); }
    catch (err) { window.alert(err.message); }
  }

  const Err = ({ f, k }) => (f.errors[k] ? <span className="err">{f.errors[k]}</span> : null);
  const Note = ({ f }) => (f.note ? <p className={f.note === "Saved." ? "ok" : "err box"}>{f.note}</p> : null);

  return (
    <div>
      {showInventory && <div className="grid">
        <form className="card" onSubmit={addItem} noValidate>
          <h3>Add item</h3>
          <label>Name<input {...itemForm.bind("name")} /><Err f={itemForm} k="name" /></label>
          <label>Unit<input {...itemForm.bind("unit")} /></label>
          <button className="primary">Add item</button><Note f={itemForm} />
        </form>

        <form className="card" onSubmit={addSupplier} noValidate>
          <h3>Add supplier</h3>
          <label>Name<input {...supForm.bind("name")} /><Err f={supForm} k="name" /></label>
          <label>Delivery time (days)<input type="number" min="0" {...supForm.bind("delivery_days")} /></label>
          <button className="primary">Add supplier</button><Note f={supForm} />
        </form>

        <form className="card" onSubmit={addPrice} noValidate>
          <h3>Record supplier price</h3>
          <label>Item<select {...priceForm.bind("item")}><option value="">Select…</option>
            {items.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}</select><Err f={priceForm} k="item" /></label>
          <label>Supplier<select {...priceForm.bind("supplier")}><option value="">Select…</option>
            {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select><Err f={priceForm} k="supplier" /></label>
          <label>Unit price<input type="number" step="0.01" {...priceForm.bind("unit_price")} /><Err f={priceForm} k="unit_price" /></label>
          <label>Date<input type="date" max={today()} {...priceForm.bind("recorded_on")} /></label>
          <button className="primary">Save price</button><Note f={priceForm} />
        </form>
      </div>}

      {showTransactions && <form className="card" onSubmit={addTx} noValidate>
        <h3>Record purchase / consumption / inventory count</h3>
        <div className="row">
          <label>Type<select {...txForm.bind("kind")}>
            {Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Item<select {...txForm.bind("item")}><option value="">Select…</option>
            {items.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}</select><Err f={txForm} k="item" /></label>
          <label>Quantity<input type="number" min="0" {...txForm.bind("quantity")} /><Err f={txForm} k="quantity" /></label>
          {txForm.values.kind === "purchase" && (<>
            <label>Unit price<input type="number" step="0.01" {...txForm.bind("unit_price")} /><Err f={txForm} k="unit_price" /></label>
            <label>Supplier<select {...txForm.bind("supplier")}><option value="">—</option>
              {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
          </>)}
          {txForm.values.kind === "consumption" && (
            <label>Department<input {...txForm.bind("department")} /></label>)}
          <label>Date<input type="date" max={today()} {...txForm.bind("date")} /><Err f={txForm} k="date" /></label>
        </div>
        <button className="primary">Save record</button><Note f={txForm} />
      </form>}

      {showInventory && <div className="card">
        <h3>Current stock</h3>
        <table><thead><tr><th>Item</th><th>Unit</th><th className="num">Current stock</th></tr></thead>
          <tbody>{items.filter((i) => !q || i.name.toLowerCase().includes(q)).map((i) => (<tr key={i.id}><td>{i.name}</td><td>{i.unit}</td><td className="num">{i.current_stock}</td></tr>))}
            {!items.length && <tr><td colSpan="3" className="muted">No items yet.</td></tr>}</tbody></table>
        {suppliers.length > 0 && <p className="muted" style={{ marginTop: 12 }}>
          Suppliers: {suppliers.map((s) => `${s.name} (${s.delivery_days}d)`).join(" · ")}</p>}
      </div>}

      {showTransactions && <div className="card">
        <h3>Records <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All items</option>{items.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}</select></h3>
        <table><thead><tr><th>Date</th><th>Item</th><th>Type</th><th className="num">Qty</th><th className="num">Unit price</th><th>Supplier / Dept</th><th></th></tr></thead>
          <tbody>{txs.filter((t) => !q || [t.item_name, t.supplier_name, t.department, KINDS[t.kind]]
              .some((s) => (s || "").toLowerCase().includes(q))).slice(0, 50).map((t) => (
            <tr key={t.id}><td>{t.date}</td><td>{t.item_name}</td><td>{KINDS[t.kind]}</td>
              <td className="num">{t.quantity}</td><td className="num">{t.unit_price ?? "—"}</td>
              <td>{t.supplier_name || t.department || "—"}</td>
              <td><button className="link" onClick={() => editQty(t)}>Edit qty</button>
                  <button className="link danger" onClick={() => remove(t)}>Delete</button></td></tr>))}
            {!txs.length && <tr><td colSpan="7" className="muted">No records yet.</td></tr>}</tbody></table>
        {txs.length > 50 && <p className="muted">Showing the latest 50 of {txs.length}.</p>}
      </div>}
    </div>
  );
}
