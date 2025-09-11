require('ts-node/register');
const { insertComments } = require('../../word_addin_dev/app/assets/annotate.js');
const { findAnchors } = require('../../word_addin_dev/app/assets/anchors.js');

describe('insertComments', () => {
  it('annotate.success', async () => {
    const comments = [];
    const ranges = [
      { start: 0, end: 1, insertComment: msg => comments.push(msg) },
      { start: 2, end: 3, insertComment: msg => comments.push(msg) },
      { start: 4, end: 5, insertComment: msg => comments.push(msg) },
    ];
    const ctx = { sync: jest.fn(async () => {}), trackedObjects: { add: jest.fn() }, document: { body: {} } };
    const body = { context: ctx, search: () => ({ items: ranges, load: () => {} }) };
    const anchors = await findAnchors(body, 'x');
    const inserted = await insertComments(ctx, anchors.map(r => ({ range: r, message: 'm' })));
    expect(inserted).toBe(3);
    expect(ctx.sync).toHaveBeenCalledTimes(2);
  });

  it('annotate.retry-on-0xA7210002', async () => {
    const inserted = [];
    const range = {
      attempts: 0,
      insertComment(msg) {
        if (this.attempts++ === 0) throw new Error('0xA7210002');
        inserted.push(msg);
      },
      expandTo() { return this; }
    };
    const ctx = { sync: jest.fn(async () => {}), document: { body: {} } };
    const count = await insertComments(ctx, [{ range, message: 'm' }]);
    expect(count).toBe(1);
    expect(inserted).toHaveLength(1);
  });

  it('annotate.skip-after-retry', async () => {
    const range = {
      attempts: 0,
      insertComment() {
        this.attempts++; throw new Error('0xA7210002');
      },
      expandTo() { return this; }
    };
    const ctx = { sync: jest.fn(async () => {}), document: { body: {} } };
    const count = await insertComments(ctx, [{ range, message: 'm' }]);
    expect(count).toBe(0);
  });
});
