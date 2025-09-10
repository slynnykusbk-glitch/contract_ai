import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { asArray } from '../common/safe';
import { postJSON, getHealth } from '../common/http';

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
  draft_text?: string;
  [k: string]: any;
}

const DraftAssistantPanel: React.FC = () => {
  const [clauseType, setClauseType] = useState('');
  const [clauseText, setClauseText] = useState('');
  const [analysis, setAnalysis] = useState<any>(null);
  const [draft, setDraft] = useState<DraftEnvelope | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState('');
  const [backendOk, setBackendOk] = useState(false);
  const [meta, setMeta] = useState<any>({});
  const PAGE_SIZE = 100;
  const [findingsLimit, setFindingsLimit] = useState(PAGE_SIZE);

  useEffect(() => {
    if (!localStorage.getItem('api_key')) {
      try { new URL(window.location.href); localStorage.setItem('api_key', 'local-test-key-123'); } catch {}
    }
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
    setStatus('loading');
    setError('');
    setDraft(null);
    try {
      const base = getBackend().replace(/\/+$/, '');
      const env = await postJSON<AnalyzeEnvelope>(`${base}/api/analyze`, { text: clauseText, clause_type: clauseType || undefined });
      const a = (env?.analysis ?? env) as any;
      a.clause_type = a.clause_type || clauseType || undefined;
      a.text = a.text || clauseText || undefined;
      setAnalysis(a);
      setStatus('ready');
    } catch (e: any) {
      console.error(e);
      setError(e?.message || 'Analyze failed');
      setStatus('error');
    }
  };

  const callGptDraft = async () => {
    setStatus('loading');
    setError('');
    try {
      const base = getBackend().replace(/\/+$/, '');
      const env = await postJSON<DraftEnvelope>(`${base}${DRAFT_PATH}`, { clause: analysis?.text || clauseText });
      setDraft(env);
      setStatus('ready');
      try { await insertIntoWord(env?.draft_text || ''); } catch {}
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

  const findings = asArray(analysis?.findings);
  const suggestions = asArray((analysis as any)?.suggestions);

  const canAnalyze = backendOk && clauseText.trim().length > 0 && status !== 'loading';
  const canDraft = status === 'ready';

  useEffect(() => { setFindingsLimit(PAGE_SIZE); }, [analysis]);

  return (
    <div style={{ padding: '1rem', fontFamily: 'Segoe UI, Arial, sans-serif', color: '#111' }}>
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

        {draft?.draft_text && (
          <button
            onClick={() => insertIntoWord(draft.draft_text || '')}
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
            {findings.length === 0 && <div>—</div>}
            {findings.slice(0, findingsLimit).map((f: any, i: number) => (
              <div key={i} style={{ background: '#f8f9fa', padding: 8, borderRadius: 4, marginBottom: 6 }}>
                <div><b>{f.code || 'FINDING'}</b> {f.severity ? `(${f.severity})` : ''}</div>
                <div>{f.message || ''}</div>
              </div>
            ))}
            {findingsLimit < findings.length && (
              <button onClick={() => setFindingsLimit(findingsLimit + PAGE_SIZE)}>Load more</button>
            )}
          </div>

          {suggestions.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h3>Suggestions</h3>
              {suggestions.map((s: any, i: number) => (
                <div key={i}>{typeof s === 'string' ? s : JSON.stringify(s)}</div>
              ))}
            </div>
          )}

          {draft?.draft_text && (
            <div style={{ marginTop: 20 }}>
              <h3>Suggested Draft</h3>
              <pre style={{ background: '#f5f5f5', padding: '1rem', borderRadius: 4, whiteSpace: 'pre-wrap' }}>
                {draft.draft_text}
              </pre>
            </div>
          )}
        </>
      )}
    </div>
  );
};

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
