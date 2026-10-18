const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const token = sessionStorage.getItem("task-api-token");
  const headers = new Headers(options.headers || {});
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed (${response.status}).`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  checkAuth: (token) =>
    request("/api/auth/check", { headers: { Authorization: `Bearer ${token}` } }),
  summary: () => request("/api/dashboard/summary"),
  tasks: (startDate, endDate) =>
    request(`/api/tasks?startDate=${startDate}&endDate=${endDate}`),
  create: (task) => request("/api/tasks", { method: "POST", body: JSON.stringify(task) }),
  update: (id, task) =>
    request(`/api/tasks/${id}`, { method: "PUT", body: JSON.stringify(task) }),
  setStatus: (id, status) =>
    request(`/api/tasks/${id}/status?status=${status}`, { method: "PATCH" }),
  remove: (id) => request(`/api/tasks/${id}`, { method: "DELETE" }),
  report: (startDate, endDate, status) => {
    const params = new URLSearchParams({ startDate, endDate });
    if (status) params.set("status", status);
    return request(`/api/reports/tasks?${params}`);
  },
};
