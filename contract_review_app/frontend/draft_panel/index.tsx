import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { postJSON, getHealth, ensureHeadersSet } from '../common/http';

const DEFAULT_BACKEND = 'http://127.0.0.1:9000';
const LS_KEY = 'contract_ai_backend';
const DRAFT_PATH = '/api/gpt-draft';

function getBackend(): string {
  try {
    const v = (localStorage.getItem(LS_KEY) || '').trim();
    return v || DEFAULT_BACKEND;
  } catch {
    return DEFAULT_BACKEND;
  }
}

type Status = 'idle' | 'loading' | 'ready' | 'error';

class Boundary extends React.Component<{ children: React.ReactNode }, { error: string | null }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  componentDidCatch(e: any) {
    console.error(e);
    this.setState({ error: e?.message || 'render failed' });
  }
  render() {
    return this.state.error ? <div style={{ color: 'red' }}>Error: {this.state.error}</div> : this.props.children;
  }
}

interface AnalyzeEnvelope {
  analysis?: any;
  [k: string]: any;
}
interface DraftEnvelope {
  proposed_text?: string;
  draft_text?: string;
  [k: string]: any;
}

interface PanelProps {
  initialAnalysis?: any;
  initialMeta?: any;
  initialAnalysisMeta?: any;
}

