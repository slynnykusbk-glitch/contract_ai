import '@testing-library/jest-dom/vitest';

(globalThis as any).Office = {
  context: { requirements: { isSetSupported: () => true }, document: { mode: 'edit' } }
};
