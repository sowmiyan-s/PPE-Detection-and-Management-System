import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: {
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on("error", () => {});
          },
        },
        "/ws": {
          target: "ws://127.0.0.1:8000",
          ws: true,
          configure: (proxy) => {
            proxy.on("error", () => {});
          },
        },
      },
    },
  },
});
