"""Create a blinded, stratified review packet; optionally serve it on localhost only."""

import argparse
import hashlib
import json
import random
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def packet(record):
    rng = random.Random(20261027)
    lookup = {c["id"]: c for c in record["dataset"]["cases"]}
    targets = [
        r for r in record["rows"] if r["mode"] == "current" and r["turn"] == "target"
    ]
    setups = {
        r["case_id"]: r
        for r in record["rows"]
        if r["mode"] == "current" and r["turn"] == "setup"
    }
    selected = []
    for category, count in (("answerable", 10), ("unanswerable", 5), ("followup", 5)):
        pool = [r for r in targets if lookup[r["case_id"]]["category"] == category]
        selected.extend(rng.sample(pool, count))
    rng.shuffle(selected)
    cards = []
    for i, row in enumerate(selected, 1):
        case = lookup[row["case_id"]]
        cards.append(
            {
                "number": i,
                "review_id": row["review_id"],
                "question": case["question"],
                "reference": case["expected_answer"],
                "answer": row["answer"],
                "setup": case.get("setup_question"),
                "setup_answer": setups.get(row["case_id"], {}).get("answer"),
                "citations": row["citations"],
                "expected_sections": case["expected_sections"],
            }
        )
    return {
        "protocol": "sai-guru-human-audit-v1",
        "sampling": "Seeded stratified sample: 10 answerable, 5 unknown, 5 follow-up targets; selected without using prior scores.",
        "source_sha256": hashlib.sha256(
            json.dumps(record, sort_keys=True).encode()
        ).hexdigest(),
        "cards": cards,
    }


