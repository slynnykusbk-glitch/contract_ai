(function(){
  // ================== Guard so inline fallback doesn't double-bind ==================
  if (window.__CAI_WIRED__) return;
  window.__CAI_WIRED__ = true;

  // ================== Build / Globals ==================
  var BUILD = (function(){
    try{
      var u = new URL(window.location.href);
      return u.searchParams.get("v") || (window.__BUILD_ID__ || ("dev-" + Date.now()));
    }catch(_){ return window.__BUILD_ID__ || "dev"; }
  })();

  var els = {};
  var CAI_STORE = window.CAI_STORE || (window.CAI_STORE = {
    settings: { riskThreshold: "high" },
    status:   { cid:null, xcache:null, latencyMs:null, schemaVersion:null },
    analysis: { analysis:null, results:null, clauses:[], document:null }
  });

  // ================== DOM helpers ==================
  function $(id){ return document.getElementById(id); }
  function val(e){ return e ? (e.value || "") : ""; }
  function setVal(e, v){ if(e) e.value = (v==null?"":String(v)); }
  function txt(e, v){ if(e) e.textContent = (v==null?"":String(v)); }
  function en(e,on){ if(e) e.disabled = !on; }
  function log(s){
    try{ var n = els.console; if(!n) return;
      n.appendChild(document.createTextNode(String(s)+"\n"));
      n.scrollTop = n.scrollHeight;
    }catch(_){}
  }
  function status(s){ log("[STATUS] " + s); }

  // ================== Local Storage ==================
  var LS_KEY = "contract_ai_backend";
  function readLS(k){ try { return localStorage.getItem(k) || ""; } catch(_){ return ""; } }
  function writeLS(k,v){ try { localStorage.setItem(k,v); return true; } catch(_){ return false; } }

  // ================== Backend URL ==================
  function sanitizeUrl(u){ if(!u) return ""; return String(u).trim().replace(/\/+$/,""); }
  function backend(){
    var def = (location.protocol === "https:") ? "https://localhost:9000" : "http://127.0.0.1:9000";
    return sanitizeUrl(val(els.backend) || readLS(LS_KEY) || def);
  }

  // ================== Security/Idempotency helpers ==================
  function _manifestSrc(){
    try{ var u = new URL(window.location.href); return u.searchParams.get("v") || u.toString(); }
    catch(_){ return window.location.href; }
  }
  function _cid(){ return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : ("cid-" + Date.now()); }
  function normalizeText(s){ return (s ? String(s).replace(/\s+/g," ").trim() : ""); }
  function sha256Hex(str){
    if (window.crypto && window.crypto.subtle && window.TextEncoder) {
      var enc = new TextEncoder().encode(str);
      return crypto.subtle.digest("SHA-256", enc).then(function(buf){
        var a = Array.from(new Uint8Array(buf));
        return a.map(function(b){ return ("00" + b.toString(16)).slice(-2); }).join("");
      });
    }
    // Non-crypto fallback (cache key only)
    var h = 2166136261>>>0;
    for (var i=0;i<str.length;i++){ h ^= str.charCodeAt(i); h += (h<<1)+(h<<4)+(h<<7)+(h<<8)+(h<<24); }
    return Promise.resolve(("00000000"+(h>>>0).toString(16)).slice(-8));
  }

  // ================== HTTP wrappers ==================
  function httpGet(url, to){
    return new Promise(function(resolve,reject){
      var x = new XMLHttpRequest();
      x.open("GET", url, true);
      x.setRequestHeader("x-panel-build", BUILD);
      x.setRequestHeader("x-manifest-src", _manifestSrc());
      x.setRequestHeader("x-cid", _cid());
      x.timeout = to || 8000;
      x.onreadystatechange = function(){
        if (x.readyState===4){
          resolve({ ok:(x.status>=200 && x.status<300), status:x.status, text:x.responseText, xhr:x });
        }
      };
      x.onerror = function(){ reject(new Error("network error")); };
      x.ontimeout = function(){ reject(new Error("timeout")); };
      x.send();
    });
  }

  function postJSONWithHeaders(url, body, headers, to){
    return new Promise(function(resolve,reject){
      var x = new XMLHttpRequest();
      x.open("POST", url, true);
      x.setRequestHeader("Content-Type","application/json");
      x.setRequestHeader("x-panel-build", BUILD);
      x.setRequestHeader("x-manifest-src", _manifestSrc());
      x.setRequestHeader("x-cid", _cid());
      if (headers && typeof headers==="object"){
        Object.keys(headers).forEach(function(k){
          try{ x.setRequestHeader(k, headers[k]); } catch(_){}
        });
      }
      x.timeout = to || 30000;
      x.onreadystatechange = function(){
        if (x.readyState===4){
          var txt = x.responseText || "";
          var j = null; try{ j = txt ? JSON.parse(txt) : null; } catch(_){ j = null; }
          var hdr = function(n){ try{ return x.getResponseHeader(n) || ""; } catch(_){ return ""; } };
          resolve({
            ok: (x.status>=200 && x.status<300),
            status: x.status,
            text: txt,
            json: j,
            headers: {
              cid: hdr("x-cid"),
              xcache: hdr("x-cache"),
              schema: hdr("x-schema-version")
            }
          });
        }
      };
      x.onerror = function(){ reject(new Error("network error")); };
      x.ontimeout = function(){ reject(new Error("timeout")); };
      x.send(JSON.stringify(body || {}));
    });
  }

  // ================== API Facade ==================
  function updateBadgesFromHeaders(h){
    txt(els.cidBadge, h && h.cid ? h.cid : "—");
    txt(els.xcacheBadge, h && h.xcache ? h.xcache : "—");
    txt(els.schemaBadge, h && h.schema ? h.schema : "—");
    if (CAI_STORE.status.latencyMs!=null) txt(els.latencyBadge, CAI_STORE.status.latencyMs + " ms");
  }

  async function apiAnalyze(text, policyPack){
    var v = backend(); if(!v) throw new Error("backend not set");
    var norm = normalizeText(text||"");
    var pol = policyPack ? JSON.stringify(policyPack).toLowerCase() : "{}";
    var idem = await sha256Hex(norm + "|" + pol);
    var t0 = (performance && performance.now) ? performance.now() : Date.now();
    var r = await postJSONWithHeaders(v + "/api/analyze", { text:text||"", policy_pack:policyPack||null }, { "x-idempotency-key": idem }, 30000);
    var t1 = (performance && performance.now) ? performance.now() : Date.now();
    CAI_STORE.status.latencyMs = Math.max(0, Math.round(t1 - t0));
    CAI_STORE.status.cid        = (r.headers && r.headers.cid)    || (r.json && r.json.meta && r.json.meta.cid) || null;
    CAI_STORE.status.xcache     = (r.headers && r.headers.xcache) || (r.json && r.json.meta && r.json.meta.cache) || null;
    CAI_STORE.status.schemaVersion = (r.headers && r.headers.schema) || (r.json && r.json.meta && r.json.meta.schema_version) || null;
    updateBadgesFromHeaders(r.headers||{});
    return r;
  }

  async function apiDraft(input){
    var v = backend(); if(!v) throw new Error("backend not set");
    var t0 = (performance && performance.now) ? performance.now() : Date.now();
    var r = await postJSONWithHeaders(v + "/api/gpt/draft", input || {}, {}, 25000);
    var t1 = (performance && performance.now) ? performance.now() : Date.now();
    CAI_STORE.status.latencyMs = Math.max(0, Math.round(t1 - t0));
    updateBadgesFromHeaders(r.headers||{});
    return r;
  }

  async function apiSuggestEdits(text, clauseId, mode, topK){
    var v = backend(); if(!v) throw new Error("backend not set");
    var body = { text: text||"", clause_id: clauseId||"", mode: mode||"friendly", top_k: (topK||3) };
    var r = await postJSONWithHeaders(v + "/api/suggest_edits", body, {}, 25000);
    updateBadgesFromHeaders(r.headers||{});
    return r;
  }

  async function apiQARecheck(text, applied){
    var v = backend(); if(!v) throw new Error("backend not set");
    var t0 = (performance && performance.now) ? performance.now() : Date.now();
    var r = await postJSONWithHeaders(v + "/api/qa-recheck", { text:text||"", applied_changes:Array.isArray(applied)?applied:[] }, {}, 20000);
    var t1 = (performance && performance.now) ? performance.now() : Date.now();
    CAI_STORE.status.latencyMs = Math.max(0, Math.round(t1 - t0));
    updateBadgesFromHeaders(r.headers||{});
    return r;
  }

  async function apiLearningLog(events){
    var v = backend(); if(!v) throw new Error("backend not set");
    return postJSONWithHeaders(v + "/api/learning/log", { events: Array.isArray(events)?events.slice(0,100):[] }, {}, 15000);
  }

  // ================== Office helpers ==================
  function ensureOfficeBadge(){
    try{
      if (!window.Office || !Office.onReady){ txt(els.officeBadge,"Office: —"); return; }
      Office.onReady(function(info){
        txt(els.officeBadge, "Office: " + (info && info.host ? info.host : "Ready"));
      });
    }catch(_){ txt(els.officeBadge,"Office: error"); }
  }

  function readSelection(){
    if (!window.Word || !Word.run) return Promise.resolve("");
    return Word.run(function(ctx){
      var s = ctx.document.getSelection(); s.load("text");
      return ctx.sync().then(function(){ return s.text || ""; });
    });
  }

  function readWholeDoc(){
    if (!window.Word || !Word.run) return Promise.resolve(val(els.clause)||"");
    return Word.run(function(ctx){
      var b = ctx.document.body; b.load("text");
      return ctx.sync().then(function(){ return b.text || ""; });
    });
  }

  async function insertPlain(text){
    if (!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function(ctx){
      var sel = ctx.document.getSelection();
      sel.insertText(String(text||""), "Replace");
      return ctx.sync();
    });
  }

  async function applyTracked(text, commentText){
    if (!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function(ctx){
      try{ if (ctx.document && ctx.document.changeTrackingMode) ctx.document.changeTrackingMode = Word.ChangeTrackingMode.trackAll; }catch(_){}
      var sel = ctx.document.getSelection(); sel.load("text");
      return ctx.sync().then(function(){
        sel.insertText(String(text||""), "Replace");
        try{ sel.insertComment(commentText || "Contract AI — applied draft"); }catch(_){}
        return ctx.sync();
      });
    });
  }

  async function acceptAll(){ if(!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function(ctx){ try{ ctx.document.acceptAllChanges(); }catch(_){ } return ctx.sync(); });
  }

  async function rejectAll(){ if(!window.Word || !Word.run) throw new Error("Word API not available");
    return Word.run(function(ctx){ try{ ctx.document.rejectAllChanges(); }catch(_){ } return ctx.sync(); });
  }

  // ================== Rendering ==================
  function _riskOrd(v){
    v = String(v||"").toLowerCase();
    if (v==="critical") return 3;
    if (v==="high") return 2;
    if (v==="medium") return 1;
    return 0;
  }

  function emojiForSeverity(s){
    var m = String(s||"").toLowerCase();
    if(m==="critical") return "🛑";
    if(m==="high")     return "🔴";
    if(m==="medium")   return "🟠";
    if(m==="low")      return "🟡";
    if(m==="info")     return "🔵";
    return "⚪";
  }

  function setBadges(a){
    var risk = a && (a.risk || a.risk_level);
    txt(els.badgeScore,   "score: "   + (a && a.score!=null ? String(a.score) : "—"));
    txt(els.badgeRisk,    "risk: "    + (risk ? String(risk) : "—"));
    txt(els.badgeStatus,  "status: "  + (a && a.status ? String(a.status) : "—"));
    // severity may map from risk (backend compat layer usually provides it)
    var sev = a && (a.severity || (risk==="critical"?"high":risk));
    txt(els.badgeSev,     "severity: "+ (sev ? String(sev) : "—"));
  }

  function clearResults(){
    txt(els.resClauseType, "—");
    txt(els.resFindingsCount, "—");
    if (els.findingsList) els.findingsList.innerHTML = "";
    if (els.recsList) els.recsList.innerHTML = "";
    if (els.rawJson){ els.rawJson.textContent = ""; els.rawJson.style.display = "none"; }
  }

  function renderAnalysis(analysis){
    if (!analysis){ clearResults(); return; }
    setBadges(analysis);
    txt(els.resClauseType, analysis.clause_type || "—");

    var findings = [];
    if (Array.isArray(analysis.findings)) findings = analysis.findings;
    var recs = [];
    if (Array.isArray(analysis.recommendations)) recs = analysis.recommendations;

    // sort by risk→severity→span.start
    findings.sort(function(a,b){
      var ra = _riskOrd(a && (a.risk || a.risk_level));
      var rb = _riskOrd(b && (b.risk || b.risk_level));
      if (rb!==ra) return rb-ra;
      var sa = String(a && a.severity || "");
      var sb = String(b && b.severity || "");
      if (sa!==sb) return (sa>sb?-1:1);
      var pa = (a && a.span && typeof a.span.start==="number") ? a.span.start : 1e9;
      var pb = (b && b.span && typeof b.span.start==="number") ? b.span.start : 1e9;
      return pa - pb;
    });

    txt(els.resFindingsCount, String(findings.length));

    if (els.findingsList){
      els.findingsList.innerHTML = "";
      if (!findings.length){
        var li = document.createElement("li"); li.textContent = "No findings returned.";
        els.findingsList.appendChild(li);
      } else {
        findings.forEach(function(f){
          var li = document.createElement("li");
          var sev = emojiForSeverity(f && (f.severity || f.risk || f.risk_level));
          var code = f && f.code ? ("["+f.code+"] ") : "";
          var msg  = f && f.message ? f.message : "—";
          var ev   = f && f.evidence ? (" — evidence: “"+f.evidence+"”") : "";
          var lb   = (f && f.legal_basis && f.legal_basis.length) ? (" — legal: "+f.legal_basis.join("; ")) : "";
          li.textContent = sev + " " + code + msg + ev + lb;
          els.findingsList.appendChild(li);
        });
      }
    }

    if (els.recsList){
      els.recsList.innerHTML = "";
      if (!recs.length){
        var li2 = document.createElement("li"); li2.textContent = "No recommendations.";
        els.recsList.appendChild(li2);
      } else {
        recs.forEach(function(r){
          var li = document.createElement("li"); li.textContent = String(r);
          els.recsList.appendChild(li);
        });
      }
    }

    if (els.rawJson){
      try{ els.rawJson.textContent = JSON.stringify(analysis, null, 2); } catch(_){ els.rawJson.textContent = "Unable to stringify analysis."; }
    }
  }

  function fillClauseSelect(envelope){
    var clauses = (envelope && envelope.clauses) || [];
    els.sugSelect.innerHTML = "";
    clauses.forEach(function(c){
      var opt = document.createElement("option");
      opt.value = c && c.id ? c.id : "";
      var ttl = (c && (c.title || c.type)) || "clause";
      opt.textContent = (c && c.id ? c.id : "—") + " · " + ttl;
      els.sugSelect.appendChild(opt);
    });
  }

  function enableDraftApply(on){
    en(els.btnPreview, on);
    en(els.btnApply, on);
    en(els.btnAcceptAll, on);
    en(els.btnRejectAll, on);
  }

  // ================== Feature flows ==================
  async function doHealth(){
    var v = backend(); if(!v){ status("Enter backend URL first"); return; }
    txt(els.connBadge, "Conn: …");
    try{
      var r = await httpGet(v + "/health", 8000);
      txt(els.connBadge, "Conn: " + r.status);
      status(r.ok ? "Backend connected ("+r.status+")" : ("HTTP "+r.status));
    }catch(e){
      txt(els.connBadge, "Conn: 0");
      status("❌ Health failed: " + (e && e.message ? e.message : e));
    }
  }

  async function doAnalyze(useWhole){
    var text = useWhole ? await readWholeDoc() : (val(els.clause)||"");
    if (!text || !text.trim()){ status("⚠️ No text to analyze."); return; }
    status("Analyzing…");
    clearResults();
    try{
      var r = await apiAnalyze(text, null);
      if (!r.ok){ status("Analyze HTTP "+r.status+" — "+(r.text||"")); return; }
      var payload = r.json || {};
      var env = payload.data || payload; // envelope-aware
      CAI_STORE.analysis.analysis = env.analysis || env; // tolerate legacy
      CAI_STORE.analysis.results  = env.results  || null;
      CAI_STORE.analysis.clauses  = Array.isArray(env.clauses) ? env.clauses : [];
      CAI_STORE.analysis.document = env.document || null;

      fillClauseSelect(env);
      renderAnalysis(CAI_STORE.analysis.analysis);
      status("Analyze OK • cid="+(CAI_STORE.status.cid||"—")+" cache="+(CAI_STORE.status.xcache||"—"));
    }catch(e){ status("❌ Analyze error: " + (e && e.message ? e.message : e)); }
  }

  async function doDraft(){
    var analysis = CAI_STORE.analysis.analysis;
    var text = val(els.clause) || "";
    if (!analysis && !text.trim()){ status("⚠️ Nothing to draft. Paste text or run Analyze."); return; }
    status("Drafting…");
    try{
      var input = analysis ? { analysis: analysis, mode:"friendly" } : { text:text, mode:"friendly" };
      var r = await apiDraft(input);
      if (!r.ok){ status("Draft HTTP "+r.status+" — "+(r.text||"")); return; }
      var payload = r.json||{};
      var env = payload.data || payload;
      var draft = env.draft_text || env.draft || "";
      setVal(els.draft, draft);
      enableDraftApply(!!draft);
      status(draft ? "Draft OK" : "Draft empty");
    }catch(e){ status("❌ Draft error: " + (e && e.message ? e.message : e)); }
  }

  async function doSuggest(){
    if (!CAI_STORE.analysis || !CAI_STORE.analysis.clauses || !CAI_STORE.analysis.clauses.length){
      status("⚠️ Run Analyze (doc) first");
      return;
    }
    var clauseId = val(els.sugSelect) || "";
    var mode = val(els.sugMode) || "friendly";
    var full = await readWholeDoc();
    status("Suggesting edits…");
    try{
      var r = await apiSuggestEdits(full, clauseId, mode, 3);
      if (!r.ok){ status("Suggest HTTP "+r.status+" — "+(r.text||"")); return; }
      var payload = r.json||{};
      var list = (payload.data && payload.data.suggestions) || payload.suggestions || [];
      renderSuggestions(list);
      status("Suggest OK (" + list.length + ")");
    }catch(e){ status("❌ Suggest error: " + (e && e.message ? e.message : e)); }
  }

  function renderSuggestions(list){
    els.sugList.innerHTML = "";
    if (!Array.isArray(list) || !list.length){
      var div = document.createElement("div"); div.className="muted"; div.textContent="No suggestions.";
      els.sugList.appendChild(div); return;
    }
    list.forEach(function(sug, i){
      var card = document.createElement("div"); card.className="sug-card";
      var head = document.createElement("div"); head.className="sug-head";
      var title = document.createElement("div"); title.className="sug-title";
      title.textContent = sug.title || (sug.clause_type ? (sug.clause_type + " suggestion") : ("Suggestion " + (i+1)));
      var meta = document.createElement("div"); meta.className="sug-meta";
      meta.textContent = (sug.risk ? ("risk:" + sug.risk) : "");
      head.appendChild(title); head.appendChild(meta);

      var pre = document.createElement("pre");
      pre.textContent = sug.draft || sug.proposed_text || "";

      var row = document.createElement("div");
      var btn = document.createElement("button"); btn.className="btn"; btn.textContent="Apply → Draft";
      btn.addEventListener("click", function(){
        setVal(els.draft, pre.textContent);
        enableDraftApply(!!pre.textContent);
        status("Suggestion copied to draft. Review, then Apply.");
      });
      row.appendChild(btn);

      card.appendChild(head);
      card.appendChild(pre);
      card.appendChild(row);
      els.sugList.appendChild(card);
    });
  }

  async function doAnnotate(){
    var analysis = CAI_STORE.analysis.analysis || null;
    if (!analysis){ status("⚠️ Analyze first."); return; }
    var thr = (val(els.riskThreshold) || CAI_STORE.settings.riskThreshold || "high").toLowerCase();
    var thrOrd = _riskOrd(thr);

    var full = await readWholeDoc();
    var items = Array.isArray(analysis.findings) ? analysis.findings : [];
    var risky = items.filter(function(f){ return _riskOrd(f && (f.risk || f.risk_level)) >= thrOrd; });
    if (!window.Word || !Word.run){ status("⚠️ Word API not available"); return; }

    try{
      await Word.run(function(ctx){
        // Clear old comments (best-effort)
        try{
          var comments = ctx.document.body.comments; comments.load("items");
        }catch(_){}
        return ctx.sync().then(function(){
          try{
            if (comments && comments.items && comments.items.length){
              comments.items.forEach(function(c){ try{ c.delete(); }catch(_){} });
            }
          }catch(_){}
          return ctx.sync();
        });
      });

      // Add comments
      for (var i=0;i<risky.length;i++){
        var f = risky[i];
        var msg = (f && f.code ? ("[" + f.code + "] ") : "") + (f && f.message ? f.message : "Issue") + (f && (f.risk || f.risk_level) ? (" — risk:" + (f.risk||f.risk_level)) : "");
        await addCommentAtSpan(full, f && f.span, msg);
      }
      status("Annotated ("+risky.length+")");
    }catch(e){ status("❌ Annotate failed: " + (e && e.message ? e.message : e)); }
  }

  function addCommentAtSpan(fullText, span, message){
    if (!window.Word || !Word.run) return Promise.resolve();
    var snippet = "";
    try{
      if (fullText && typeof fullText==="string" && span && typeof span.start==="number" && typeof span.length==="number"){
        snippet = fullText.substr(span.start, Math.min(span.length, 64));
      }
    }catch(_){}
    return Word.run(function(ctx){
      var body = ctx.document.body;
      var found = snippet ? body.search(snippet, { matchCase:false, matchWholeWord:false, ignorePunct:true, ignoreSpace:true }) : null;
      if (found) found.load("items");
      return ctx.sync().then(function(){
        var rng = null;
        if (found && found.items && found.items.length) rng = found.items[0];
        else rng = ctx.document.getSelection();
        try{ rng.insertComment(String(message||"Contract AI")); }catch(_){}
        return ctx.sync();
      });
    });
  }

  async function doQARecheck(){
    var full = await readWholeDoc();
    status("QA recheck…");
    try{
      var r = await apiQARecheck(full, []);
      if (!r.ok){ status("QA HTTP "+r.status+" — "+(r.text||"")); return; }
      var payload = r.json || {};
      var d = (payload.data && payload.data.deltas) || payload.deltas || payload.data || payload || {};
      var badge = "Δ: s" + (d.score_delta>=0?"+":"") + (d.score_delta||0) +
                  " r" + (d.risk_delta>=0?"+":"") + (d.risk_delta||0) +
                  " " + (d.status_from||"") + "→" + (d.status_to||"");
      txt(els.qaDeltaBadge, badge);

      var res = (payload.data && payload.data.residual_risks) || payload.residual_risks || [];
      els.qaResidualList.innerHTML = "";
      if (res.length){
        els.qaResiduals.style.display = "block";
        res.forEach(function(it){
          var li = document.createElement("li");
          li.textContent = (it.code?("["+it.code+"] "):"") + (it.message||"risk");
          els.qaResidualList.appendChild(li);
        });
      } else {
        els.qaResiduals.style.display = "none";
      }
      status("QA OK");
    }catch(e){ status("❌ QA error: " + (e && e.message ? e.message : e)); }
  }

  // ================== Wire UI ==================
  function wire(){
    els.backend       = $("backendInput");
    els.btnSave       = $("btnSave");
    els.btnTest       = $("btnTest");
    els.connBadge     = $("connBadge");
    els.officeBadge   = $("officeBadge");
    els.cidBadge      = $("cidBadge");
    els.xcacheBadge   = $("xcacheBadge");
    els.latencyBadge  = $("latencyBadge");
    els.schemaBadge   = $("schemaBadge");
    els.doctorToggle  = $("doctorToggle");
    els.doctorPanel   = $("doctorPanel");
    els.doctorReqList = $("doctorReqList");
    els.doctorCid     = $("doctorCid");
    els.doctorLatency = $("doctorLatency");
    els.doctorPayload = $("doctorPayload");

    els.clause        = $("originalClause");
    els.analyzeBtn    = $("analyzeBtn");
    els.draftBtn      = $("draftBtn");
    els.copyBtn       = $("copyResultBtn");
    els.useSel        = $("useSelection");
    els.useDoc        = $("useWholeDoc");
    els.btnInsert     = $("btnInsertIntoWord");

    els.btnAnalyzeDoc = $("btnAnalyzeDoc");
    els.btnAnnotate   = $("btnAnnotate");
    els.btnQARecheck  = $("btnQARecheck");
    els.btnClearAnnots= $("btnClearAnnots");
    els.qaDeltaBadge  = $("qaDeltaBadge");
    els.qaResiduals   = $("qaResiduals");
    els.qaResidualList= $("qaResidualList");
    els.riskThreshold = $("riskThreshold");

    els.badgeScore    = $("scoreBadge");
    els.badgeRisk     = $("riskBadge");
    els.badgeStatus   = $("statusBadge");
    els.badgeSev      = $("severityBadge");

    els.resClauseType   = $("resClauseType");
    els.resFindingsCount= $("resFindingsCount");
    els.findingsList    = $("findingsList");
    els.recsList        = $("recsList");
    els.toggleRaw       = $("toggleRaw");
    els.rawJson         = $("rawJson");

    els.sugSelect     = $("cai-clause-select");
    els.sugMode       = $("cai-mode");
    els.sugBtn        = $("cai-btn-suggest");
    els.sugList       = $("cai-suggest-list");

    els.draft         = $("draftBox");
    els.btnPreview    = $("btnPreview");
    els.btnApply      = $("btnApply");
    els.btnAcceptAll  = $("acceptAllBtn");
    els.btnRejectAll  = $("rejectAllBtn");

    els.console       = $("console");

    // events
    if (els.btnSave) els.btnSave.addEventListener("click", function(){
      var v = backend(); if(!v){ status("⚠️ Enter backend URL first"); return;}
      writeLS(LS_KEY, v); status("Saved: " + v);
    });

    if (els.btnTest) els.btnTest.addEventListener("click", function(){ doHealth(); });

    if (els.analyzeBtn) els.analyzeBtn.addEventListener("click", function(){ doAnalyze(false); });
    if (els.btnAnalyzeDoc) els.btnAnalyzeDoc.addEventListener("click", function(){ doAnalyze(true); });

    if (els.useSel) els.useSel.addEventListener("click", async function(){ var t=await readSelection(); setVal(els.clause,t); status("Selection copied."); });
    if (els.useDoc) els.useDoc.addEventListener("click", async function(){ var t=await readWholeDoc(); setVal(els.clause,t); status("Whole document copied."); });

    if (els.draftBtn) els.draftBtn.addEventListener("click", function(){ doDraft(); });
    if (els.copyBtn) els.copyBtn.addEventListener("click", function(){
      try{ navigator.clipboard && navigator.clipboard.writeText(val(els.draft)||""); status("Draft copied to clipboard"); }catch(_){}
    });

    if (els.sugBtn) els.sugBtn.addEventListener("click", function(){ doSuggest(); });

    if (els.toggleRaw) els.toggleRaw.addEventListener("click", function(){
      if (!els.rawJson) return;
      var s = window.getComputedStyle(els.rawJson).display;
      els.rawJson.style.display = (s==="none" ? "block" : "none");
    });

    if (els.btnInsert) els.btnInsert.addEventListener("click", async function(){
      try{
        var t = val(els.draft).trim();
        if (!t){ status("Draft empty"); return; }
        await insertPlain(t);
        status("Inserted into Word (plain)");
      }catch(e){ status("❌ Insert failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnApply) els.btnApply.addEventListener("click", async function(){
      try{
        var t = val(els.draft).trim(); if(!t){ status("Draft empty"); return; }
        await applyTracked(t, "Contract AI — applied draft");
        enableDraftApply(true);
        status("Applied as tracked changes.");

        // Learning log (no raw text)
        try{
          var now = new Date().toISOString();
          var norm = normalizeText(val(els.clause)||"");
          var docHash = await sha256Hex(norm + "|local");
          var ev = {
            schema_ver: "1",
            event_id: "ev-"+Date.now(),
            ts: now,
            action: "applied",
            user: "local",
            doc_id: docHash,
            clause_id: val(els.sugSelect)||null,
            mode: val(els.sugMode)||"friendly",
            ui_latency_ms: CAI_STORE.status.latencyMs || null,
            client: { cid: CAI_STORE.status.cid || "", panel_build: BUILD }
          };
          apiLearningLog([ev]).catch(function(){});
        }catch(_){}
      }catch(e){ status("❌ Apply failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnPreview) els.btnPreview.addEventListener("click", function(){
      var o = val(els.clause)||"", d = val(els.draft)||"";
      if (!o || !d){ status("Provide original and draft for diff."); return; }
      status("Diff ready (console). orig.len="+o.length+" draft.len="+d.length);
    });

    if (els.btnAcceptAll) els.btnAcceptAll.addEventListener("click", async function(){
      try{ await acceptAll(); status("Accepted all changes."); }catch(e){ status("❌ Accept failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnRejectAll) els.btnRejectAll.addEventListener("click", async function(){
      try{ await rejectAll(); status("Rejected all changes."); }catch(e){ status("❌ Reject failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnAnnotate) els.btnAnnotate.addEventListener("click", function(){ doAnnotate(); });
    if (els.btnClearAnnots) els.btnClearAnnots.addEventListener("click", async function(){
      if (!window.Word || !Word.run){ status("⚠️ Word API not available"); return; }
      try{
        await Word.run(function(ctx){
          var comments = ctx.document.body.comments; comments.load("items");
          return ctx.sync().then(function(){
            if (comments && comments.items){
              comments.items.forEach(function(c){ try{ c.delete(); }catch(_){} });
            }
            return ctx.sync();
          });
        });
        status("Annotations cleared.");
      }catch(e){ status("❌ Clear annotations failed: " + (e && e.message ? e.message : e)); }
    });

    if (els.btnQARecheck) els.btnQARecheck.addEventListener("click", function(){ doQARecheck(); });

    if (els.doctorToggle) els.doctorToggle.addEventListener("click", function(){
      var vis = els.doctorPanel && (els.doctorPanel.style.display!=="none");
      els.doctorPanel.style.display = vis ? "none" : "block";
      els.doctorToggle.textContent = vis ? "Doctor ▸" : "Doctor ▾";
    });
  }

  // ================== Boot ==================
  function boot(){
    wire();
    ensureOfficeBadge();
    // init backend box
    try {
      var v = readLS(LS_KEY) || "http://127.0.0.1:9000";
      if ($("backendInput")) $("backendInput").value = v;
    } catch(_){}
    status("🟢 Bundle ready ("+BUILD+"). Set backend and click Test.");
  }

  document.addEventListener("DOMContentLoaded", boot, { once:true });

  // ================== Global error diag ==================
  window.addEventListener("error", function(e){
    try { var n = $("console"); if (n) { n.appendChild(document.createTextNode("[JS ERROR] " + (e.message || e.error || e) + "\n")); n.scrollTop = n.scrollHeight; } } catch(_){}
  });
  window.addEventListener("unhandledrejection", function(e){
    try { var n = $("console"); if (n) { n.appendChild(document.createTextNode("[PROMISE REJECTION] " + (e.reason && (e.reason.message || e.reason)) + "\n")); n.scrollTop = n.scrollHeight; } } catch(_){}
  });

})();
