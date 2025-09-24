import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const ORIGINAL_CACHE = (globalThis as any).__traceCache;

function setupDom(): void {
  document.body.innerHTML = `
    <div id="resultsBlock">
      <div class="muted">
        <span data-role="trace-link"></span>
        <span id="traceBadges"></span>
      </div>
    </div>
  `;
}

describe('TRACE smoke integration', () => {
  beforeEach(() => {
    vi.resetModules();
    setupDom();
    (globalThis as any).__traceCache = new Map<string, any>();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    (globalThis as any).__traceCache = ORIGINAL_CACHE;
  });

  it('updates trace link and renders badges from cache', async () => {
    const { updateResultsTraceLink } = await import('../assets/updateResultsTraceLink.ts');
    const { renderTraceBadges } = await import('../assets/traceBadges.ts');

    const cid = 'cid-smoke-1';
    const backend = 'http://localhost:9443';

    updateResultsTraceLink(cid, backend);

    const cache = new Map<string, any>();
    cache.set(cid, {
      coverage: { zones_total: 45, zones_present: 20, zones_fired: 11 },
      meta: { timings_ms: { merge_ms: 42 } },
    });
    (globalThis as any).__traceCache = cache;

    renderTraceBadges(cid);

    const link = document.querySelector('[data-role="open-trace"]') as HTMLAnchorElement | null;
    expect(link).not.toBeNull();
    expect(link?.href).toBe(`${backend}/api/trace/${cid}.html`);

    const badges = document.getElementById('traceBadges') as HTMLSpanElement | null;
    expect(badges).not.toBeNull();
    expect(badges?.style.display).toBe('');
    expect(badges?.children).toHaveLength(2);
    expect(badges?.children[0].textContent).toBe('Coverage: 11/20/45');
    expect(badges?.children[1].textContent).toBe('Merge: 42 ms');

    (globalThis as any).__traceCache = new Map<string, any>();
    renderTraceBadges(cid);

    const rerenderedBadges = document.getElementById('traceBadges') as HTMLSpanElement | null;
    expect(rerenderedBadges).not.toBeNull();
    expect(rerenderedBadges?.children).toHaveLength(0);
    expect(rerenderedBadges?.style.display).toBe('none');

    const linkAfter = document.querySelector('[data-role="open-trace"]') as HTMLAnchorElement | null;
    expect(linkAfter).not.toBeNull();
    expect(linkAfter?.href).toBe(`${backend}/api/trace/${cid}.html`);
  });
});
