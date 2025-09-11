import json
import subprocess
import textwrap

JS = r"""
function renderAnalysisSummary(json) {
  const clauseType =
    json?.summary?.clause_type ||
    json?.meta?.clause_type ||
    json?.doc_type ||
    "—";

  const findings = Array.isArray(json?.findings) ? json.findings : [];
  const recs = Array.isArray(json?.recommendations) ? json.recommendations : [];

  let visible = findings.length;
  let hidden = 0;
  if (typeof json?.meta?.visible_count === "number") {
    visible = json.meta.visible_count;
  }
  if (typeof json?.meta?.hidden_count === "number") {
    hidden = json.meta.hidden_count;
  }

  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  setText("clauseTypeOut", String(clauseType));
  setText("visibleHiddenOut", `${visible} / ${hidden}`);

  const fCont = document.getElementById("findingsList");
  if (fCont) {
    fCont.innerHTML = "";
    for (const f of findings) {
      const li = document.createElement("li");
      const title = f?.title || f?.finding?.title || f?.rule_id || "Issue";
      const snippet = f?.snippet || f?.evidence?.text || "";
      li.textContent = snippet ? `${title}: ${snippet}` : String(title);
      fCont.appendChild(li);
    }
  }

  const rCont = document.getElementById("recsList");
  if (rCont) {
    rCont.innerHTML = "";
    for (const r of recs) {
      const li = document.createElement("li");
      li.textContent = r?.text || r?.advice || r?.message || "Recommendation";
      rCont.appendChild(li);
    }
  }

  const rb = document.getElementById("resultsBlock");
  if (rb) rb.style && rb.style.removeProperty && rb.style.removeProperty("display");
}

const vh = { textContent: '' };
const findingsList = { innerHTML: '', items: [], appendChild(li){ this.items.push(li); } };
const elements = { visibleHiddenOut: vh, findingsList };

global.document = {
  getElementById(id){ return elements[id] || null; },
  createElement(){ return { textContent: '' }; }
};

renderAnalysisSummary({
  findings: [
    { snippet: 'a', rule_id: 'l' },
    { snippet: 'b', rule_id: 'm' },
    { snippet: 'c', rule_id: 'h' }
  ],
  recommendations: [],
  meta: { visible_count: 1, hidden_count: 2 }
});

const parts = vh.textContent.split('/');
const visible = parseInt(parts[0], 10);
const hidden = parseInt(parts[1], 10);
const totalCount = findingsList.items.length;
console.log(JSON.stringify({ visible, hidden, total: totalCount }));
"""

def test_filters_visibility(tmp_path):
    result = subprocess.run([
        "node",
        "-e",
        textwrap.dedent(JS),
    ], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["visible"] + data["hidden"] == data["total"] == 3
