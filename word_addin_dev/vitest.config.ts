import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['app/**/__tests__/**/*.{test,spec}.ts?(x)', 'app/src/**/*.{test,spec}.ts?(x)'],
    setupFiles: ['./vitest.setup.ts'],
  },
  server: {
    fs: {
      allow: ['..'],
    },
  },
});
