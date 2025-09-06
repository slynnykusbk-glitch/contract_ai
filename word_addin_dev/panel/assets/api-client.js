// Unified API client for panel + self-test
export const API = (() => {
  const SCHEMA = "1.3";
  const base = () => (localStorage.getItem("backendUrl") || "https://localhost:9443").replace(/\/+$/,"");

  const parse = async (res) => {
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = { status: "error", detail: "bad json", raw: text }; }
    const headers = {
      cid: res.headers.get("x-cid"),
      cache: res.headers.get("x-cache"),
      latency: res.headers.get("x-latency-ms"),
      schema: res.headers.get("x-schema-version") || data.x_schema_version || data.schema_version,
      provider: res.headers.get("x-provider"),
      model: res.headers.get("x-model"),
      mode: res.headers.get("x-llm-mode"),
      usage: res.headers.get("x-usage-total"),
    };
    const ok = String(data?.status || "").toLowerCase() === "ok";
    const aok = String(data?.analysis?.status || "ok").toLowerCase() === "ok";
    return { ok: res.ok && ok && aok, http: res.status, headers, data };
  };

  const req = (path, init={}) => fetch(base()+path, {
    method: init.method || "GET",
    headers: Object.assign({ "content-type":"application/json", "x-cid": crypto.randomUUID() }, init.headers||{}),
    body: init.body,
    credentials: "include",
  }).then(parse);

  return {
    health:   () => req("/health"),
    analyze:  (text, mode="live") => req("/api/analyze", { method:"POST", body: JSON.stringify({ text, mode }) }),
    summary:  (text) => req("/api/summary", { method:"POST", body: JSON.stringify({ text }) }),
    gptDraft: (text, mode="friendly") => req("/api/gpt-draft", { method:"POST", body: JSON.stringify({ text, mode }) }),
    suggest:  (text, mode="friendly") => req("/api/suggest_edits", { method:"POST", body: JSON.stringify({ text, mode }) }),
    qaRecheck:(text, rules=[]) => req("/api/qa-recheck", { method:"POST", body: JSON.stringify({ text, rules }) }),
    trace:    (cid) => req(`/api/trace/${encodeURIComponent(cid)}`),
  };
})();
