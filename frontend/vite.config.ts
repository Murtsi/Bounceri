import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

// Kehitys: /api → API (uvicorn :8001; MVP:n oletusportti, päätös 054). Tuotannossa API tarjoilee dist/:in itse.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { port: 5173, proxy: { "/api": process.env.API_URL ?? "http://127.0.0.1:8001" } },
});
