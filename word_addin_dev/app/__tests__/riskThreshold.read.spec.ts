import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('risk threshold read', () => {
  beforeEach(() => { vi.resetModules(); });

  it('reads selectRiskThreshold', async () => {
    (globalThis as any).window = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => {} };
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).document = {
      getElementById: (id: string) => id === 'selectRiskThreshold' ? { value: 'high' } : null,
    } as any;
    const mod = await import('../assets/taskpane.ts');
    expect(mod.getRiskThreshold()).toBe('high');
  });

  it('defaults to medium when missing', async () => {
    (globalThis as any).window = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => {} };
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).document = { getElementById: () => null } as any;
    const mod = await import('../assets/taskpane.ts');
    expect(mod.getRiskThreshold()).toBe('medium');
  });
});
