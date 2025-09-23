/* @vitest-environment jsdom */
import { describe, it, expect, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

describe('panel bootstrap flow', () => {
  it('enables analyze after successful health', async () => {
    const htmlPath = path.resolve(
      __dirname,
      '../../../contract_review_app/contract_review_app/static/panel/taskpane.html'
    );
    const html = fs.readFileSync(htmlPath, 'utf8');
    document.documentElement.innerHTML = html;

    const btnWhole = document.getElementById('btnUseWholeDoc') as HTMLButtonElement;
    btnWhole.disabled = true;
    const btnAnalyze = document.getElementById('btnAnalyze') as HTMLButtonElement;
    const spy = vi.spyOn(btnAnalyze, 'addEventListener');

    (globalThis as any).Office = {
      onReady: (cb: any) => cb({ host: 'Word' }),
      context: { host: 'Word', requirements: { isSetSupported: () => true } },
    } as any;
    (globalThis as any).localStorage = { getItem: () => '', setItem: () => {} };
    (globalThis as any).fetch = vi.fn(async () => ({
      ok: true,
      json: async () => ({ status: 'ok' }),
      headers: { get: () => null },
    }));

    await import(
      'file://' +
        path.resolve(
          __dirname,
          '../../../contract_review_app/contract_review_app/static/panel/taskpane.bundle.js'
        )
    );
    await new Promise(res => setTimeout(res, 0));

    expect(btnWhole.disabled).toBe(false);
    expect(btnAnalyze.disabled).toBe(false);
    expect(spy).toHaveBeenCalledWith('click', expect.any(Function));
  });
});
