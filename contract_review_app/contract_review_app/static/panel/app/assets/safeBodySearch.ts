export async function safeBodySearch(body: any, needle: string, options?: any): Promise<any> {
  const ctx: any = body?.context;
  const txt = (needle ?? '').trim();
  if (!txt) return { items: [] };

  if (txt.length <= 240) {
    try {
      const res = body.search(txt, options);
      res?.load?.('items');
      await ctx?.sync?.();
      return res;
    } catch {
      return { items: [] };
    }
  }

  const anchor = txt.slice(0, 120);
  let anchorRes: any;
  try {
    anchorRes = body.search(anchor, options);
    anchorRes?.load?.('items');
    await ctx?.sync?.();
  } catch {
    return { items: [] };
  }

  const matches: any[] = [];
  const innerNeedle = txt.slice(0, 240);

  for (const r of anchorRes?.items || []) {
    let scope: any = r;
    try {
      scope = r.paragraphs?.getFirst?.() || r;
      scope?.load?.('text');
      await ctx?.sync?.();
    } catch {}

    const text: string = scope?.text || '';
    if (text.includes(innerNeedle)) {
      try {
        const inner = scope.search(innerNeedle, options);
        inner?.load?.('items');
        await ctx?.sync?.();
        if (inner?.items?.length) matches.push(...inner.items);
        continue;
      } catch {}
    }

    const tokens = innerNeedle.split(/\s+/).filter(t => t.length > 3).slice(0, 5);
    let ok = true;
    for (const t of tokens) {
      if (!text.includes(t)) { ok = false; break; }
    }
    if (ok) matches.push(scope);
  }

  return { items: matches };
}
