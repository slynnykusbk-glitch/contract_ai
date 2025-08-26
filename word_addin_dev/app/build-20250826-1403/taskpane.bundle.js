(() => {
  // word_addin_dev/app/src/panel/index.ts
  var input = document.getElementById("input");
  var output = document.getElementById("output");
  async function callApi(endpoint) {
    output.textContent = "...";
    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: input.value })
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(JSON.stringify(data));
      output.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      output.textContent = err.message || String(err);
    }
  }
  document.getElementById("btnAnalyze").onclick = () => callApi("/api/analyze");
  document.getElementById("btnSummary").onclick = () => callApi("/api/summary");
  document.getElementById("btnSuggest").onclick = () => callApi("/api/suggest_edits");
  document.getElementById("btnQA").onclick = () => callApi("/api/qa-recheck");
  async function pingHealth() {
    const badge = document.getElementById("health");
    if (!badge) return;
    try {
      const r = await fetch("/health");
      badge.textContent = r.ok ? "ok" : "fail";
      badge.className = r.ok ? "ok" : "fail";
    } catch {
      badge.textContent = "fail";
      badge.className = "fail";
    }
  }
  pingHealth();
})();
