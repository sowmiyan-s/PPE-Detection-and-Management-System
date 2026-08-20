export function getWsUrl(): string {
  if (typeof window === "undefined") return "ws://127.0.0.1:8000/ws";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const hostname = window.location.hostname || "127.0.0.1";

  // If frontend is running on non-8000 port (e.g. Vite dev server 3000), connect directly to backend port 8000
  if (window.location.port && window.location.port !== "8000") {
    return `${protocol}//${hostname}:8000/ws`;
  }
  return `${protocol}//${window.location.host}/ws`;
}
