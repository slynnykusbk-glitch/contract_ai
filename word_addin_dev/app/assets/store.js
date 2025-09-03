/* eslint-disable */
(function (root) {
  const DEFAULT_BASE = "https://localhost:9443";
  const S = {
    baseUrl: localStorage.getItem("backendUrl") || DEFAULT_BASE,
    risk:    localStorage.getItem("risk") || "medium",
    lastCid: null,
    meta: { cid:"", cache:"", latencyMs:0, schema:"", provider:"", model:"", llm_mode:"", usage:"" },
    last: { analyze:null, summary:null, draft:null, suggest:null }
  };
  function setBase(u){ S.baseUrl = u; try { localStorage.setItem("backendUrl", u); } catch {} }
  function setRisk(r){ S.risk = r; try { localStorage.setItem("risk", r); } catch {} }
  function setMeta(m){ S.meta = { ...S.meta, ...m }; if (m && m.cid) S.lastCid = m.cid; }
  function get(){ return S; }
  root.CAI = root.CAI || {};
  root.CAI.Store = { setBase, setRisk, setMeta, get, DEFAULT_BASE };
}(typeof self !== "undefined" ? self : this));
