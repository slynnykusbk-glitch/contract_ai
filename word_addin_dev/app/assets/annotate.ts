/** Utilities for inserting comments into Word with batching and retries. */
export interface CommentItem {
  range: any;
  message: string;
}

/**
 * Insert comments for provided ranges. Operations are batched: ``context.sync``
 * is called after every 20 successful insertions and once at the end. If
 * ``range.insertComment`` throws an error containing ``0xA7210002`` it retries
 * once after rehydrating the range via ``expandTo(context.document.body)``. On
 * second failure the error is logged and the comment is skipped.
 *
 * Returns the number of comments successfully queued for insertion.
 */
export async function insertComments(ctx: any, items: CommentItem[]): Promise<number> {
  let inserted = 0;
  let pending = 0;
  for (const it of items) {
    let r = it.range;
    const msg = it.message;
    try {
      r.insertComment(msg);
      inserted++;
    } catch (e: any) {
      if (String(e).includes("0xA7210002")) {
        try {
          r = r.expandTo ? r.expandTo(ctx.document.body) : r;
          r.insertComment(msg);
          inserted++;
        } catch (e2) {
          console.warn("annotate retry failed", e2);
        }
      } else {
        console.warn("annotate error", e);
      }
    }
    pending++;
    if (pending % 20 === 0) {
      await ctx.sync();
    }
  }
  if (pending % 20 !== 0) {
    await ctx.sync();
  }
  return inserted;
}
