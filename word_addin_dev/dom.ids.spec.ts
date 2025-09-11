import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

describe('taskpane.html ids', () => {
  const html = readFileSync(join(__dirname, 'taskpane.html'), 'utf8');
  it('contains hdrWarn', () => {
    expect(html).toMatch(/id="hdrWarn"/);
  });
  it('contains chkAddCommentsOnAnalyze', () => {
    expect(html).toMatch(/id="chkAddCommentsOnAnalyze"/);
  });
  it('contains selectRiskThreshold', () => {
    expect(html).toMatch(/id="selectRiskThreshold"/);
  });
});
