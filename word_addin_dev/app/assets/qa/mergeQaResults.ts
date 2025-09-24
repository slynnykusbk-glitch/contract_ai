import { AnalyzeFinding } from "../api-client.ts";
import { normalizeText, severityRank } from "../dedupe.ts";

const AGENDA_GROUP_ORDER: Record<string, number> = {
  law: 0,
  policy: 1,
  substantive: 2,
  drafting: 3,
  grammar: 4,
};

function coerceNumber(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return Number.NaN;
}

function getSalience(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return Number.NEGATIVE_INFINITY;
}

function agendaRank(value: unknown): number {
  if (typeof value === "string") {
    const key = value.trim().toLowerCase();
    if (key in AGENDA_GROUP_ORDER) {
      return AGENDA_GROUP_ORDER[key as keyof typeof AGENDA_GROUP_ORDER];
    }
  }
  return Number.MAX_SAFE_INTEGER;
}

function cloneFinding(finding: AnalyzeFinding): AnalyzeFinding {
  return { ...finding };
}

function hasSourceProp(finding: AnalyzeFinding): boolean {
  return Object.prototype.hasOwnProperty.call(finding, "source");
}

function setSourceIfNeeded(
  finding: AnalyzeFinding,
  preferred: unknown,
  shouldMark: boolean,
): AnalyzeFinding {
  if (!shouldMark) {
    return finding;
  }
  const clone = cloneFinding(finding);
  if (typeof preferred !== "undefined") {
    (clone as any).source = preferred;
  } else if (typeof (clone as any).source === "undefined") {
    (clone as any).source = "qa";
  }
  return clone;
}

export function makeKey(finding: AnalyzeFinding): string {
  const rule = finding?.rule_id ?? "";
  const start = coerceNumber((finding as any)?.start);
  const end = coerceNumber((finding as any)?.end);
  const snippetNorm = normalizeText((finding as any)?.snippet ?? "");
  return `${rule}|${start}|${end}|${snippetNorm}`;
}

export function priorityCompare(a: AnalyzeFinding, b: AnalyzeFinding): number {
  const severityDiff = severityRank((a as any)?.severity) - severityRank((b as any)?.severity);
  if (severityDiff !== 0) {
    return severityDiff;
  }

  const salienceDiff = getSalience((a as any)?.salience) - getSalience((b as any)?.salience);
  if (salienceDiff !== 0) {
    return salienceDiff;
  }

  const agendaDiff = agendaRank((b as any)?.agenda_group) - agendaRank((a as any)?.agenda_group);
  if (agendaDiff !== 0) {
    return agendaDiff;
  }

  const ruleA = `${(a as any)?.rule_id ?? ""}`;
  const ruleB = `${(b as any)?.rule_id ?? ""}`;
  const cmp = ruleA.localeCompare(ruleB, undefined, { numeric: true, sensitivity: "base" });
  if (cmp !== 0) {
    return -cmp;
  }

  return 0;
}

function getCollectionEntry(
  base: AnalyzeFinding[],
  appends: AnalyzeFinding[],
  index: number,
): AnalyzeFinding {
  return index < base.length ? base[index] : appends[index - base.length];
}

function setCollectionEntry(
  base: AnalyzeFinding[],
  appends: AnalyzeFinding[],
  index: number,
  value: AnalyzeFinding,
): void {
  if (index < base.length) {
    base[index] = value;
  } else {
    appends[index - base.length] = value;
  }
}

export function mergeQaFindings(
  baseFindings: AnalyzeFinding[] = [],
  qaFindings: AnalyzeFinding[] = [],
): AnalyzeFinding[] {
  const base = Array.isArray(baseFindings) ? [...baseFindings] : [];
  const qa = Array.isArray(qaFindings) ? qaFindings : [];
  const map = new Map<string, number>();
  for (let i = 0; i < base.length; i += 1) {
    map.set(makeKey(base[i]), i);
  }

  const appends: AnalyzeFinding[] = [];
  const shouldMarkSource = base.some(hasSourceProp) || qa.some(hasSourceProp);

  for (const qaItem of qa) {
    const candidate = cloneFinding(qaItem);
    const key = makeKey(candidate);
    const idx = map.get(key);
    if (typeof idx === "number") {
      const existing = getCollectionEntry(base, appends, idx);
      const cmp = priorityCompare(candidate, existing);
      if (cmp < 0) {
        continue;
      }
      const preferredSource = shouldMarkSource ? (existing as any)?.source : undefined;
      const replacement = setSourceIfNeeded(candidate, preferredSource, shouldMarkSource);
      setCollectionEntry(base, appends, idx, replacement);
      continue;
    }

    const preferredIndex = base.length + appends.length;
    const appended = shouldMarkSource ? setSourceIfNeeded(candidate, undefined, true) : candidate;
    appends.push(appended);
    map.set(key, preferredIndex);
  }

  return base.concat(appends);
}

export function mergeQaPayload(
  existing: AnalyzeFinding[] | undefined,
  qaPayload: AnalyzeFinding[] | undefined,
): AnalyzeFinding[] {
  return mergeQaFindings(existing ?? [], qaPayload ?? []);
}
