import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

/**
 * Build goals:
 * - Dev: open http://localhost:3000/draft_panel/index.html (Vite serves TSX directly).
 * - Prod: emit ONE self-executing bundle `taskpane.react.js`
 *   into ../contract_review_app/static/panel (relative to this file).
 * - No code splitting; inline dynamic imports for Word add-in simplicity.
 */
export default defineConfig(() => ({
  plugins: [react()],
  root: resolve(__dirname),
  base: "./",
  server: {
    port: 3000,          // matches API CORS
    strictPort: true,
    open: false,
  },
  preview: {
    port: 3001,
    strictPort: true,
  },
  build: {
    outDir: resolve(__dirname, "../contract_review_app/static/panel"),
    emptyOutDir: false,          // keep other static assets if present
    sourcemap: true,
    cssCodeSplit: false,
    lib: {
      entry: resolve(__dirname, "draft_panel/index.tsx"),
      name: "DraftPanel",
      formats: ["iife"],         // self-executing; mounts to #root if present
      fileName: () => "taskpane.react.js",
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
        manualChunks: undefined,
        assetFileNames: "taskpane.react.[name][extname]",
      },
    },
  },
}));
