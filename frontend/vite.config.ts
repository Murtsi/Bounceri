import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Kehitys: /api → API (uvicorn :8001; MVP:n oletusportti, päätös 054). Tuotannossa API tarjoilee dist/:in itse.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": process.env.API_URL ?? "http://127.0.0.1:8001" } },
});
