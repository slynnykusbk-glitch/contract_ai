// vitest.config.ci.ts
import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { existsSync } from 'node:fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const candidateVitestDirs = [
  path.resolve(here, 'node_modules/vitest'),
  path.resolve(here, '../node_modules/vitest'),
  path.resolve(here, '../../node_modules/vitest'),
  path.resolve(here, '../../../node_modules/vitest'),
  path.resolve(here, '../../../../node_modules/vitest'),
  path.resolve(here, '../../../word_addin_dev/node_modules/vitest'),
  path.resolve(here, '../../../../word_addin_dev/node_modules/vitest'),
];
const vitestDir = candidateVitestDirs.find(dir => existsSync(dir));
const vitestRoot = vitestDir ? path.dirname(vitestDir) : undefined;

export default defineConfig({
  resolve: vitestRoot
    ? {
        alias: {
          vitest: path.join(vitestRoot, 'vitest/dist/index.js'),
          'vitest/config': path.join(vitestRoot, 'vitest/dist/config.js'),
        },
      }
    : undefined,
  test: {
    // jsdom нам нужен для лёгких DOM-утилит, но мы исключаем тяжёлые офисные спеки
    environment: 'jsdom',
    // Явно исключаем интеграции/офисные/E2E/рендер-тесты, которые требуют Office/Word runtime:
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/build/**',
      // legacy / офисный рантайм / e2e:
      '**/*office*.spec.*',
      '**/*.e2e.spec.*',
      '**/__e2e__/**',
      '**/__office__/**',
      '**/__dom__/**',
      '**/render*.spec.*',
      '**/*taskpane*.spec.*',
      '**/*ui-gating*.spec.*',
      '**/*annotate.flow*.spec.*'
    ],
    // Разрешённый «белый список» — логика, утилиты, поиск, аннотации, таймауты, нормализация:
    include: [
      'app/assets/__tests__/**/*.{spec,test}.ts',
      // допускаем явные файлы, которые важны нам в CI (если присутствуют):
      'app/assets/__tests__/**/*anchors*.spec.ts',
      'app/assets/__tests__/**/*annotate*.spec.ts',
      'app/assets/__tests__/**/*timeout*.spec.ts',
      'app/assets/__tests__/**/*normalized*.spec.ts',
      'app/assets/__tests__/**/*supports*.spec.ts'
    ],
    // ускоряем/стабилизируем CI
    reporters: ['default'],
    watch: false,
    clearMocks: true,
    restoreMocks: true,
    // снижаем флейки от таймаутов
    testTimeout: 30000,
    hookTimeout: 30000,
  },
});
