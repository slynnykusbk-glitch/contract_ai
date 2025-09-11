import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rollupOptions: {
      input: 'taskpane.ts',
      output: {
        entryFileNames: 'taskpane.bundle.js',
        format: 'iife',
      },
    },
    outDir: 'dist',
    emptyOutDir: true,
  },
});
