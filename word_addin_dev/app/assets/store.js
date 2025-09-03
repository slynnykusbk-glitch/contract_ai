/* eslint-disable */
(function (root) {
  const DEFAULT_BASE = "https://localhost:9443";
  const S = {
    baseUrl: localStorage.getItem("backendUrl") || DEFAULT_BASE,
    lastCid: null,
    meta: { cid:"", cache:"", latencyMs:0, schema:"", provider:"", model:"", llm_mode:"", usage:"" },
    last: { analyze:null, summary:null, draft:null, suggest:null }
  };
  function setBase(u){ 
    const v = (String(u||"").trim() || DEFAULT_BASE).replace(/^http:\/\//i,"https://").replace(/\/+$/,"");
    S.baseUrl = v; 
    try { localStorage.setItem("backendUrl", v); } catch {}
  }
  function setMeta(m){ S.meta = { ...S.meta, ...m }; if (m && m.cid) S.lastCid = m.cid; }
  function get(){ return S; }
  root.CAI = root.CAI || {};
  root.CAI.Store = { setBase, setMeta, get, DEFAULT_BASE };
}(typeof self !== "undefined" ? self : this));
