import React, { useState } from "react";
import ReactDOM from "react-dom";

type Status = "ok" | "warn" | "fail";

const DEFAULT_BACKEND = "http://127.0.0.1:9000";
const LS_KEY = "contract_ai_backend";

function getBackend(): string {
  try {
    const v = (localStorage.getItem(LS_KEY) || "").trim();
    return v || DEFAULT_BACKEND;
  } catch {
    return DEFAULT_BACKEND;
  }
}

type Citation = {
  system?: string;          // "UK"
  instrument?: string;      // e.g., "UK GDPR"
  section?: string;         // e.g., "Art. 32"
};

interface AnalysisFinding {
  code?: string;
  message?: string;
  severity?: string;        // may come as "minor/major/critical" or "low/..."
  evidence?: string;
  citations?: Citation[];
  legal_basis?: string[];   // legacy tolerance
  [k: string]: any;
}

interface AnalysisOutput {
  clause_type?: string;
  text?: string;
  status?: string;          // "OK" | "WARN" | "FAIL"
  score?: number;
  risk?: string;
  findings?: AnalysisFinding[];
  recommendations?: string[];
  citations?: Citation[];
  [k: string]: any;
}

interface AnalyzeEnvelope {
  analysis?: AnalysisOutput;
  results?: any;
  clauses?: any[];
  document?: any;
  [k: string]: any;
}

interface DraftEnvelope {
  status?: Status | string;
  model?: string;
  draft_text?: string;
  alternatives?: any[];
  meta?: any;
  [k: string]: any;
}

async function postJSON<T = any>(path: string, body: any): Promise<T> {
  const base = getBackend().replace(/\/+$/, "");
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-cid": crypto?.randomUUID ? crypto.randomUUID() : String(Date.now()),
    },
    body: JSON.stringify(body || {}),
  });
  const text = await res.text();
  let json: any = {};
  try { json = text ? JSON.parse(text) : {}; } catch { /* tolerate */ }
  if (!res.ok) {
    const msg = json?.title || json?.detail || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  // Envelope tolerant: some responses have { data: {...} }
  return (json?.data ?? json) as T;
}

function renderCitations(cits?: Citation[] | string[]): string {
  if (!cits || !Array.isArray(cits) || cits.length === 0) return "";
  if (typeof cits[0] === "string") return (cits as string[]).join(", ");
  return (cits as Citation[])
    .map((c) => [c.instrument, c.section].filter(Boolean).join(" "))
    .filter(Boolean)
    .join("; ");
}

