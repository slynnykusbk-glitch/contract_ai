# DOM Contract & Build Marker

The panel HTML used by ContractAI must include a small set of required element IDs. These IDs are defined in [`word_addin_dev/app/panel_dom.schema.json`](../word_addin_dev/app/panel_dom.schema.json):

- `btnUseWholeDoc`
- `btnAnalyze`
- `originalText`
- `results`
- `busyBar`
- `officeBadge`
- `connBadge`

Any panel page missing one of these IDs fails fast at runtime and the build pipeline.

During `npm run build:panel` the script replaces every `__BUILD_TS__` placeholder in HTML and JavaScript with a timestamp token and writes the token to `.build-token`. The active build marker is printed in the browser console as:

```
ContractAI build <timestamp>
```

This allows developers to verify which build of the panel is loaded.
