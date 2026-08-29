import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    // The dev container's bind-mounted source tree is a Windows host directory —
    // native inotify events don't reliably cross that boundary (Docker Desktop on
    // Windows/WSL2), so Vite's default watcher can silently keep serving a stale
    // module after a file edit until the dev server is restarted. Polling trades a
    // small CPU cost for actually noticing changes.
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
