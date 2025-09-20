import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

function makeElement(overrides: any = {}) {
  return Object.assign({
    style: { display: '', removeProperty: vi.fn() },
    classList: { add: vi.fn(), remove: vi.fn(), toggle: vi.fn() },
    appendChild: vi.fn(),
    removeChild: vi.fn(),
    dispatchEvent: vi.fn(),
    addEventListener: vi.fn(),
    setAttribute: vi.fn(),
    removeAttribute: vi.fn(),
    innerHTML: '',
    textContent: '',
    value: '',
  }, overrides);
}

describe('risk forwarding to analyze', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  afterEach(() => {
    delete (globalThis as any).document;
    delete (globalThis as any).window;
    delete (globalThis as any).localStorage;
    delete (globalThis as any).fetch;
    delete (globalThis as any).CustomEvent;
    delete (globalThis as any).Office;
    delete (globalThis as any).__CAI_TESTING__;
  });

  it('includes selected critical risk in analyze request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: async () => ({}) });
    (globalThis as any).fetch = fetchMock;
    (globalThis as any).window = { addEventListener() {}, removeEventListener() {}, dispatchEvent() {}, location: { search: '' } } as any;
    (globalThis as any).document = { addEventListener() {}, querySelectorAll() { return [] as any; } } as any;
    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    const { analyze } = await import('../assets/api-client.ts');
    await analyze({ text: 'hello', risk: 'critical' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, opts] = fetchMock.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toMatchObject({ text: 'hello', mode: 'live', schema: '1.4', risk: 'critical' });
  });

  it('does not drop findings already filtered by the server', async () => {
    const serverFindings = [
      { rule_id: 'F1', snippet: 'alpha', severity: 'critical' },
    ];
    (globalThis as any).__CAI_TESTING__ = true;
    (globalThis as any).window = {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      location: { search: '' },
      __CAI_TESTING__: true,
    } as any;
    const apiClient = await import('../assets/api-client.ts');
    const analyzeSpy = vi.spyOn(apiClient, 'analyze').mockResolvedValue({
      resp: {
        ok: true,
        status: 200,
        headers: new Headers([
          ['x-schema-version', '1.4'],
          ['x-cid', 'demo'],
        ]),
      },
      json: { analysis: { findings: serverFindings }, recommendations: [] },
      meta: {},
    } as any);
    const parseFindingsSpy = vi.spyOn(apiClient, 'parseFindings').mockImplementation(() => serverFindings);

    const annotateMod = await import('../assets/annotate.ts');
    const planAnnotationsSpy = vi.spyOn(annotateMod, 'planAnnotations').mockImplementation((items: any[]) => items.map(f => ({ ...f, raw: f.snippet })) as any);
    vi.spyOn(annotateMod, 'annotateFindingsIntoWord').mockResolvedValue();

    const notifierMod = await import('../assets/notifier');
    vi.spyOn(notifierMod, 'notifyOk').mockImplementation(() => {});
    vi.spyOn(notifierMod, 'notifyErr').mockImplementation(() => {});
    vi.spyOn(notifierMod, 'notifyWarn').mockImplementation(() => {});

    const storeMod = await import('../assets/store.ts');
    vi.spyOn(storeMod, 'getApiKeyFromStore').mockReturnValue('k');
    vi.spyOn(storeMod, 'getSchemaFromStore').mockReturnValue('1.4');
    vi.spyOn(storeMod, 'getAddCommentsFlag').mockReturnValue(false);
    vi.spyOn(storeMod, 'setAddCommentsFlag').mockImplementation(() => {});
    vi.spyOn(storeMod, 'setSchemaVersion').mockImplementation(() => {});
    vi.spyOn(storeMod, 'setApiKey').mockImplementation(() => {});

    const elements = new Map<string, any>();
    const ensureElement = (id: string, overrides: any = {}) => {
      if (!elements.has(id)) {
        elements.set(id, makeElement());
      }
      const el = elements.get(id);
      Object.assign(el, overrides);
      return el;
    };

    ensureElement('selectRiskThreshold', { value: 'critical' });
    ensureElement('btnAnalyze', { disabled: false });
    ensureElement('busyBar');
    ensureElement('originalText', { value: 'contract text', dispatchEvent: vi.fn() });
    ensureElement('hdrWarn');
    ensureElement('results');
    ensureElement('resultsBlock');
    ensureElement('resClauseType');
    ensureElement('findingsBlock');
    ensureElement('recommendationsBlock');
    ensureElement('recommendationsList');
    ensureElement('resFindingsCount');
    ensureElement('rawJson');
    ensureElement('findingsList');
    ensureElement('connBadge');

    (globalThis as any).document = {
      getElementById: (id: string) => ensureElement(id),
      querySelector: () => null,
      querySelectorAll: () => [] as any,
      createElement: () => makeElement(),
      createDocumentFragment: () => makeElement({ appendChild: vi.fn() }),
      addEventListener: vi.fn(),
      body: makeElement(),
    } as any;

    (globalThis as any).window = {
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
      location: { search: '' },
      __CAI_TESTING__: true,
    } as any;

    (globalThis as any).localStorage = { getItem: () => null, setItem: () => {} } as any;
    (globalThis as any).CustomEvent = class {
      detail: any;
      constructor(public type: string, init?: any) {
        this.detail = init?.detail;
      }
    } as any;
    (globalThis as any).Office = { onReady: (cb: any) => cb({}) } as any;

    const taskpane = await import('../assets/taskpane.ts');
    vi.spyOn(taskpane, 'renderAnalysisSummary').mockImplementation(() => {});

    await taskpane.onAnalyze();

    expect(analyzeSpy).toHaveBeenCalledWith(expect.objectContaining({ risk: 'critical' }));
    expect(planAnnotationsSpy).toHaveBeenCalledTimes(1);
    const planned = planAnnotationsSpy.mock.calls[0][0];
    expect(planned).toHaveLength(serverFindings.length);
    expect(planned.map((f: any) => f.rule_id)).toEqual(serverFindings.map(f => f.rule_id));
    expect(parseFindingsSpy).toHaveBeenCalledWith({ analysis: { findings: serverFindings }, recommendations: [] });
  });
});
