# Word Add-in Dev

## Tests

To run unit tests for the add-in helper:

```bash
cd word_addin_dev
npm ci
npm test --silent
```

## Manual check

1. Open the add-in in Word.
2. Click **Analyze** to receive draft text.
3. Use **Insert result into Word** to insert the draft; the button is disabled while the operation runs.
4. Click **Annotate** to insert comments.

Both actions should work without `RichApi.Error 0xA7210002` errors.
