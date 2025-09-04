# Migration: Add comments on Analyze

## Toggle
- The Task Pane now includes **Add comments on Analyze** checkbox.
- Enabled by default. Uncheck to skip automatic comment insertion.

## Comment prefix
- Comments inserted by Contract AI start with `"[CAI][cid:{CID}][rule:{RULE_ID}]"`.
- Search for this prefix to locate all generated comments.

## Limitations
- Only comments are added; document text is not modified.
- Track Changes are untouched.

## Manual test: tracked suggestions

1. Open Word and load the ContractAI task pane.
2. Ensure the document contains text matching a suggestion's excerpt.
3. In the panel, choose **Suggest** to populate suggestions and click **Apply (tracked)** for one item.
   - Track Changes is enabled and the text is replaced with a revision.
   - A comment and content control with `cai:sugg:<id>` tag are inserted.
   - The suggestion card shows a “tracked in Word” badge (status `applied`).
4. Click **Accept** on that card – it turns grey with a checkmark while the Word revision remains pending.
5. Click **Reject** on another pending card – it shows as rejected and the document stays untouched.
6. Reload the pane: statuses persist via `localStorage`.