const DraftAssistantPanel: React.FC<PanelProps> = ({ initialAnalysis = null, initialMeta = {}, initialAnalysisMeta = null }) => {
  const [clauseType, setClauseType] = useState('');
  const [clauseText, setClauseText] = useState('');
  const [analysis, setAnalysis] = useState<any>(initialAnalysis);
  const [analysisMeta, setAnalysisMeta] = useState<any>(initialAnalysisMeta);
  const [draft, setDraft] = useState<DraftEnvelope | null>(null);
  const [status, setStatus] = useState<Status>(initialAnalysis ? 'ready' : 'idle');
  const [error, setError] = useState('');
  const [backendOk, setBackendOk] = useState(false);
  const [meta, setMeta] = useState<any>(initialMeta);
  const PAGE_SIZE = 100;
  const [findingsLimit, setFindingsLimit] = useState(PAGE_SIZE);
  const [toast, setToast] = useState('');
  const [companies, setCompanies] = useState<Record<string, any>>({});
  const [companyStatus, setCompanyStatus] = useState<Record<string, Status>>({});

  const CH_CACHE_TTL_MS = 15 * 60 * 1000;

  function getCached(num: string): any | null {
    try {
      const raw = sessionStorage.getItem(`ch_${num}`);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (Date.now() - obj.ts < CH_CACHE_TTL_MS) {
        return obj.data;
      }
    } catch {}
    return null;
  }

  function setCached(num: string, data: any) {
    try {
      sessionStorage.setItem(`ch_${num}`, JSON.stringify({ ts: Date.now(), data }));
    } catch {}
  }

  const fetchCompany = async (num: string) => {
    setCompanyStatus(s => ({ ...s, [num]: 'loading' }));
    const cached = getCached(num);
    if (cached) {
      setCompanies(d => ({ ...d, [num]: cached }));
      setCompanyStatus(s => ({ ...s, [num]: 'ready' }));
      return;
    }
    try {
      const base = getBackend().replace(/\/+$/, '');
      const resp = await fetch(`${base}/api/companies/${num}`);
      if (resp.status === 429) {
        setToast('Companies House rate-limited — retry shortly');
        setCompanyStatus(s => ({ ...s, [num]: 'error' }));
        return;
      }
      if (!resp.ok) throw new Error('profile failed');
      const data = await resp.json();
      setCached(num, data);
      setCompanies(d => ({ ...d, [num]: data }));
      setCompanyStatus(s => ({ ...s, [num]: 'ready' }));
    } catch (e) {
      console.error(e);
      setCompanyStatus(s => ({ ...s, [num]: 'error' }));
    }
  };

  useEffect(() => {
    if (!analysisMeta?.companies_meta) return;
    const list = Array.isArray(analysisMeta.companies_meta) ? analysisMeta.companies_meta : [];
    list.forEach((c: any) => {
      const num = c?.matched?.company_number || c?.from_document?.number;
      if (num && !companies[num]) {
        fetchCompany(num);
      }
    });
  }, [analysisMeta]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(''), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    ensureHeadersSet();
    const base = getBackend().replace(/\/+$/, '');
    getHealth(base).then(j => {
      setBackendOk(true);
      setMeta(j || {});
    }).catch(e => {
      console.error(e);
      setBackendOk(false);
    });
  }, []);

  const callAnalyze = async () => {
    const text = clauseText.trim();
    if (!text) {
      setToast('Пустой документ/выделение');
      return;
    }
    setStatus('loading');
    setError('');
    setDraft(null);
    try {
      const base = getBackend().replace(/\/+$/, '');
      const env = await postJSON<AnalyzeEnvelope>(`${base}/api/analyze`, { text, clause_type: clauseType || undefined });
      const a = (env?.analysis ?? env) as any;
      a.cid = a.cid || (env as any)?.cid;
      a.clause_type = a.clause_type || clauseType || undefined;
      a.text = a.text || text || undefined;
      setAnalysis(a);
      setAnalysisMeta((env as any)?.meta || null);
      setStatus('ready');
    } catch (e: any) {
      console.error(e);
      const msg = e?.message || 'Analyze failed';
      setError(msg);
      if (e?.status === 422) {
        setToast(msg);
      }
      setStatus('error');
    }
  };

  const callGptDraft = async () => {
    setStatus('loading');
    setError('');
    try {
      const base = getBackend().replace(/\/+$/, '');
      const env = await postJSON<DraftEnvelope>(`${base}${DRAFT_PATH}`, {
        cid: (analysis as any)?.cid,
        clause: analysis?.text || clauseText,
      });
      const text = env?.proposed_text || env?.draft_text || '';
      setDraft({ ...env, proposed_text: text });
      setStatus('ready');
      try { await insertIntoWord(text); } catch {}
    } catch (e: any) {
      console.error(e);
      setError(e?.message || 'Draft failed');
      setStatus('error');
    }
  };

  async function insertIntoWord(text: string) {
    const w: any = window as any;
    if (w?.Office?.context?.document?.setSelectedDataAsync) {
      await new Promise<void>((resolve, reject) =>
        w.Office.context.document.setSelectedDataAsync(
          text,
          { coercionType: w.Office.CoercionType.Text },
          (res: any) =>
            res?.status === w.Office.AsyncResultStatus.Succeeded
              ? resolve()
              : reject(res?.error),
        ),
      );
    } else {
      await navigator.clipboard?.writeText(text).catch(() => {});
      alert('Draft copied to clipboard (Office not ready). Paste it into the document.');
    }
  }

  const findings = Array.isArray(analysis?.findings) ? analysis.findings : [];
  const suggestions = Array.isArray((analysis as any)?.suggestions) ? (analysis as any).suggestions : [];

  const canAnalyze = backendOk && clauseText.trim().length > 0 && status !== 'loading';
  const canDraft = status === 'ready';

  useEffect(() => { setFindingsLimit(PAGE_SIZE); }, [analysis]);

  return (
    <div style={{ padding: '1rem', fontFamily: 'Segoe UI, Arial, sans-serif', color: '#111' }}>
      {toast && (
        <div style={{ position: 'fixed', top: 8, right: 8, background: '#333', color: '#fff', padding: '6px 10px', borderRadius: 4 }}>
          {toast}
        </div>
      )}
      <h2>Draft Assistant (React)</h2>
      <div style={{ marginBottom: 8, fontSize: 12, color: '#444' }}>
        Backend: <code>{getBackend()}</code>
        {meta?.provider && <span> — {meta.provider} {meta.model}</span>}
      </div>

      <label style={{ display: 'block', marginBottom: 6 }}>
        Clause Type:
        <input
          type="text"
          value={clauseType}
          onChange={(e) => setClauseType(e.target.value)}
          style={{ width: '100%', marginTop: 4 }}
          placeholder="e.g., confidentiality"
        />
      </label>

      <label style={{ display: 'block', marginBottom: 6 }}>
        Clause Text:
        <textarea
          value={clauseText}
          onChange={(e) => setClauseText(e.target.value)}
          rows={6}
          style={{ width: '100%', marginTop: 4 }}
          placeholder="Paste clause text here…"
        />
      </label>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button
          onClick={callAnalyze}
          disabled={!canAnalyze}
          style={{ background: '#6c757d', color: 'white', padding: '8px 12px', border: 'none', borderRadius: 4 }}
        >
          {status === 'loading' ? 'Analyzing…' : 'Analyze'}
        </button>

        <button
          onClick={callGptDraft}
          disabled={!canDraft}
          style={{ background: '#007bff', color: 'white', padding: '8px 12px', border: 'none', borderRadius: 4 }}
        >
          {status === 'loading' ? 'Generating…' : 'Get AI Draft'}
        </button>

        {draft?.proposed_text && (
          <button
            onClick={() => insertIntoWord(draft.proposed_text || '')}
            style={{ background: '#28a745', color: 'white', padding: '8px 12px', border: 'none', borderRadius: 4 }}
          >
            Insert result into Word
          </button>
        )}
      </div>

      {status === 'idle' && <div style={{ marginTop: 12 }}>Enter text and press Analyze.</div>}
      {status === 'loading' && <div style={{ marginTop: 12 }}>Loading…</div>}
      {status === 'error' && <div style={{ marginTop: 12, color: 'red' }}>{error} <button onClick={callAnalyze}>Retry</button></div>}
      {status === 'ready' && (
        <>
          <div style={{ marginTop: 16 }}>
            <h3>Findings</h3>
            {findings.length === 0 && (
              <div>No findings (rules_evaluated: {meta.rules_evaluated}, triggered: {meta.rules_triggered})</div>
            )}
            {Array.isArray(findings) &&
              findings.slice(0, findingsLimit).map((f: any, i: number) => (
                <div key={f?.rule_id || i} style={{ background: '#f8f9fa', padding: 8, borderRadius: 4, marginBottom: 6 }}>
                  <div><b>{f?.code || 'FINDING'}</b> {f?.severity ? `(${f.severity})` : ''}</div>
                  <div>{f?.message || ''}</div>
                </div>
              ))}
            {findingsLimit < findings.length && (
              <button onClick={() => setFindingsLimit(findingsLimit + PAGE_SIZE)}>Load more</button>
            )}
          </div>

          {Array.isArray(suggestions) && suggestions.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>Suggestions</h3>
              {Array.isArray(suggestions) &&
                suggestions.map((s: any, i: number) => (
                  <div key={s?.rule_id || i}>{typeof s === 'string' ? s : JSON.stringify(s)}</div>
                ))}
            </div>
          )}

          {draft?.proposed_text && (
            <div style={{ marginTop: 20 }}>
              <h3>Suggested Draft</h3>
              <pre style={{ background: '#f5f5f5', padding: '1rem', borderRadius: 4, whiteSpace: 'pre-wrap' }}>
                {draft.proposed_text}
              </pre>
            </div>
          )}

          {Array.isArray(analysisMeta?.companies_meta) && analysisMeta.companies_meta.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <h3>Company Check</h3>
              {analysisMeta.companies_meta.map((c: any, i: number) => {
                const num = c?.matched?.company_number || c?.from_document?.number;
                const data = (num && companies[num]) || c.matched || {};
                const st = (num && companyStatus[num]) || 'idle';
                const verdict = (c?.verdict || '').toLowerCase();
                let badge = 'NOT FOUND';
                let color = '#6c757d';
                if (verdict === 'ok') { badge = 'OK'; color = '#28a745'; }
                else if (verdict === 'mismatch') { badge = 'MISMATCH'; color = '#ffc107'; }
                return (
                  <div key={i} style={{ border: '1px solid #ddd', padding: 8, borderRadius: 4, marginBottom: 8 }}>
                    <div><b>{data?.company_name || c.from_document?.name}</b> {data?.company_number && `(${data.company_number})`} {badge && (<span style={{background: color, color: '#fff', padding: '2px 4px', borderRadius: 4}}>{badge}</span>)} {st === 'loading' ? '...' : ''}</div>
                    <div style={{ fontSize: 12 }}>Name doc vs registry: {c.from_document?.name} / {data?.company_name || '—'}</div>
                    {st === 'loading' && <div style={{ fontSize: 12, color: '#888' }}>Loading...</div>}
                    {st === 'error' && <div style={{ fontSize: 12, color: 'red' }}>Failed to load</div>}
                    {data?.registered_office && (
                      <div style={{ fontSize: 12 }}>Address: {data.registered_office.postcode || ''}</div>
                    )}
                    {Array.isArray(data?.sic_codes) && data.sic_codes.length > 0 && (
                      <div style={{ fontSize: 12 }}>SIC: {data.sic_codes.join(', ')}</div>
                    )}
                    {data?.incorporated_on && (
                      <div style={{ fontSize: 12 }}>Incorporated: {data.incorporated_on}</div>
                    )}
                    {data?.company_number && (
                      <a href={`https://find-and-update.company-information.service.gov.uk/company/${data.company_number}`} target="_blank" rel="noopener noreferrer">Open in Companies House</a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export { DraftAssistantPanel };

const mount = document.getElementById('root');
if (mount) {
  try {
    // @ts-ignore - runtime check for React 18
    const { createRoot } = (ReactDOM as any);
    if (createRoot) {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      createRoot(mount).render(<React.StrictMode><Boundary><DraftAssistantPanel /></Boundary></React.StrictMode>);
    } else {
      ReactDOM.render(
        <React.StrictMode><Boundary><DraftAssistantPanel /></Boundary></React.StrictMode>,
        mount
      );
    }
  } catch {
    ReactDOM.render(
      <React.StrictMode><Boundary><DraftAssistantPanel /></Boundary></React.StrictMode>,
      mount
    );
  }
}
