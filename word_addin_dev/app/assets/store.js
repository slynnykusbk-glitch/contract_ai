/* eslint-disable */
(function (root) {
  const S = {
    baseUrl: localStorage.getItem("backendUrl") || "https://localhost:9443",
    lastCid: null,
    meta: { cid:"", cache:"", latencyMs:0, schema:"", provider:"", model:"", llm_mode:"", usage:"" },
    last: { analyze:null, summary:null, draft:null, suggest:null }
  };
  function setBase(u){ S.baseUrl = u; localStorage.setItem("backendUrl", u); }
  function setMeta(m){ S.meta = { ...S.meta, ...m }; if (m.cid) S.lastCid = m.cid; }
  function get(){ return S; }
  root.CAI = root.CAI || {};
  root.CAI.Store = { setBase, setMeta, get };
}(typeof self !== "undefined" ? self : this));
