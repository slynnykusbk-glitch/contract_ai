const fs = require('fs');
const src = 'dist/taskpane.bundle.js';
const dst = 'taskpane.bundle.js';
if (!fs.existsSync(src)) {
  console.error(`[copy-bundle] Missing ${src}`);
  process.exit(1);
}
fs.copyFileSync(src, dst);
console.log(`[copy-bundle] ${src} -> ${dst}`);
