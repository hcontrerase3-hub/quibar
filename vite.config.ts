import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = `http://${env.QUIBAR_API_HOST || "127.0.0.1"}:${env.QUIBAR_API_PORT || "8000"}`;
  return {
    plugins: [react()],
    resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
    server: {
      port: Number(env.QUIBAR_WEB_PORT || 3000), strictPort: true,
      proxy: Object.fromEntries(["/api", "/media", "/tiles"].map(path => [path, { target: backend, timeout: 125000 }])),
    },
    build: { outDir: "dist" },
  };
});
