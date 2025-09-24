import { describe, beforeEach, it, expect } from 'vitest';
import { renderTraceBadges } from '../traceBadges';

declare global {
  // eslint-disable-next-line no-var
  var __traceCache: Map<string, any> | undefined;
}

describe('trace badges integration', () => {
  beforeEach(() => {
    document.body.innerHTML = '<span id="traceBadges"></span>';
    globalThis.__traceCache = new Map();
  });

  it('smoke_trace_badges_integration renders coverage and merge badges', () => {
    const cid = 'cid-123';
    const trace = {
      coverage: { zones_total: 12, zones_present: 10, zones_fired: 6 },
      meta: { timings_ms: { merge_ms: 42.2 } },
    };
    globalThis.__traceCache?.set(cid, trace);

    renderTraceBadges(cid);

    const badges = Array.from(document.querySelectorAll('#traceBadges .trace-badge'));
    expect(badges).toHaveLength(2);
    expect(badges[0]?.textContent).toBe('Coverage: 6/10/12');
    expect(badges[1]?.textContent).toBe('Merge: 42 ms');
    expect((document.getElementById('traceBadges') as HTMLElement | null)?.style.display).toBe('');
  });

  it('hides badges if cache missing entry', () => {
    renderTraceBadges('missing');

    const container = document.getElementById('traceBadges') as HTMLElement | null;
    expect(container?.textContent).toBe('');
    expect(container?.style.display).toBe('none');
  });

  it('does nothing without container', () => {
    document.body.innerHTML = '';
    globalThis.__traceCache = new Map([[
      'cid',
      { coverage: { zones_total: 1, zones_present: 1, zones_fired: 1 } },
    ]]);

    expect(() => renderTraceBadges('cid')).not.toThrow();
  });
});
