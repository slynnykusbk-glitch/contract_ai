import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

describe('traceBadges.ts safety', () => {
  it('does not use innerHTML for trace data', () => {
    const here = path.dirname(fileURLToPath(import.meta.url));
    const filePath = path.resolve(here, '../traceBadges.ts');
    const contents = readFileSync(filePath, 'utf-8');
    expect(contents.includes('innerHTML')).toBe(false);
  });
});
