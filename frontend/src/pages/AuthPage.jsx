import { useState } from "react";
import { api, ApiError } from "../api.js";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateRegister(f) {
  const e = {};
  if (f.organization_name.trim().length < 3) e.organization_name = "At least 3 characters.";
  if (!/^[\w.@+-]{3,150}$/.test(f.username)) e.username = "3+ characters: letters, digits and . @ + - _ only.";
  if (!EMAIL_RE.test(f.email)) e.email = "Enter a valid email address.";
  if (f.password.length < 8) e.password = "At least 8 characters.";
  else if (/^\d+$/.test(f.password)) e.password = "Password cannot be only digits.";
  if (f.password2 !== f.password) e.password2 = "Passwords do not match.";
  return e;
}

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    organization_name: "", username: "", email: "", password: "", password2: "",
  });
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k) => (ev) => setForm({ ...form, [k]: ev.target.value });

  async function submit(ev) {
    ev.preventDefault();
    setMessage("");
    let local = {};
    if (mode === "register") local = validateRegister(form);
    else {
      if (!form.username) local.username = "Required.";
      if (!form.password) local.password = "Required.";
    }
    setErrors(local);
    if (Object.keys(local).length) return;

    setBusy(true);
    try {
      const body = mode === "login"
        ? { username: form.username, password: form.password }
        : form;
      const data = await api(mode === "login" ? "/auth/login/" : "/auth/register/", { method: "POST", body });
      onAuth(data);
    } catch (err) {
      if (err instanceof ApiError) {
        const fe = {};
        for (const [k, v] of Object.entries(err.fields)) fe[k] = Array.isArray(v) ? v.join(" ") : String(v);
        setErrors(fe);
        if (!Object.keys(fe).length) setMessage(err.message);
      } else setMessage("Unexpected error.");
    } finally {
      setBusy(false);
    }
  }

  const field = (key, label, type = "text", autoComplete) => (
    <label>
      {label}
      <input type={type} value={form[key]} onChange={set(key)} autoComplete={autoComplete} />
      {errors[key] && <span className="err">{errors[key]}</span>}
    </label>
  );

  return (
    <div className="auth">
      <h1>ACE Procurement Intelligence</h1>
      <p className="muted">AI-assisted procurement planning for educational institutions</p>
      <div className="card">
        <div className="switch">
          <button className={mode === "login" ? "tab active" : "tab"} onClick={() => { setMode("login"); setErrors({}); }}>
            Log in
          </button>
          <button className={mode === "register" ? "tab active" : "tab"} onClick={() => { setMode("register"); setErrors({}); }}>
            Register organization
          </button>
        </div>
        <form onSubmit={submit} noValidate>
          {mode === "register" && field("organization_name", "Organization name")}
          {field("username", "Username", "text", "username")}
          {mode === "register" && field("email", "Email", "email", "email")}
          {field("password", "Password", "password", mode === "login" ? "current-password" : "new-password")}
          {mode === "register" && field("password2", "Confirm password", "password", "new-password")}
          {message && <p className="err box">{message}</p>}
          <button className="primary" disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Create organization & account"}
          </button>
        </form>
      </div>
    </div>
  );
}
