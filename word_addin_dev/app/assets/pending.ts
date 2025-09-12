export const pendingFetches = new Set<AbortController>();
export const pendingTimers = new Set<any>();

type BusyState = { count: number };
const busyState: BusyState = { count: 0 };

export function pushBusy(): void {
  busyState.count++;
  window.dispatchEvent(new CustomEvent('cai:busy', { detail: { busy: true, count: busyState.count } }));
}

export function popBusy(): void {
  busyState.count = Math.max(0, busyState.count - 1);
  window.dispatchEvent(new CustomEvent('cai:busy', { detail: { busy: busyState.count > 0, count: busyState.count } }));
}

export async function withBusy<T>(fn: () => Promise<T>): Promise<T> {
  try {
    pushBusy();
    return await fn();
  } finally {
    popBusy();
  }
}

export function registerFetch(ctrl: AbortController) { pendingFetches.add(ctrl); }
export function deregisterFetch(ctrl: AbortController) { pendingFetches.delete(ctrl); }
export function registerTimer(id: any) { pendingTimers.add(id); }
export function deregisterTimer(id: any) { pendingTimers.delete(id); }

export function clearPending(reason?: string) {
  pendingFetches.forEach(c => { try { c.abort(reason); } catch {} });
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
  const handler = (reason: string) => { clearPending(reason); (globalThis as any).__wasUnloaded = true; };
  window.addEventListener('pagehide', () => handler('pagehide'));
  window.addEventListener('unload', () => handler('unload'));
  const vis = (() => {
    try { return localStorage.getItem('cai_abort_on_visibility') === '1'; }
    catch { return false; }
  })();
  if (vis) {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') handler('dev-visibility');
    });
  }
}

export function wasUnloaded(): boolean { return !!(globalThis as any).__wasUnloaded; }
export function resetUnloadFlag() { (globalThis as any).__wasUnloaded = false; }
