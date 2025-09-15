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
  const com = req;
  const reason = req ? 'WordApi 1.4' : 'WordApi < 1.4';
  return { revisions: rev, comments: com, search: srch, contentControls: cc, commentsReason: reason };
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
