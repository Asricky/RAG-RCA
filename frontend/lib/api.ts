export type User = { id: string; email: string; name: string; role: "ADMIN" | "ANALYST" };

const base = process.env.NEXT_PUBLIC_API_URL || "";
const ACCESS_KEY = "rca_token";
const REFRESH_KEY = "rca_refresh";
const USER_KEY = "rca_user";
let refreshPromise: Promise<string> | null = null;

function browserStorage() {
  return typeof window === "undefined" ? null : window.sessionStorage;
}

function migrateLegacySession() {
  if (typeof window === "undefined") return;
  const session = browserStorage();
  if (!session || session.getItem(ACCESS_KEY)) return;
  for (const key of [ACCESS_KEY, REFRESH_KEY, USER_KEY]) {
    const value = window.localStorage.getItem(key);
    if (value) session.setItem(key, value);
    window.localStorage.removeItem(key);
  }
}

export function token() {
  migrateLegacySession();
  return browserStorage()?.getItem(ACCESS_KEY) || "";
}

export function refreshToken() {
  migrateLegacySession();
  return browserStorage()?.getItem(REFRESH_KEY) || "";
}

export function storedUser(): User | null {
  migrateLegacySession();
  const raw = browserStorage()?.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as User; } catch { return null; }
}

export function saveSession(payload: { access_token: string; refresh_token: string; user: User }) {
  const storage = browserStorage();
  storage?.setItem(ACCESS_KEY, payload.access_token);
  storage?.setItem(REFRESH_KEY, payload.refresh_token);
  storage?.setItem(USER_KEY, JSON.stringify(payload.user));
}

export function clearSession() {
  if (typeof window === "undefined") return;
  for (const storage of [window.sessionStorage, window.localStorage]) {
    for (const key of [ACCESS_KEY, REFRESH_KEY, USER_KEY]) storage.removeItem(key);
  }
}

async function renewAccessToken(): Promise<string> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const refresh = refreshToken();
    if (!refresh) throw new Error("Session expired");
    const response = await fetch(`${base}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Session expired");
    const payload = await response.json();
    browserStorage()?.setItem(ACCESS_KEY, payload.access_token);
    return payload.access_token as string;
  })().finally(() => { refreshPromise = null; });
  return refreshPromise;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const request = async (accessToken: string) => {
    const headers = new Headers(options.headers);
    if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${base}/api${path}`, { ...options, headers, cache: "no-store" });
  };

  let response = await request(token());
  if (response.status === 401 && !path.startsWith("/auth/")) {
    try { response = await request(await renewAccessToken()); }
    catch {
      clearSession();
      window.dispatchEvent(new Event("rca:auth-expired"));
      throw new Error("Sesi berakhir. Silakan masuk kembali.");
    }
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail || "Request failed");
  }
  return response.json();
}

export function fmt(date: string) {
  return new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(date));
}
