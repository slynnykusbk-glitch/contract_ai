export function updateResultsTraceLink(cid: string | null | undefined, backend: string): void {
  try {
    if (typeof document === 'undefined') return;
  } catch {
    return;
  }

  const parent = document.getElementById('resultsBlock') as HTMLElement | null;
  if (!parent) return;
  const header = parent.querySelector('.muted') as HTMLElement | null;
  if (!header) return;

  let container = header.querySelector('[data-role="trace-link"]') as HTMLElement | null;
  if (!container) {
    container = document.createElement('span');
    container.dataset.role = 'trace-link';
    container.style.marginLeft = '8px';
    header.appendChild(container);
  }

  let badgesContainer = header.querySelector('#traceBadges') as HTMLSpanElement | null;
  if (!badgesContainer) {
    badgesContainer = document.createElement('span');
    badgesContainer.id = 'traceBadges';
    header.appendChild(badgesContainer);
  }

  container.textContent = '';
  badgesContainer.textContent = '';
  container.style.display = 'none';
  badgesContainer.style.display = 'none';

  const normalizedCid = (cid ?? '').trim();
  const backendBase = (backend ?? '').trim().replace(/\/+$/, '');
  if (!normalizedCid || !backendBase) {
    return;
  }

  container.style.display = '';

  const separator = document.createElement('span');
  separator.textContent = ' · ';
  container.appendChild(separator);

  const link = document.createElement('a');
  link.dataset.role = 'open-trace';
  link.target = '_blank';
  link.rel = 'noreferrer noopener';
  link.textContent = 'Open TRACE';
  link.href = `${backendBase}/api/trace/${normalizedCid}.html`;
  container.appendChild(link);
}
