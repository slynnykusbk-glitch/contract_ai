export type FeatureSupport = {
  revisions: boolean;
  comments: boolean;
  search: boolean;
  contentControls: boolean;
  commentsReason: string;
};

export function detectSupports(): FeatureSupport {
  const g: any = globalThis as any;
  const req = !!g.Office?.context?.requirements?.isSetSupported?.('WordApi', '1.4');
  const w: any = g.Word || {};

  const hasWordComment = !!w?.Comment;
  const forcedComments = (() => {
    try {
      const raw = g.localStorage?.getItem?.('cai.force.comments');
      if (!raw) return false;
      const val = String(raw).trim().toLowerCase();
      return val !== '0' && val !== 'false' && val !== 'no';
    } catch {
      return false;
    }
  })();

  const comments = !!(req || forcedComments || hasWordComment);
  const commentsReason = forcedComments
    ? 'forced by cai.force.comments'
    : req
      ? 'WordApi 1.4'
      : hasWordComment
        ? 'Word.Comment'
        : 'WordApi < 1.4';

  const revisions = !!(req && w?.Revision);
  const search = !!(req && w?.SearchOptions);
  const contentControls = !!(req && w?.ContentControl);

  return { revisions, comments, search, contentControls, commentsReason };
}

export const supports = {
  revisions: () => detectSupports().revisions,
  comments: () => detectSupports().comments,
  search: () => detectSupports().search,
  contentControls: () => detectSupports().contentControls,
};

export function logSupportMatrix() {
  const s = detectSupports();
  try { console.log('support matrix', s); } catch {}
  return s;
}
