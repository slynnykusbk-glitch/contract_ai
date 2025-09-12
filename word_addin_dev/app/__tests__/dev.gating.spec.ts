import { describe, it, expect, beforeEach, vi } from 'vitest';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../../taskpane.html', import.meta.url), 'utf-8');
if (!html.includes('id="btnTest"')) throw new Error('btnTest missing from canonical HTML');

const mkDoc = () => {
  const el: any = { disabled: false, style: { display: '' }, addEventListener: () => {}, classList: { remove: () => {} }, removeAttribute: () => {} };
  return {
    getElementById: (id: string) => id === 'btnTest' ? el : null,
    querySelector: (sel: string) => sel === '#btnTest' ? el : null,
  } as any;
};

describe('dev gating', () => {
  beforeEach(() => {
    vi.resetModules();
    (globalThis as any).window = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => {} };
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).Office = { context: { requirements: { isSetSupported: () => true } } } as any;
    (globalThis as any).Word = { Revision:{}, Comment:{}, SearchOptions:{}, ContentControl:{} } as any;
  });

  it('hides test button in prod', async () => {
    (globalThis as any).ENV_MODE = 'prod';
    (globalThis as any).document = mkDoc();
    const { wireUI } = await import('../assets/taskpane.ts');
    wireUI();
    const btn = document.getElementById('btnTest') as any;
    expect(btn.style.display).toBe('none');
  });

  it('shows test button in dev', async () => {
    (globalThis as any).ENV_MODE = 'dev';
    (globalThis as any).document = mkDoc();
    const { wireUI } = await import('../assets/taskpane.ts');
    wireUI();
    const btn = document.getElementById('btnTest') as any;
    expect(btn.style.display).toBe('');
  });
});
