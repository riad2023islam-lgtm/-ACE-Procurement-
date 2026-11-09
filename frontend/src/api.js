// Small fetch wrapper: adds the auth token and turns DRF error bodies into readable text.

const KEY = "ace_token";

export function getToken() {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
export function setToken(token) {
  try { token ? localStorage.setItem(KEY, token) : localStorage.removeItem(KEY); } catch { /* ignore */ }
}

function flatten(body) {
  if (!body) return ["Something went wrong."];
  if (typeof body === "string") return [body];
  if (body.detail) return [String(body.detail)];
  return Object.entries(body).flatMap(([field, msgs]) =>
    (Array.isArray(msgs) ? msgs : [String(msgs)]).map((m) => `${field}: ${m}`)
  );
}

export class ApiError extends Error {
  constructor(status, messages, fields) {
    super(messages.join(" "));
    this.status = status;
    this.messages = messages;
    this.fields = fields || {};
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Token ${token}`;

  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new ApiError(0, ["Cannot reach the server. Is the Django backend running?"]);
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON body */ }
  if (!res.ok) {
    const fields = data && typeof data === "object" && !data.detail ? data : {};
    throw new ApiError(res.status, flatten(data), fields);
  }
  return data;
}
