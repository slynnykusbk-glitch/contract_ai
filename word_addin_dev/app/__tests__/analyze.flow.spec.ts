import { describe, it, expect, vi, afterEach } from 'vitest';
import type { components } from '../../../docs/api';
import type { AnalyzeFinding } from '../assets/api-client.ts';

type AnalyzeRequest = components['schemas']['AnalyzeRequest'];

describe('analyze flow', () => {
  afterEach(() => {
    delete (globalThis as any).__CAI_TESTING__;
    delete (globalThis as any).window;
    delete (globalThis as any).document;
    delete (globalThis as any).localStorage;
    delete (globalThis as any).fetch;
  });

  it('posts flat payload with schema', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}), headers: new Headers(), status: 200 });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).window = { dispatchEvent() {} } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const { analyze } = await import('../assets/api-client.ts');
    const payload: AnalyzeRequest = { text: 'hello', language: 'en-GB', mode: 'live', risk: null, schema: null };
    await analyze({ text: payload.text, mode: payload.mode } as any);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, opts] = fetchMock.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toMatchObject({ text: 'hello', mode: 'live', schema: '1.4', risk: 'medium' });
    expect(opts.headers['x-schema-version']).toBe('1.4');
  });

  it('filters QA findings to high and above', async () => {
    vi.resetModules();
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).window = { addEventListener() {}, removeEventListener() {}, location: { search: '' } } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const { filterFindingsByRiskForTests } = await import('../assets/taskpane.ts');
    const findings: AnalyzeFinding[] = [
      { rule_id: 'low', snippet: 'l', severity: 'low' } as AnalyzeFinding,
      { rule_id: 'med', snippet: 'm', severity: 'medium' } as AnalyzeFinding,
      { rule_id: 'hi', snippet: 'h', severity: 'high' } as AnalyzeFinding,
      { rule_id: 'crit', snippet: 'c', severity: 'critical' } as AnalyzeFinding,
      { rule_id: 'upper', snippet: 'u', severity: 'CRITICAL' as any } as AnalyzeFinding,
    ];
    const filtered = filterFindingsByRiskForTests(findings, 'high');
    expect(filtered.map(f => f.rule_id)).toEqual(['hi', 'crit', 'upper']);
  });
});
