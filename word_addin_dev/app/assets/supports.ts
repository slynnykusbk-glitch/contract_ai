export type FeatureSupport = {
  revisions: boolean;
  comments: boolean;
  search: boolean;
  contentControls: boolean;
  commentsReason: string;
};

export function detectSupports(): FeatureSupport {
  const req = !!(globalThis as any).Office?.context?.requirements?.isSetSupported?.('WordApi', '1.4');
  const w: any = (globalThis as any).Word || {};
  const rev = req && !!w?.Revision;
  const srch = req && !!w?.SearchOptions;
  const cc = req && !!w?.ContentControl;

  const ls = (globalThis as any).localStorage;
  const override = ls?.getItem?.('cai.force.comments') === '1';
  let comments = false;
  let reason = 'unsupported';
  if (override) {
    comments = true;
    reason = 'dev override';
  } else if (w?.Comment) {
    comments = true;
    reason = 'Word.Comment available';
  } else if (req) {
    comments = true;
    reason = 'WordApi 1.4';
  } else {
    comments = false;
    reason = 'Word.Comment missing';
  }

  return { revisions: rev, comments, search: srch, contentControls: cc, commentsReason: reason };
}

export const supports = {
  revisions: () => detectSupports().revisions,
  comments: () => detectSupports().comments,
  search: () => detectSupports().search,
  contentControls: () => detectSupports().contentControls,
};

export function logSupportMatrix() {
  const s = detectSupports();
  try { console.log('support matrix', { comments: s.comments, reason: s.commentsReason }); } catch {}
  return s;
}
