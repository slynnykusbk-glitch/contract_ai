import { logSupportMatrix } from './supports.ts';
import { checkHealth } from './health.ts';
import { logApiClientChecksum } from './api-client.ts';

export async function runStartupSelftest(backend: string) {
  const missing: string[] = [];
  try { await logApiClientChecksum(); } catch {}
  ['btnAnalyze', 'selectRiskThreshold'].forEach(id => {
    if (!document.getElementById(id)) missing.push(`missingID:${id}`);
  });
  if (!Office?.context?.requirements?.isSetSupported?.('WordApi', '1.4')) missing.push('req1.4:0');
  const featsRaw = logSupportMatrix();
  const features = {
    revisions: featsRaw.revisions ? 1 : 0,
    comments: featsRaw.comments ? 1 : 0,
    search: featsRaw.search ? 1 : 0,
    contentControls: featsRaw.contentControls ? 1 : 0,
  } as Record<string, number>;
  let healthOk = false;
  try {
    const res = await checkHealth({ backend });
    healthOk = res.ok;
    if (!healthOk) missing.push('health');
  } catch {
    missing.push('health:timeout');
  }
    const build = 'build-20250914-100041';
  const host = (Office as any)?.context?.host || 'Word';
  const ok = missing.length === 0;
  const msg = ok
    ? `Startup OK | build=${build} | host=${host} | req=1.4 | features=${JSON.stringify(features)} | backend=${backend}`
    : `Startup FAIL: ${missing.join('; ')}`;
  console.log(msg);
  const badge = document.getElementById('startupBadge');
  if (badge) {
    badge.textContent = ok ? 'OK' : 'FAIL';
    badge.setAttribute('data-status', ok ? 'ok' : 'fail');
  }
  return { ok, missing, features };
}