const DraftAssistantPanel: React.FC = () => {
  const [clauseType, setClauseType] = useState("");
  const [clauseText, setClauseText] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisOutput | null>(null);
  const [draft, setDraft] = useState<DraftEnvelope | null>(null);
  const [loadingAnalyze, setLoadingAnalyze] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const callAnalyze = async () => {
    setLoadingAnalyze(true);
    setError(null);
    setDraft(null);
    try {
      const env = await postJSON<AnalyzeEnvelope>("/api/analyze", {
        text: clauseText,
        clause_type: clauseType || undefined,
      });
      const a = (env?.analysis ?? env) as AnalysisOutput;
      // Backfill minimal fields
      a.clause_type = a.clause_type || clauseType || undefined;
      a.text = a.text || clauseText || undefined;
      setAnalysis(a);
    } catch (e: any) {
      setError(e?.message || "Analyze failed");
    } finally {
      setLoadingAnalyze(false);
    }
  };

  const callGptDraft = async () => {
    if (!analysis) {
      setError("Run Analyze first.");
      return;
    }
    setLoadingDraft(true);
    setError(null);
    try {
      const env = await postJSON<DraftEnvelope>("/api/gpt/draft", {
        analysis,
        mode: "friendly",
      });
      setDraft(env);
    } catch (e: any) {
      setError(e?.message || "Draft failed");
    } finally {
      setLoadingDraft(false);
    }
  };

  const findings = analysis?.findings || [];

  return (
    <div style={{ padding: "1rem", fontFamily: "Segoe UI, Arial, sans-serif", color: "#111" }}>
      <h2>Draft Assistant (React)</h2>

      <div style={{ marginBottom: 8, fontSize: 12, color: "#444" }}>
        Backend: <code>{getBackend()}</code>
      </div>

      <label style={{ display: "block", marginBottom: 6 }}>
        Clause Type:
        <input
          type="text"
          value={clauseType}
          onChange={(e) => setClauseType(e.target.value)}
          style={{ width: "100%", marginTop: 4 }}
          placeholder="e.g., confidentiality"
        />
      </label>

      <label style={{ display: "block", marginBottom: 6 }}>
        Clause Text:
        <textarea
          value={clauseText}
          onChange={(e) => setClauseText(e.target.value)}
          rows={6}
          style={{ width: "100%", marginTop: 4 }}
          placeholder="Paste clause text here…"
        />
      </label>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button
          onClick={callAnalyze}
          disabled={loadingAnalyze}
          style={{ background: "#6c757d", color: "white", padding: "8px 12px", border: "none", borderRadius: 4 }}
        >
          {loadingAnalyze ? "Analyzing…" : "Analyze"}
        </button>

        <button
          onClick={callGptDraft}
          disabled={loadingDraft || !analysis}
          style={{ background: "#007bff", color: "white", padding: "8px 12px", border: "none", borderRadius: 4 }}
        >
          {loadingDraft ? "Generating…" : "Get AI Draft"}
        </button>
      </div>

      {error && <div style={{ marginTop: 12, color: "red" }}>Warning: {error}</div>}

      {analysis && (
        <div style={{ marginTop: 16 }}>
          <h3>Findings</h3>
          {findings.length === 0 && <div>—</div>}
          {findings.map((f, i) => (
            <div key={i} style={{ background: "#f8f9fa", padding: 8, borderRadius: 4, marginBottom: 6 }}>
              <div><b>{f.code || "FINDING"}</b> {f.severity ? `(${f.severity})` : ""}</div>
              <div>{f.message || ""}</div>
              {f.evidence && <div style={{ color: "#555", fontSize: 12 }}>Evidence: {f.evidence}</div>}
              {(f.citations || f.legal_basis)?.length ? (
                <div style={{ color: "#555", fontSize: 12 }}>
                  Basis: {renderCitations((f.citations as any) || f.legal_basis)}
                </div>
              ) : null}
            </div>
          ))}

          <div style={{ marginTop: 10, fontSize: 14 }}>
            <span style={{ marginRight: 12 }}>Score: <b>{analysis.score ?? "—"}</b></span>
            <span style={{ marginRight: 12 }}>Risk: <b>{analysis.risk ?? "—"}</b></span>
            <span>Status: <b>{analysis.status ?? "—"}</b></span>
          </div>
        </div>
      )}

      {draft && (
        <div style={{ marginTop: 20 }}>
          <h3>Suggested Draft</h3>
          <pre style={{ background: "#f5f5f5", padding: "1rem", borderRadius: 4, whiteSpace: "pre-wrap" }}>
            {draft.draft_text || ""}
          </pre>

          <div style={{ marginTop: 8, fontSize: 14 }}>
            <span style={{ marginRight: 12 }}>Status: <b>{String(draft.status || "ok")}</b></span>
            <span>Model: <b>{draft.model || "rule-based"}</b></span>
          </div>
        </div>
      )}
    </div>
  );
};

export default DraftAssistantPanel;

// React 17 fallback; if React 18 is used, createRoot will exist on react-dom/client
const mount = document.getElementById("root");
if (mount) {
  try {
    // @ts-ignore - runtime check for React 18
    const { createRoot } = (ReactDOM as any);
    if (createRoot) {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      createRoot(mount).render(<React.StrictMode><DraftAssistantPanel /></React.StrictMode>);
    } else {
      ReactDOM.render(
        <React.StrictMode><DraftAssistantPanel /></React.StrictMode>,
        mount
      );
    }
  } catch {
    ReactDOM.render(
      <React.StrictMode><DraftAssistantPanel /></React.StrictMode>,
      mount
    );
  }
}
