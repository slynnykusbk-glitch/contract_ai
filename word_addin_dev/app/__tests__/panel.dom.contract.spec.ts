import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';

const schema = JSON.parse(
  readFileSync(new URL('../panel_dom.schema.json', import.meta.url), 'utf-8')
);
const html = readFileSync(
  new URL('../../../contract_review_app/contract_review_app/static/panel/taskpane.html', import.meta.url),
  'utf-8'
);

describe('panel DOM contract', () => {
  it('contains all required ids', () => {
    for (const id of schema.required_ids) {
      expect(html).toContain(`id="${id}"`);
    }
  });
});
