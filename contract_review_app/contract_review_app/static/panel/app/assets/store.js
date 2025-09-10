/* eslint-disable */
(function (root) {
  const DEFAULT_BASE = "https://localhost:9443";
  const S = {
    baseUrl: localStorage.getItem("backendUrl") || DEFAULT_BASE,
    risk:    localStorage.getItem("risk") || "medium",
    apiKey:  localStorage.getItem("api_key") || "",
    schemaVersion: localStorage.getItem("schemaVersion") || "",
    lastCid: null,
    meta: { cid:"", cache:"", latencyMs:0, schema:"", provider:"", model:"", llm_mode:"", usage:"" },
    last: { analyze:null, summary:null, draft:null, suggest:null }
  };
  function setBase(u){ S.baseUrl = u; try { localStorage.setItem("backendUrl", u); } catch {} }
  function setRisk(r){ S.risk = r; try { localStorage.setItem("risk", r); } catch {} }
  function setApiKey(k){ S.apiKey = k; try { localStorage.setItem("api_key", k); } catch {} }
  function setSchemaVersion(v){ S.schemaVersion = v; try { localStorage.setItem("schemaVersion", v); } catch {} }
  function setMeta(m){
    S.meta = { ...S.meta, ...m };
    if (m && m.cid) S.lastCid = m.cid;
    if (m && m.schema) setSchemaVersion(m.schema);
  }
  function get(){ return S; }
  root.CAI = root.CAI || {};
  root.CAI.Store = { setBase, setRisk, setMeta, setApiKey, setSchemaVersion, get, DEFAULT_BASE };
}(typeof self !== "undefined" ? self : this));

window.CAI = window.CAI || {};
CAI.store = CAI.store || {};
CAI.store.get = CAI.store.get || ((k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } });
CAI.store.set = CAI.store.set || ((k, v) => { localStorage.setItem(k, JSON.stringify(v)); });
CAI.store.setLastInput = (inp) => CAI.store.set("lastInput", inp);
CAI.store.getLastInput = () => CAI.store.get("lastInput", null);
CAI.store.updateSuggestion = (id, patch) => {
  const arr = CAI.store.get("cai:suggestions", []);
  const ix = arr.findIndex(x => x.id === id);
  if (ix >= 0) {
    arr[ix] = { ...arr[ix], ...patch };
    CAI.store.set("cai:suggestions", arr);
    return arr[ix];
  }
  return null;
};

// === B9-S4: UI helpers ===
const __busy = new Set();
export function setBusy(key, on) {
  if (on) __busy.add(key); else __busy.delete(key);
  const busy = __busy.size > 0;
  document.body.dataset.busy = busy ? "1" : "0";
  // дизейблим все элементы с классом-хелпером
  document.querySelectorAll(".js-disable-while-busy").forEach(el => {
    el.toggleAttribute("disabled", busy);
    if (busy) el.classList.add("is-busy"); else el.classList.remove("is-busy");
  });
}

let __debounceTimers = new Map();
export function debounce(fn, ms = 450) {
  return (...args) => {
    const key = fn; // один таймер на функцию
    clearTimeout(__debounceTimers.get(key));
    __debounceTimers.set(key, setTimeout(() => fn(...args), ms));
  };
}

const KEY = "cai:last_analyze";
export function saveLastAnalyze({ cid, docHash, risk }) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ cid, docHash, risk, ts: Date.now() }));
  } catch {}
}

export function getLastAnalyze() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "null");
  } catch {
    return null;
  }
}

// === learning event queue ===
const QKEY = "cai_learning_queue_v1";

export function enqueueLearning(evt) {
  try {
    const q = JSON.parse(localStorage.getItem(QKEY) || "[]");
    const id = `${evt.cid||"nocid"}|${evt.ts}|${evt.action}|${evt.rule_id||"norule"}`;
    if (!q.find(x => x._id === id)) { q.push({ ...evt, _id: id }); }
    localStorage.setItem(QKEY, JSON.stringify(q));
  } catch {}
}

export function readQueue() {
  try { return JSON.parse(localStorage.getItem(QKEY) || "[]"); } catch { return []; }
}

export function dropFromQueue(ids) {
  try {
    const q = readQueue().filter(x => !ids.includes(x._id));
    localStorage.setItem(QKEY, JSON.stringify(q));
  } catch {}
}
