import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../../taskpane.html', import.meta.url), 'utf-8');

describe('dom ids', () => {
  it('contains required ids', () => {
    const required = ['btnAnalyze', 'selectRiskThreshold'];
    for (const id of required) {
      expect(html).toContain(`id="${id}"`);
    }
    expect(html).not.toContain('id="riskThreshold"');
  });
});
