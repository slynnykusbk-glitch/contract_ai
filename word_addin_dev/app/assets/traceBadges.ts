export function renderTraceBadges(cid: string): void {
  try {
    if (typeof document === 'undefined') return;
  } catch {
    return;
  }

  const container = document.getElementById('traceBadges') as HTMLSpanElement | null;
  if (!container) return;

  container.textContent = '';
  container.style.display = 'none';

  const cache = (globalThis as any).__traceCache as Map<string, any> | undefined;
  if (!cache?.has(cid)) {
    return;
  }

  const trace = cache.get(cid) || {};
  const cov = trace?.coverage;
  const total = Number(cov?.zones_total) || 0;
  const present = Number(cov?.zones_present) || 0;
  const fired = Number(cov?.zones_fired) || 0;
  const mergeMs = Math.round(Number(trace?.meta?.timings_ms?.merge_ms) || 0);

  const badges: string[] = [];
  if (total > 0) {
    badges.push(`Coverage: ${fired}/${present}/${total}`);
  }
  if (mergeMs > 0) {
    badges.push(`Merge: ${mergeMs} ms`);
  }

  if (!badges.length) {
    return;
  }

  badges.forEach(text => {
    const span = document.createElement('span');
    span.className = 'trace-badge';
    span.textContent = text;
    container.appendChild(span);
  });

  container.style.display = '';
}
