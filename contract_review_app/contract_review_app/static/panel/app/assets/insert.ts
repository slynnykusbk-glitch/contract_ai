export async function insertDraftText(text: string): Promise<void> {
  if (!text || !text.trim()) return;
  const w: any = globalThis as any;
  if (!w.Word?.run) {
    await w.navigator?.clipboard?.writeText(text).catch(() => {});
    w.alert?.('Draft copied to clipboard (Office not ready). Paste it into the document.');
    return;
  }
  if (w.Office?.context?.document?.mode && w.Office.context.document.mode !== 'edit') {
    w.alert?.('Document is read-only.');
    throw new Error('Document mode is not editable');
  }
  await w.Word.run(async (context: any) => {
    const doc = context.document;
    const sel = doc.getSelection();
    sel.load('isEmpty');
    await context.sync();
    const target = sel.isEmpty ? doc.body.getRange('End') : sel;
    target.insertText(text, w.Word.InsertLocation.replace);
    await context.sync();
  }).catch((e: any) => {
    const g: any = globalThis as any;
    g.logRichError?.(e, "insertDraft");
    console.warn('insertDraftText error', e?.code, e?.message, e?.debugInfo);
    throw e;
  });
}
