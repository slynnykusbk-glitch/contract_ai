# Lint Health Report

## Overview

- **ESLint** now extends `plugin:prettier/recommended` to keep linting rules in sync with Prettier and fail on formatting drift.
- **Prettier** enforces the shared style guide: semicolons, single quotes, two-space indentation, trailing commas where valid in ES5, and a 100-character print width.
- `lint-staged` runs `eslint --fix --max-warnings=0` followed by `prettier --write` on staged files, ensuring fixes are applied before commit.

## Key Rules

- `@typescript-eslint/no-explicit-any` remains a warning for production assets until migration is complete.
- `prettier/prettier` is an error so any formatting deviations break the lint run and CI.
- ESLint ignores generated assets: `dist`, `taskpane.bundle.js`, and `app/assets`.

## Developer Workflow

1. **Auto-fix on commit**: `.pre-commit-config.yaml` now calls `npm --prefix word_addin_dev run lint:staged`. Staged files are auto-fixed and re-staged. The subsequent `npm --prefix word_addin_dev run lint` gate guarantees the full project still passes linting.
2. **Manual commands**:
   - `npm --prefix word_addin_dev run lint` – run ESLint with `--max-warnings=0`.
   - `npm --prefix word_addin_dev run format` – format the project with Prettier.
   - `npm --prefix word_addin_dev run lint:staged` – execute the `lint-staged` pipeline locally.

## CI Changes

- The CI workflow already calls `npm --prefix word_addin_dev run lint`; with the stricter ESLint+Prettier integration, warnings fail the job. No additional `lint:fix` invocation is required.

## Getting Started

1. Install dependencies once: `npm --prefix word_addin_dev install`.
2. Activate pre-commit hooks: `python -m pre_commit install` (already part of repository instructions).
3. Make your changes; staged files are automatically formatted and linted on commit.
