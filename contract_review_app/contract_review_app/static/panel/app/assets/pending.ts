export const pendingFetches = new Set<AbortController>();
export const pendingTimers = new Set<any>();

export function registerFetch(ctrl: AbortController) { pendingFetches.add(ctrl); }
export function deregisterFetch(ctrl: AbortController) { pendingFetches.delete(ctrl); }
export function registerTimer(id: any) { pendingTimers.add(id); }
export function deregisterTimer(id: any) { pendingTimers.delete(id); }

export function clearPending() {
  pendingFetches.forEach(c => { try { c.abort(); } catch {} });
  pendingFetches.clear();
  pendingTimers.forEach(t => { try { clearTimeout(t); clearInterval(t); } catch {} });
  pendingTimers.clear();
  try {
    document.querySelectorAll('.progress').forEach(el => { (el as HTMLElement).style.display = 'none'; });
  } catch {}
}

export function registerUnloadHandlers() {
  if ((globalThis as any).__pendingUnloadReg) return;
  (globalThis as any).__pendingUnloadReg = true;
  const handler = () => { clearPending(); (globalThis as any).__wasUnloaded = true; };
  window.addEventListener('pagehide', handler);
  window.addEventListener('unload', handler);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') handler(); });
}

export function wasUnloaded(): boolean { return !!(globalThis as any).__wasUnloaded; }
export function resetUnloadFlag() { (globalThis as any).__wasUnloaded = false; }
