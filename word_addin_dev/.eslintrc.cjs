module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  ignorePatterns: ['dist', 'taskpane.bundle.js', 'app/assets'],
  overrides: [
    {
      files: ['app/__tests__/**/*.ts', 'app/src/**/*.spec.ts'],
      rules: {
        '@typescript-eslint/no-explicit-any': 'off',
        'no-empty': 'off'
      }
    }
  ],
  rules: {
    // Allow transitional 'any' in production assets for now; flip to "error" in Step 1
    '@typescript-eslint/no-explicit-any': 'warn'
  }
};
