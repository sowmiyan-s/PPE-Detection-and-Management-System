import "./lib/error-capture";

import { consumeLastCapturedError } from "./lib/error-capture";
import { renderErrorPage } from "./lib/error-page";

type ServerEntry = {
  fetch: (request: Request, env: unknown, ctx: unknown) => Promise<Response> | Response;
};

let serverEntryPromise: Promise<ServerEntry> | undefined;

async function getServerEntry(): Promise<ServerEntry> {
  if (!serverEntryPromise) {
    serverEntryPromise = import("@tanstack/react-start/server-entry").then(
      (m) => (m.default ?? m) as ServerEntry,
    );
  }
  return serverEntryPromise;
}

// h3 swallows in-handler throws into a normal 500 Response with body
// {"unhandled":true,"message":"HTTPError"} — try/catch alone never fires for those.
async function normalizeCatastrophicSsrResponse(response: Response): Promise<Response> {
  if (response.status < 500) return response;
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) return response;

  const body = await response.clone().text();
  if (!isH3SwallowedErrorBody(body)) return response;

  console.error(consumeLastCapturedError() ?? new Error(`h3 swallowed SSR error: ${body}`));
  return new Response(renderErrorPage(), {
    status: 500,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

function isH3SwallowedErrorBody(body: string): boolean {
  try {
    const payload = JSON.parse(body) as { unhandled?: unknown; message?: unknown };
    return payload.unhandled === true && payload.message === "HTTPError";
  } catch {
    return false;
  }
}

const BACKEND_URL = process.env["VITE_BACKEND_URL"] || "http://127.0.0.1:8000";

export default {
  async fetch(request: Request, env: unknown, ctx: unknown) {
    const url = new URL(request.url);

    // Forward API and backend stream requests directly to FastAPI server
    if (
      url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/stream/") ||
      url.pathname.startsWith("/evidence/") ||
      url.pathname === "/health" ||
      url.pathname === "/zones"
    ) {
      try {
        const targetUrl = new URL(url.pathname + url.search, BACKEND_URL);
        const reqHeaders = new Headers(request.headers);
        reqHeaders.set("host", targetUrl.host);

        const init: RequestInit = {
          method: request.method,
          headers: reqHeaders,
          redirect: "follow",
        };

        if (request.method !== "GET" && request.method !== "HEAD") {
          init.body = await request.arrayBuffer();
        }

        const backendRes = await fetch(targetUrl.toString(), init);
        return backendRes;
      } catch (proxyErr) {
        console.error("Nitro API proxy error:", proxyErr);
        return new Response(JSON.stringify({ error: "Backend service unreachable", detail: String(proxyErr) }), {
          status: 502,
          headers: { "content-type": "application/json" },
        });
      }
    }

    try {
      const handler = await getServerEntry();
      const response = await handler.fetch(request, env, ctx);
      return await normalizeCatastrophicSsrResponse(response);
    } catch (error) {
      console.error(error);
      return new Response(renderErrorPage(), {
        status: 500,
        headers: { "content-type": "text/html; charset=utf-8" },
      });
    }
  },
};
