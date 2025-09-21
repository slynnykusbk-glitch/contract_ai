import { normalizeTextFull } from './normalize_full.ts';

export function normalizeIntakeText(input: string | null | undefined): string {
  if (!input) return '';
  return normalizeTextFull(input).text;
}

