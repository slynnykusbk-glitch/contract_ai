export async function safeBodySearch(body: any, q: string, opt?: any): Promise<any> {
  const empty = { items: [] as any[] };
  try { q = (q || '').trim(); } catch { q = ''; }
  if (!q) return empty;

  const ctx: any = body?.context;
  const lengths = [200, 160, 120, 80, 40];
  const smartCut = (s: string, max: number): string => {
    if (s.length <= max) return s;
    let slice = s.slice(0, max);
    const rx = /[\s.,;:!?]/g;
    let last = -1; let m: RegExpExecArray | null;
    while ((m = rx.exec(slice))) last = m.index;
    if (last >= 120) slice = slice.slice(0, last);
    else slice = slice.slice(0, 120);
    return slice;
  };

  for (let i = 0; i < lengths.length; i++) {
    const lim = lengths[i];
    let needle = q;
    if (needle.length > lim) {
      needle = i === 0 ? smartCut(needle, lim) : needle.slice(0, lim);
    }
    try {
      const res: any = body.search(needle, opt);
      res?.load?.('items');
      await ctx?.sync?.();
      if (Array.isArray(res?.items) && res.items.length) return res;
      if (res?.items) return res; // return even if empty
      // if res without items, continue
    } catch (e: any) {
      const code = e?.code || e?.name || '';
      if (code === 'SearchStringInvalidOrTooLong' || code === 'InvalidOrTooLong' || code === 'InvalidArgument') {
        try { console.warn('[safeBodySearch]', code); } catch {}
        continue;
      }
      try { console.warn('[safeBodySearch]', e); } catch {}
      return empty;
    }
    // if we got here, search succeeded but no items
    return empty;
  }
  return empty;
}
