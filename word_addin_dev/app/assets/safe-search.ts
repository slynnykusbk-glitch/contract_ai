export interface BodyLike {
  search: (s: string, opts: any) => any;
}

export function safeBodySearch(body: BodyLike, s: string, opts: any): any {
  const empty = { items: [] as any[], load: () => {} };
  if (!s) return empty;
  let needle = s;
  if (needle.length > 200) {
    needle = needle.slice(0, 100).trim();
    if (needle.length > 200) {
      needle = needle.slice(0, 120);
    }
  }
  try {
    return body.search(needle, opts);
  } catch (e: any) {
    const code = e?.code || e?.name || '';
    if (code === 'SearchStringInvalidOrTooLong' || code === 'InvalidArgument') {
      try {
        console.warn('[WARN] safeBodySearch', code);
        const g: any = globalThis as any;
        g.toast2?.('Some anchors skipped: long text', 'warn');
        g.__anchorsSkipped = (g.__anchorsSkipped || 0) + 1;
        g.updateAnchorBadge?.();
      } catch {}
      return empty;
    }
    throw e;
  }
}
