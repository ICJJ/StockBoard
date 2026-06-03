const base = "/api/trading";
async function j(path, opts = {}) {
  const r = await fetch(base + path, {
    headers: { "content-type": "application/json" }, ...opts,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
  return r.json();
}
export const quizApi = {
  login: (username, password) =>
    j("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => j("/auth/logout", { method: "POST" }),
  me: () => j("/auth/me"),
  listUsers: () => j("/auth/users"),
  addUser: (b) => j("/auth/users", { method: "POST", body: JSON.stringify(b) }),
  patchUser: (u, b) => j(`/auth/users/${u}`, { method: "PATCH", body: JSON.stringify(b) }),
};
