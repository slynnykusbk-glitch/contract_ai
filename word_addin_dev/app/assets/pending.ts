const win = window as any;
win.__cai_pending_fetches = win.__cai_pending_fetches || new Set<AbortController>();
win.__cai_pending_timers = win.__cai_pending_timers || new Set<any>();
export const pendingFetches: Set<AbortController> = win.__cai_pending_fetches;
export const pendingTimers: Set<any> = win.__cai_pending_timers;

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
  if (win.__pendingUnloadReg) return;
  win.__pendingUnloadReg = true;
  const abortNav = (() => {
    try { return localStorage.getItem('cai_abort_on_navigation') !== '0'; }
    catch { return true; }
  })();
  const navHandler = () => {
    if (abortNav) clearPending('pagehide/unload');
    win.__wasUnloaded = true;
  };
  window.addEventListener('pagehide', navHandler);
  window.addEventListener('unload', navHandler);
  window.addEventListener('beforeunload', navHandler);
  const abortHidden = (() => {
    try { return localStorage.getItem('cai_abort_on_hidden') !== '0'; }
    catch { return true; }
  })();
  if (abortHidden) {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') clearPending('visibilitychange');
    });
  }
}

export function wasUnloaded(): boolean { return !!win.__wasUnloaded; }
export function resetUnloadFlag() { win.__wasUnloaded = false; }
