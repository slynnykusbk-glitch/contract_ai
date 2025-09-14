import { describe, it, expect } from 'vitest';

describe('postJson', () => {
  it('sends request even when headers missing', async () => {
    (globalThis as any).window = {
      dispatchEvent: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
    } as any;
    let called = false;
    (globalThis as any).document = { getElementById: () => ({ value: 'https://base' }) };
    (globalThis as any).localStorage = { getItem: () => '' };
    (globalThis as any).fetch = async () => {
      called = true;
      return { status: 200, json: async () => ({}) } as any;
    };
    const { postJson } = await import('../../assets/api-client.ts');
    await postJson('/x', {});
    expect(called).toBe(true);
  });

  it('sends headers when present', async () => {
    (globalThis as any).window = {
      dispatchEvent: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
    } as any;
    let captured: any = null;
    (globalThis as any).document = { getElementById: () => ({ value: 'https://base' }) };
    (globalThis as any).localStorage = {
      getItem: (k: string) => (k === 'api_key' ? 'KEY' : k === 'schema_version' ? '1.2' : ''),
    };
    (globalThis as any).fetch = async (_url: string, opts: any) => {
      captured = opts;
      return { status: 200, json: async () => ({}) } as any;
    };
    const { postJson } = await import('../../assets/api-client.ts');
    await postJson('/test', { a: 1 });
    expect(captured.headers['x-api-key']).toBe('KEY');
    expect(captured.headers['x-schema-version']).toBe('1.2');
    const parsed = JSON.parse(captured.body);
    expect(parsed).toMatchObject({ a: 1, schema: '1.2' });
  });
});
