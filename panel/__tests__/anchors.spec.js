require('ts-node/register');
const { findAnchors } = require('../../word_addin_dev/app/assets/anchors.js');

describe('findAnchors', () => {
  it('anchors.exact-match', async () => {
    const range = { start: 1, end: 4 };
    const ctx = { sync: jest.fn(async () => {}), trackedObjects: { add: jest.fn() } };
    const body = {
      context: ctx,
      search: txt => ({ items: txt === 'foo' ? [range] : [], load: () => {} })
    };
    const res = await findAnchors(body, 'foo');
    expect(res).toHaveLength(1);
    expect(res[0]).toBe(range);
    expect(ctx.trackedObjects.add).toHaveBeenCalledWith(range);
  });

  it('anchors.normalized-fallback', async () => {
    const range = { start: 0, end: 3 };
    const ctx = { sync: jest.fn(async () => {}), trackedObjects: { add: jest.fn() } };
    const body = {
      context: ctx,
      search: txt => ({ items: txt === 'foo bar' ? [range] : [], load: () => {} })
    };
    const res = await findAnchors(body, 'foo\u00A0bar');
    expect(res).toHaveLength(1);
  });

  it('anchors.overlap-pruning', async () => {
    const r1 = { start: 0, end: 5 };
    const r2 = { start: 2, end: 6 };
    const r3 = { start: 4, end: 8 };
    const ctx = { sync: jest.fn(async () => {}), trackedObjects: { add: jest.fn() } };
    const body = { context: ctx, search: () => ({ items: [r1, r2, r3], load: () => {} }) };
    const res = await findAnchors(body, 'x');
    expect(res).toHaveLength(1);
    expect(res[0]).toBe(r1);
  });
});
