import { safeBodySearch } from '../assets/safeBodySearch.ts';
import { postJSON } from '../assets/api-client.ts';
import {
  safeInsertComment,
  COMMENT_PREFIX,
  fallbackAnnotateWithContentControl,
} from '../assets/annotate.ts';

export interface Finding {
  id: string;
  anchor: string;
  snippet?: string;
  skipped?: boolean;
}

export interface DraftOp {
  anchor: string;
  replace?: { before?: string; after: string };
}

export interface Draft {
  plainText: string;
  ops: DraftOp[];
}

export type PanelState = {
  mode: 'friendly' | 'strict';
  items: Finding[];
  selectedId?: string;
  cachedDrafts: Map<string, Draft>;
  correlationId: string;
};

/**
 * Safely add a comment at the provided Word range. If inserting the comment
 * directly fails, the comment is added to the first paragraph of the range.
 */
export async function addCommentAtRange(range: Word.Range, text: string) {
  let res = await safeInsertComment(range, text);
  if (!res.ok) {
    try {
      const p = range.paragraphs.getFirst();
      res = await safeInsertComment(p as unknown as Word.Range, text);
      if (!res.ok) {
        await fallbackAnnotateWithContentControl(range, text.replace(COMMENT_PREFIX, '').trim());
      }
    } catch {
      await fallbackAnnotateWithContentControl(range, text.replace(COMMENT_PREFIX, '').trim());
    }
  }
}

function itemIndex(state: PanelState, id?: string) {
  return state.items.findIndex(f => f.id === id);
}

async function focusRange(body: Word.Body, anchor: string) {
  const searchOpts = { matchCase: false, matchWholeWord: false };
  const res = await safeBodySearch(body, anchor, searchOpts);
  const range = res?.items?.[0];

  if (range) {
    try {
      range.select();
      if (range.font) range.font.highlightColor = '#ffff00';
    } catch {
      /* ignore */
    }
  }
}

async function move(state: PanelState, dir: -1 | 1, doc: Word.Document) {
  if (!state.items.length) return;
  let idx = itemIndex(state, state.selectedId);
  if (idx === -1) idx = dir === 1 ? 0 : state.items.length - 1;
  else idx = Math.min(Math.max(idx + dir, 0), state.items.length - 1);
  const target = state.items[idx];
  state.selectedId = target.id;
  await focusRange(doc.body, target.anchor || target.snippet || '');
}

export async function prevFinding(state: PanelState, doc: Word.Document) {
  await move(state, -1, doc);
}

export async function nextFinding(state: PanelState, doc: Word.Document) {
  await move(state, 1, doc);
}

export async function getDraft(state: PanelState, id: string): Promise<Draft> {
  const cached = state.cachedDrafts.get(id);
  if (cached) return cached;
  const resp = await postJSON<Draft>('/api/draft', { id });
  state.cachedDrafts.set(id, resp);
  return resp;
}

export async function applyDraft(state: PanelState, id: string, draft: Draft, doc: Word.Document) {
  const docObj = doc.context.document;
  let prevTracking = false;
  try {
    docObj.load?.('trackRevisions');
    await doc.context.sync?.();
    prevTracking = !!docObj.trackRevisions;
    docObj.trackRevisions = true;
    await doc.context.sync?.();
  } catch {
    /* ignore */
  }

  for (const op of draft.ops) {
    const res = await safeBodySearch(doc.body, op.anchor, {
      matchCase: false,
      matchWholeWord: false,
    });
    const range = res?.items?.[0];
    if (!range) continue;
    if (op.replace) {
      const current = range.text;
      if (op.replace.before && current !== op.replace.before) {
        console.warn('text drift', { id });
      }
      range.insertText(op.replace.after, 'Replace');
    }
  }

  try {
    docObj.trackRevisions = prevTracking;
    await doc.context.sync?.();
  } catch {
    /* ignore */
  }

  try {
    const raw = localStorage.getItem('cai_history') || '[]';
    const hist = JSON.parse(raw);
    hist.push({ id, ts: Date.now(), ops: draft.ops });
    localStorage.setItem('cai_history', JSON.stringify(hist));
  } catch {
    /* ignore */
  }
}

export function rejectFinding(state: PanelState, id: string) {
  const idx = itemIndex(state, id);
  if (idx !== -1) state.items[idx].skipped = true;
}
