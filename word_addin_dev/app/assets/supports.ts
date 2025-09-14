export type FeatureSupport = {
  revisions: boolean;
  comments: boolean;
  search: boolean;
  contentControls: boolean;
};

export function detectSupports(): FeatureSupport {
  const req = !!(globalThis as any).Office?.context?.requirements?.isSetSupported?.('WordApi','1.4');
  const w: any = (globalThis as any).Word || {};
  const rev = req && !!w?.Revision;
  const com = req && !!w?.Comment;
  const srch = req && !!w?.SearchOptions;
  const cc = req && !!w?.ContentControl;
  const base = { revisions: rev, comments: com, search: srch, contentControls: cc };
  if (!req && w?.Comment && localStorage.getItem('cai.force.comments') === '1') {
    return { ...base, comments: true };
  }
  return base;
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
