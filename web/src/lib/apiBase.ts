/** Local FastAPI default — override with ``VITE_API_URL`` in ``.env.development``. */
export function getApiBaseUrl(): string {
  const v = import.meta.env.VITE_API_URL;
  if (typeof v === "string" && v.trim() !== "") {
    return v.replace(/\/$/, "");
  }
  return "http://127.0.0.1:8787";
}