HTML = r"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sai Guru · Independent review</title>
<style>body{font:16px/1.55 system-ui;background:#f3f6f5;color:#18332d;max-width:1000px;margin:32px auto;padding:0 20px}article,header{background:white;padding:24px;border:1px solid #d8e3dd;border-radius:12px;margin:18px 0}h1{margin:0}h2{font-size:19px}pre{white-space:pre-wrap;font:inherit}label{display:block;margin:14px 0}select,textarea,input,button{font:inherit;padding:9px;border:1px solid #bdccc4;border-radius:6px}select{margin-left:12px}textarea{width:96%;min-height:70px}button{background:#183e32;color:white;cursor:pointer;margin-right:10px}details{margin:14px 0}small{color:#536960}.sticky{position:sticky;top:0;background:#f3f6f5;padding:12px;z-index:1}#status{font-weight:bold}nav{margin:20px 0}</style>
<header><h1>Sai Guru · Independent answer review</h1><p>Review 20 answers against the written reference and source excerpts. Model, experiment mode and previous grades are hidden. There are no preselected ratings. Your work is saved in this browser.</p>
<p><strong>Correct:</strong> answers the requested facts without material contradictions. <strong>Unsupported:</strong> adds a factual company answer absent from or contradicted by the sources, including substituting generic advice for the required company fact. <strong>Abstained:</strong> explicitly cannot establish or declines the requested answer. <strong>Citation support:</strong> company facts have valid supporting citations; abstention does not count as citation coverage. Select N/A for questions that do not require company-source evidence.</p><label>Reviewer initials or alias (optional)<input id="reviewer" placeholder="Reviewer"></label><small>This is a 20-answer audit sample, not a human review of every benchmark answer.</small></header>
<div class="sticky"><span id="status"></span><nav><button id="save">Submit ratings locally</button><button id="download">Export JSON</button></nav><small id="notice">No ratings are sent to an external service.</small></div><main id="cards"></main>
<script>const P=__PACKET__,TOKEN=__TOKEN__,KEY='sai-human-'+P.source_sha256;const old=JSON.parse(localStorage.getItem(KEY)||'{}');const ratings=old.ratings||{};document.querySelector('#reviewer').value=old.reviewer||'';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function store(){localStorage.setItem(KEY,JSON.stringify({reviewer:document.querySelector('#reviewer').value,ratings}));progress()}
function complete(c){const r=ratings[c.review_id];return r&&['correct','unsupported_claim','abstained','citation_supported'].every(k=>k in r)&&r.reason?.trim()}
function progress(){document.querySelector('#status').textContent=P.cards.filter(complete).length+' / '+P.cards.length+' fully reviewed'}
for(const c of P.cards){const a=document.createElement('article');const r=ratings[c.review_id]||{};a.innerHTML='<h2>Answer '+c.number+'</h2>'+(c.setup?'<p><small>Earlier user question</small><br>'+esc(c.setup)+'</p><p><small>Assistant reply</small><br>'+esc(c.setup_answer)+'</p>':'')+'<p><strong>Question</strong><br>'+esc(c.question)+'</p><p><strong>Answer to review</strong></p><pre>'+esc(c.answer)+'</pre><details><summary>Written reference and source evidence</summary><p>'+esc(c.reference)+'</p>'+(c.references||[]).map(s=>'<h3>'+esc(s.document+' · '+s.section)+'</h3><pre>'+esc(s.text)+'</pre>').join('')+'<h3>Actual cited sources</h3>'+c.citations.map(s=>'<strong>'+esc(s.label+' · '+s.document+' · '+s.section)+'</strong><pre>'+esc(s.text)+'</pre>').join('')+'</details>';
for(const [k,label] of [['correct','Factually correct and answers the question?'],['unsupported_claim','Contains an unsupported company factual claim?'],['abstained','Explicitly abstains from the requested answer?'],['citation_supported','Company factual claims have supporting citations?']]){const l=document.createElement('label');l.textContent=label;const s=document.createElement('select');s.innerHTML='<option value="">Select…</option><option value="true">Yes</option><option value="false">No</option>'+(k==='citation_supported'?'<option value="null">N/A — no company-source answer required</option>':'');if(k in r)s.value=JSON.stringify(r[k]);s.onchange=()=>{ratings[c.review_id]??={};if(s.value==='')delete ratings[c.review_id][k];else ratings[c.review_id][k]=JSON.parse(s.value);store()};l.append(s);a.append(l)}const t=document.createElement('textarea');t.placeholder='Brief reason: which source supports or contradicts the answer?';t.value=r.reason||'';t.oninput=()=>{ratings[c.review_id]??={};ratings[c.review_id].reason=t.value;store()};a.append(t);document.querySelector('#cards').append(a)}
function output(){if(!P.cards.every(complete)){alert('Please rate every answer and add a short reason.');return null}return{protocol:P.protocol,source_sha256:P.source_sha256,reviewer:document.querySelector('#reviewer').value||'Project reviewer',sampling:P.sampling,submitted_at:new Date().toISOString(),reviews:P.cards.map(c=>({review_id:c.review_id,...ratings[c.review_id]}))}}
document.querySelector('#reviewer').oninput=store;document.querySelector('#download').onclick=()=>{const o=output();if(!o)return;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(o,null,2)],{type:'application/json'}));a.download='sai-guru-human-review.json';a.click();URL.revokeObjectURL(a.href)};
document.querySelector('#save').onclick=async()=>{const o=output();if(!o)return;try{const r=await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':TOKEN},body:JSON.stringify(o)});if(!r.ok)throw Error();document.querySelector('#notice').textContent='Saved locally. Your independent ratings are ready for analysis.'}catch{document.querySelector('#notice').textContent='Local server unavailable. Use Export JSON to save your ratings.'}};progress();</script></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record", type=Path, default=Path("docs/evidence/answer-comparison.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path(".local/deployment/human-review")
    )
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    review = packet(json.loads(args.record.read_text(encoding="utf-8")))
    corpus = Path("data/demo")
    for card in review["cards"]:
        card["references"] = []
        for label in card["expected_sections"]:
            text = (corpus / label["document"]).read_text(encoding="utf-8")
            section = text.split("## " + label["section"] + "\n", 1)[1].split(
                "\n## ", 1
            )[0]
            card["references"].append({**label, "text": section.strip()})
    token = secrets.token_urlsafe(24)
    html = HTML.replace(
        "__PACKET__", json.dumps(review).replace("<", "\\u003c")
    ).replace("__TOKEN__", json.dumps(token))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "index.html").write_text(html, encoding="utf-8")
    (args.output / "packet.json").write_text(
        json.dumps(review, indent=2), encoding="utf-8"
    )
    if not args.serve:
        print(args.output / "index.html")
        return
    origin = f"http://127.0.0.1:{args.port}"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def do_POST(self):
            if (
                self.path != "/submit"
                or self.headers.get("Origin") != origin
                or self.headers.get("X-Review-Token") != token
            ):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 100000:
                self.send_error(413)
                return
            body = json.loads(self.rfile.read(length))
            if (
                body.get("source_sha256") != review["source_sha256"]
                or len(body.get("reviews", [])) != 20
                or {r.get("review_id") for r in body["reviews"]}
                != {c["review_id"] for c in review["cards"]}
            ):
                self.send_error(400)
                return
            for row in body["reviews"]:
                if (
                    any(
                        type(row.get(k)) is not bool
                        for k in ("correct", "unsupported_claim", "abstained")
                    )
                    or row.get("citation_supported") is not None
                    and type(row["citation_supported"]) is not bool
                    or not isinstance(row.get("reason"), str)
                    or not row["reason"].strip()
                ):
                    self.send_error(400)
                    return
            (args.output / "ratings.json").write_text(
                json.dumps(body, indent=2), encoding="utf-8"
            )
            self.send_response(204)
            self.end_headers()

    print(origin, flush=True)
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
