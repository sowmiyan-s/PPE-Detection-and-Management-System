import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: {
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
          configure: (proxy) => {
            proxy.on("error", () => {});
          },
        },
        "/ws": {
          target: "ws://localhost:8000",
          ws: true,
          configure: (proxy) => {
            proxy.on("error", () => {});
          },
        },
      },
    },
  },
});
