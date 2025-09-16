import fs from 'fs';

type Op = { op:'replace'|'insertBefore'|'insertAfter'|'comment',
            anchor:{text:string,fingerprint?:string,offsetHint?:number},
            before?:string, after?:string, text?:string };

function applyOpsToPlainText(text: string, ops: Op[]) {
  const applied: any[] = [], failed: any[] = [], comments: any[] = [];
  let current = text;

  for (const op of ops) {
    const idx = current.indexOf(op.anchor.text);
    if (idx < 0) { failed.push({op, reason:'anchor not found'}); continue; }

    if (op.op === 'replace' && op.before) {
      const seg = current.substr(idx, op.before.length);
      if (seg !== op.before) { failed.push({op, reason:'before mismatch'}); continue; }
      current = current.slice(0, idx) + (op.after ?? '') + current.slice(idx + op.before.length);
      applied.push(op); continue;
    }
    if (op.op === 'insertBefore') {
      current = current.slice(0, idx) + (op.text ?? '') + current.slice(idx);
      applied.push(op); continue;
    }
    if (op.op === 'insertAfter') {
      const afterIdx = idx + op.anchor.text.length;
      current = current.slice(0, afterIdx) + (op.text ?? '') + current.slice(afterIdx);
      applied.push(op); continue;
    }
    if (op.op === 'comment') {
      comments.push(op);
      applied.push({ ...op, note: 'comment (no-op in plain text)' });
      continue;
    }
  }
  return { text: current, applied, failed, comments };
}

(async () => {
  const stamp = Date.now();
  try {
    const original = fs.readFileSync('samples/nda_en.txt', 'utf8');
    const resA = await fetch('https://127.0.0.1:9443/api/analyze', {
      method:'POST', headers: {'Content-Type':'application/json','X-Api-Key':'local-test-key-123','X-Schema-Version':'1.4'},
      body: JSON.stringify({ mode:'live', doc:{ text:original, locale:'en-GB', docType:'NDA' } })
    });
    const A: any = await resA.json();
    const ids = A.findings.map((f:any)=>f.id);

    const resD = await fetch('https://127.0.0.1:9443/api/draft', {
      method:'POST', headers: {'Content-Type':'application/json','X-Api-Key':'local-test-key-123','X-Schema-Version':'1.4'},
      body: JSON.stringify({ mode:'friendly', docFingerprint:A.docFingerprint, findingIds: ids })
    });
    const D: any = await resD.json();

    let text = original, appliedAll:any[]=[] , failedAll:any[]=[], commentsAll:any[]=[];
    for (const d of D.drafts) {
      const { text: t, applied, failed, comments } = applyOpsToPlainText(text, d.ops);
      text = t; appliedAll.push(...applied); failedAll.push(...failed); commentsAll.push(...comments);
    }

    fs.writeFileSync(`sim_report_${stamp}.json`, JSON.stringify({
      totalOps: appliedAll.length + failedAll.length,
      applied: appliedAll.length,
      failed: failedAll.length,
      failedOps: failedAll,
      comments: commentsAll
    }, null, 2));

    const reportLines = ['# Disagreements', ''];
    if (failedAll.length === 0) {
      reportLines.push('No failed operations.');
    } else {
      for (const f of failedAll) {
        reportLines.push(`- ${f.reason}: ${JSON.stringify(f.op)}`);
      }
    }
    fs.writeFileSync(`disagreements_${stamp}.md`, reportLines.join('\n'));
    fs.writeFileSync(`patched_${stamp}.txt`, text, 'utf8');
  } catch (err:any) {
    fs.writeFileSync(`sim_report_${stamp}.json`, JSON.stringify({ error: err?.message || String(err) }, null, 2));
    console.error('Simulation failed', err);
  }
})();
