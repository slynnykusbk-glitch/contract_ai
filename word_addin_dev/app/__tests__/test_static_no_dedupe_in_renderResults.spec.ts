import { describe, expect, it } from 'vitest';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

describe('renderResults static guard', () => {
  it('does not dedupe or sort findings', () => {
    const filePath = resolve(dirname(fileURLToPath(import.meta.url)), '../assets/taskpane.ts');
    const text = readFileSync(filePath, 'utf-8');
    const start = text.indexOf('export function renderResults');
    expect(start).toBeGreaterThan(-1);
    const end = text.indexOf('function mergeQaResults', start);
    expect(end).toBeGreaterThan(start);
    const body = text.slice(start, end);
    expect(body.includes('dedupeFindings(')).toBe(false);
    expect(body.includes('.sort(')).toBe(false);
  });
});
