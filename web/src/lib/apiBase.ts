/**
 * Local FastAPI base URL.
 *
 * Defaults to the **same hostname** as the Vite page (``localhost`` vs ``127.0.0.1``)
 * so the browser does not treat the API as a different site. Override with
 * ``VITE_API_URL`` in ``.env.development`` if needed.
 */
export function getApiBaseUrl(): string {
  const v = import.meta.env.VITE_API_URL;
  if (typeof v === "string" && v.trim() !== "") {
    return v.replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.location?.hostname) {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8787`;
  }
  return "http://127.0.0.1:8787";
}
