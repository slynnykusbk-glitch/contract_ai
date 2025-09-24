import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

describe('taskpane cache busting', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const repoRoot = resolve(here, '../../..');
  const panelDir = join(repoRoot, 'contract_review_app', 'contract_review_app', 'static', 'panel');
  const htmlPath = join(panelDir, 'taskpane.html');
  const taskpaneTs = join(repoRoot, 'word_addin_dev', 'app', 'assets', 'taskpane.ts');

  it('embeds the latest build token in taskpane bundle query', () => {
    const html = readFileSync(htmlPath, 'utf8');
    const tsSource = readFileSync(taskpaneTs, 'utf8');
    const htmlMatch = html.match(/taskpane\.bundle\.js\?b=(build-\d{8}-\d{6})/i);
    const tsMatch = tsSource.match(/const\s+BUILD_ID\s*=\s*'([^']+)'/);
    expect(htmlMatch?.[1]).toMatch(/^build-\d{8}-\d{6}$/);
    expect(tsMatch?.[1]).toBe(htmlMatch?.[1]);
  });
});
