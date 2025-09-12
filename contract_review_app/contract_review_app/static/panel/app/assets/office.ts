export async function getWholeDocText(): Promise<string> {
  return await Word.run(async (ctx) => {
    const body = ctx.document.body;
    body.load("text");
    await ctx.sync();
    return (body.text || "").trim();
  });
}

export async function getSelectionText(): Promise<string> {
  return await Word.run(async (ctx) => {
    const sel = ctx.document.getSelection();
    sel.load("text");
    await ctx.sync();
    return (sel.text || "").trim();
  });
}
