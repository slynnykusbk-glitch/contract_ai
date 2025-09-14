import { COMMENT_PREFIX } from "./annotate.ts";
import { findAnchors } from "./anchors.ts";

export async function insertDraftText(
  text: string,
  mode: string,
  rationale?: string,
): Promise<void> {
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
    let target: any = null;
    const prevTrack = doc.trackRevisions;
    try {
      const arr = (w.__findings || []) as any[];
      const idx = w.__findingIdx;
      const cur = arr && typeof idx === 'number' ? arr[idx] : null;
      const body = doc.body as any;
      const anchors = cur?.snippet ? await findAnchors(body, cur.snippet) : [];
      target = anchors[0] || null;
      if (!target) {
        const sel = doc.getSelection();
        sel.load('isEmpty');
        await context.sync();
        target = sel.isEmpty ? doc.body.getRange('End') : sel;
      }
    } catch {
      const sel = doc.getSelection();
      sel.load('isEmpty');
      await context.sync();
      target = sel.isEmpty ? doc.body.getRange('End') : sel;
    }
    doc.trackRevisions = true;
    const range = target.insertText(text, w.Word.InsertLocation.replace);
    const lines = [`${COMMENT_PREFIX} Suggested clause – ${mode}`];
    const rat = (rationale || '').split(/\r?\n/).slice(0, 2).join(' ');
    const wArr: any[] = (w.__findings || []) as any[];
    const idx = w.__findingIdx;
    if (!rat) {
      const cur = wArr && typeof idx === 'number' ? wArr[idx] : null;
      const alt = cur?.rule_id || cur?.title || '';
      if (alt) lines.push(alt);
    } else {
      lines.push(rat);
    }
    lines.push('schema 1.4 | model gpt-4o-mini | provider azure');
    try { doc.comments.add(range, lines.join('\n')); } catch {}
    await context.sync();
    doc.trackRevisions = prevTrack;
    await context.sync();
  }).catch((e: any) => {
    const g: any = globalThis as any;
    g.logRichError?.(e, "insertDraft");
    console.warn('insertDraftText error', e?.code, e?.message, e?.debugInfo);
    throw e;
  });
}
