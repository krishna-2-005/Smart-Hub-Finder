import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import basicSsl from "@vitejs/plugin-basic-ssl";

// `npm run dev`        -> http://localhost:5173 (geolocation works: localhost is a secure context)
// `npm run dev:https`  -> https://<your-LAN-IP>:5173 for testing GPS on a phone (self-signed cert)
export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === "https" ? [basicSsl()] : [])],
  server: {
    port: 5173,
    host: mode === "https" ? true : "localhost",
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      "/api": { target: process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          map: ["leaflet", "react-leaflet"],
          charts: ["recharts"],
        },
      },
    },
  },
  test: {
    environment: "node",
  },
}));
