import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('dom ids', () => {
  beforeEach(() => { vi.resetModules(); });

  it('reads risk threshold from selectRiskThreshold', async () => {
    (globalThis as any).window = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => {} };
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).document = {
      getElementById: (id: string) => id === 'selectRiskThreshold' ? { value: 'high' } : null,
    } as any;
    const mod = await import('../assets/taskpane.ts');
    expect(mod.getRiskThreshold()).toBe('high');
  });

  it('missing selectRiskThreshold defaults to medium', async () => {
    (globalThis as any).window = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => {} };
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).document = { getElementById: () => null } as any;
    const mod = await import('../assets/taskpane.ts');
    expect(mod.getRiskThreshold()).toBe('medium');
  });
});
