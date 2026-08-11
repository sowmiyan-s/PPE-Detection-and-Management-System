import { defineConfig } from "@lovable.dev/vite-tanstack-config";

const backendUrl = process.env["VITE_BACKEND_URL"] || "http://127.0.0.1:8000";
const wsBackendUrl = backendUrl.replace(/^http/, "ws");

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  nitro: {
    preset: "node-server",
  },
  vite: {
    server: {
      proxy: {
        "/api": {
          target: backendUrl,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on("error", () => {});
          },
        },
        "/ws": {
          target: wsBackendUrl,
          ws: true,
          configure: (proxy) => {
            proxy.on("error", () => {});
          },
        },
        "/stream": {
          target: backendUrl,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on("error", () => {});
          },
        },
      },
    },
  },
});

