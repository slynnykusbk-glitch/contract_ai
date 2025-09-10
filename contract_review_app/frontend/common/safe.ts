export function asArray<T = any>(v: any): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}
export function asString(v: any, d = ''): string {
  return typeof v === 'string' ? v : d;
}
export function asNumber(v: any, d = 0): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
}
