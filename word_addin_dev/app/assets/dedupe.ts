import { AnalyzeFinding } from "./api-client.ts";

export const RISK_LEVELS = ["low", "medium", "high", "critical"] as const;
export type RiskLevel = typeof RISK_LEVELS[number];

export function normalizeText(s: string | undefined | null): string {
  if (!s) return "";
  return s
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\u00A0/g, " ")
    .replace(/[ \t]+/g, " ")
    .trim();
}

export function normalizeSeverity(val: unknown): RiskLevel | null {
  if (typeof val !== "string") return null;
  const v = val.trim().toLowerCase();
  if (v === "low" || v === "medium" || v === "high" || v === "critical") {
    return v;
  }
  return null;
}

export function severityRank(val: unknown): number {
  const sev = normalizeSeverity(val);
  if (!sev) return RISK_LEVELS.indexOf("medium");
  return RISK_LEVELS.indexOf(sev);
}

export function dedupeFindings(findings: AnalyzeFinding[]): AnalyzeFinding[] {
  const map = new Map<string, AnalyzeFinding>();
  let invalid = 0, dupes = 0;
  for (const f of findings || []) {
    const snippet = normalizeText(f.snippet || "");
    const start = typeof f.start === "number" ? f.start : undefined;
    const end = typeof f.end === "number" ? f.end : (start !== undefined ? start + snippet.length : undefined);
    if (typeof start !== "number" || typeof end !== "number" || end <= start || end - start > 10000) {
      invalid++;
      continue;
    }
    const key = `${f.rule_id || ""}|${start}|${end}|${snippet}`;
    const ex = map.get(key);
    if (!ex || severityRank(f.severity) > severityRank(ex.severity)) {
      map.set(key, { ...f, snippet, start, end });
    } else {
      dupes++;
    }
  }
  const res = Array.from(map.values());
  console.log("panel:annotate", `dedupe dropped ${invalid} invalid, ${dupes} duplicates`);
  return res;
}
