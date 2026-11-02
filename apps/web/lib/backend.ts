import "server-only";

const DEFAULT_API = "http://127.0.0.1:6969";

export class BackendConnectionError extends Error {}

function apiConfiguration(): string {
  const configured = process.env.GRAPHIV_API_URL?.trim();
  const url = new URL(configured || DEFAULT_API);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
    throw new Error("Unsupported research server configuration");
  }
  url.search = "";
  url.hash = "";
  return url.href.replace(/\/$/, "");
}

/** Only server-owned paths are passed here; the browser never supplies a backend URL. */
export async function backendRequest(path: string, init: RequestInit = {}, timeout = 3_000): Promise<Response> {
  const base = apiConfiguration();
  const token = process.env.GRAPHIV_API_TOKEN?.trim();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  try {
    return await fetch(`${base}${path}`, {
      ...init,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(timeout),
      headers,
    });
  } catch {
    throw new BackendConnectionError("The research server could not be reached");
  }
}
