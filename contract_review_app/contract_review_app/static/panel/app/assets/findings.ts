import { parseFindings as apiParseFindings, AnalyzeFinding, AnalyzeResponse } from './api-client.ts';
import type { AnalyzeFindingEx } from './types.ts';

export function coerceOffset(v: unknown): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined;
}

export function parseFindings(resp: AnalyzeResponse | AnalyzeFinding[]): AnalyzeFindingEx[] {
  const arr = (apiParseFindings(resp as any) || []) as AnalyzeFindingEx[];
  return arr
    .filter(f => f && f.rule_id && f.snippet)
    .map(f => ({
      ...f,
      start: coerceOffset(f.start),
      end: coerceOffset(f.end),
      clause_type: f.clause_type || 'Unknown'
    }))
    .filter(f => f.clause_type);
}
