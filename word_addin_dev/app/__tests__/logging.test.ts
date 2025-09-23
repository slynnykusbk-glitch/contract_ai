import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('extended error logging', () => {
  beforeEach(() => {
    vi.resetModules();
    delete (globalThis as any).__ENABLE_EXTENDED_LOGS__;
    delete (globalThis as any).__ENV__;
    (globalThis as any).window = globalThis;
    (globalThis as any).localStorage = {
      getItem: () => null,
      setItem: () => {},
    };
    const stubEl = {
      addEventListener: () => {},
      style: {},
      classList: { add: () => {}, remove: () => {}, contains: () => false },
      setAttribute: () => {},
      removeAttribute: () => {},
      innerHTML: '',
      textContent: '',
    };
    (globalThis as any).document = {
      readyState: 'complete',
      addEventListener: () => {},
      querySelector: () => stubEl,
      body: { dataset: {}, querySelectorAll: () => ({ forEach: () => {} }) },
    };
    (globalThis as any).__CAI_TESTING__ = true;
  });

  it('enables in development', async () => {
    const config: any = {};
    (globalThis as any).OfficeExtension = { config };
    process.env.NODE_ENV = 'development';
    await import('../assets/taskpane');
    expect(config.extendedErrorLogging).toBe(true);
  });

  it('disabled in production by default', async () => {
    const config: any = {};
    (globalThis as any).OfficeExtension = { config };
    process.env.NODE_ENV = 'production';
    await import('../assets/taskpane');
    expect(config.extendedErrorLogging).toBeUndefined();
  });

  it('defaults to production when env is undefined', async () => {
    const config: any = {};
    (globalThis as any).OfficeExtension = { config };
    const origProcess = (globalThis as any).process;
    (globalThis as any).process = undefined;
    await import('../assets/taskpane');
    expect(config.extendedErrorLogging).toBeUndefined();
    (globalThis as any).process = origProcess;
  });

  it('can be enabled in production via flag', async () => {
    const config: any = {};
    (globalThis as any).OfficeExtension = { config };
    (globalThis as any).__ENABLE_EXTENDED_LOGS__ = true;
    process.env.NODE_ENV = 'production';
    await import('../assets/taskpane');
    expect(config.extendedErrorLogging).toBe(true);
  });
});
