export async function safeBodySearch(body: any, needle: string, options?: any): Promise<any> {
  const ctx: any = body?.context;
  const needleClamped = (needle ?? '').slice(0, 240); // Word капризничает >255
  let res: any;
  try {
    res = body.search(needleClamped, options);
  } catch (e: any) {
    // fallback: урезать ещё сильнее, либо отдать пусто
    const shorter = needleClamped.slice(0, 120);
    try {
      res = body.search(shorter, options);
    } catch {
      return { items: [] };
    }
  }
  try {
    res?.load?.('items');
    await ctx?.sync?.();
  } catch {}
  return res;
}

