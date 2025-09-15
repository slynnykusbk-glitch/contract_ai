import fs from 'fs';
import path from 'path';
import { describe, it, expect } from 'vitest';

describe('taskpane bundle', () => {
  it('has no raw comment API calls', () => {
    const dir = path.resolve(__dirname, '..', '..');
    const files = fs.readdirSync(dir).filter(f => /^taskpane\.bundle.*\.js$/.test(f));
    for (const file of files) {
      const code = fs.readFileSync(path.join(dir, file), 'utf8');
      const insertCount = (code.match(/insertComment\(/g) || []).length;
      const addCount = (code.match(/comments\.add\(/g) || []).length;
      expect(insertCount).toBeLessThanOrEqual(1);
      expect(addCount).toBeLessThanOrEqual(1);
    }
  });
});
