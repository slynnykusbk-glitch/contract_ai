/* eslint-disable */
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.CAI = root.CAI || {};
    root.CAI.API = factory();
  }
}(typeof self !== "undefined" ? self : this, function () {
  const SCHEMA = "1.3";
  const DEFAULT_BASE = "https://localhost:9443";

  // ---- helpers
  const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const uuid = () => (crypto?.randomUUID?.() || Math.random().toString(16).slice(2) + Date.now());

  function normBase(u) {
    try {
      if (!u) return DEFAULT_BASE;
      let s = String(u).trim();
      s = s.replace(/^http:\/\//i, "https://").replace(/\/+$/,"" );
      return s || DEFAULT_BASE;
    } catch { return DEFAULT_BASE; }
  }

  function isOk(v) { return String(v || "").toLowerCase() === "ok"; }
  function versionOf(body, headers) {
    return headers.get("x-schema-version") || body?.x_schema_version || body?.schema_version || null;
  }

  // ---- shared fetch wrapper with retry/backoff + contract guards
  async function _doFetch({ base, path, method, body, headers, timeoutMs, retry }) {
    const url = normBase(base) + path;
    const ctrl = new AbortController();
    const tOut = setTimeout(() => ctrl.abort("timeout"), timeoutMs);
    const t0 = now();
    let resp, text = "", json = null, err = null;
    try {
      resp = await fetch(url, {
        method: method || "GET",
        headers: headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
        credentials: "include"
      });
      text = await resp.text();
      try { json = text ? JSON.parse(text) : {}; } catch { json = { status: "error", title:"bad-json", detail:"Response is not JSON", raw: text }; }
    } catch (e) {
      err = e;
    } finally {
      clearTimeout(tOut);
    }

    const t1 = now();
    const hdr = (name) => (resp?.headers?.get(name) || "");
    const meta = {
      http: resp?.status || 0,
      latencyMs: Number(hdr("x-latency-ms")) || Math.round(t1 - t0),
      headers: {
        cid: hdr("x-cid") || "",
        cache: hdr("x-cache") || "",
        schema: hdr("x-schema-version") || "",
        provider: hdr("x-provider") || "",
        model: hdr("x-model") || "",
        llm_mode: hdr("x-llm-mode") || "",
        usage: hdr("x-usage-total") || ""
      }
    };

    // contract guard + tolerate old shapes
    const bodyStatus = json?.status;
    const analysisStatus = json?.analysis?.status;
    const bodyOk = isOk(bodyStatus);
    const analysisOk = analysisStatus == null ? true : isOk(analysisStatus);
    const schema = meta.headers.schema || versionOf(json, resp?.headers || new Headers());
    const ok = !!(resp?.ok && bodyOk && analysisOk);

    const result = { ok, http: meta.http, data: json, meta: { ...meta, schema } };

    // retry policy
    const retriable = (code) => [429, 502, 503, 504].includes(code);
    if ((!resp || !resp.ok) && retry.left > 0) {
      const code = meta.http || (err ? 0 : 500);
      if (retriable(code) || err === "timeout") {
        const backoff = clamp(retry.baseMs * Math.pow(2, retry.attempt), retry.baseMs, retry.maxMs);
        await sleep(backoff);
        return _doFetch({ base, path, method, body, headers, timeoutMs, retry: { ...retry, attempt: retry.attempt + 1, left: retry.left - 1 } });
      }
    }

    // contract mismatch banner trigger
    if (resp?.ok && !ok) {
      result.contractMismatch = {
        bodyStatus, analysisStatus, schema,
        note: "Response HTTP ok, but status not ok or analysis.status not ok"
      };
    }

    if (!resp?.ok && !err && json?.title) {
      result.problem = { title: json.title, detail: json.detail || "", code: json.code || json.error_code || "" };
    }
    if (err) result.error = String(err);

    return result;
  }

  async function request(path, { method="GET", body=null, timeoutMs=30000, cid=null } = {}) {
    const base = localStorage.getItem("backendUrl") || DEFAULT_BASE;
    const headers = new Headers({
      "content-type": "application/json",
      "x-schema-version": SCHEMA,
      "x-idempotency-key": uuid(),
      "x-cid": cid || uuid(),
      "x-client-build": (window.__BUILD_ID__ || "dev")
    });
    const retry = { baseMs: 250, maxMs: 2000, attempt: 0, left: 2 }; // 3 попытки всего
    return _doFetch({ base, path, method, body, headers, timeoutMs, retry });
  }

  // ---- public API
  const API = {
    health:   () => request("/health"),
    analyze:  (text, mode="live") => request("/api/analyze", { method:"POST", body:{ text, mode } }),
    summary:  (text) => request("/api/summary", { method:"POST", body:{ text } }),
    gptDraft: (text, mode="friendly") => request("/api/gpt-draft", { method:"POST", body:{ text, mode } }),
    suggest:  (text, mode="friendly") => request("/api/suggest_edits", { method:"POST", body:{ text, mode } }),
    qaRecheck:(text, rules=[]) => request("/api/qa-recheck", { method:"POST", body:{ text, rules } }),
    trace:    (cid) => request(`/api/trace/${encodeURIComponent(cid)}`)
  };

  return API;
}));
