from __future__ import annotations
import csv
import fnmatch
import html
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
from .util import atomic_json, file_digest


def suppression_for(f: dict, rules: list[dict]) -> dict | None:
    for rule in rules:
        if date.fromisoformat(str(rule["expires"]))<date.today():continue
        if not fnmatch.fnmatchcase(f["rule"],rule["rule"]):continue
        if not fnmatch.fnmatchcase(f["stage"],rule.get("route","*")):continue
        pattern=rule.get("selector","*")
        if not any(s==pattern or fnmatch.fnmatchcase(s,pattern) for s in f["selectors"]):continue
        return {k:str(v) for k,v in rule.items()}
    return None


def aggregate(data: dict, cfg: dict) -> list[dict]:
    groups=defaultdict(list)
    for o in data["occurrences"]:groups[o["fingerprint"]].append(o)
    result=[]
    for key,obs in sorted(groups.items()):
        exemplar=obs[0];percell=defaultdict(set)
        for o in obs:
            if o["stable"] and not o["candidate"]:percell[o["cell"]].add(o["repeat"])
        reproduced=sorted(c for c,rs in percell.items() if len(rs)>=2)
        status="confirmed" if reproduced else "candidate"
        f={"id":key,**{k:exemplar[k] for k in ("rule","title","message","selectors","severity","stage")},
           "confidence":max(o["confidence"] for o in obs),"status":status,"reproduced_cells":reproduced,
           "occurrences":[{k:o[k] for k in ("cell","repeat","stage","evidence","rects","details","stable")} for o in obs]}
        suppression=suppression_for(f,cfg["suppressions"])
        if suppression:f["status"]="suppressed";f["suppression"]=suppression
        result.append(f)
    order={"confirmed":0,"candidate":1,"suppressed":2}
    return sorted(result,key=lambda f:(order[f["status"]],f["rule"],f["id"]))


def finalize(root: Path, data: dict, cfg: dict) -> None:
    data["findings"]=aggregate(data,cfg)
    from .gate import plan_checks, evaluate
    data.setdefault("cell_plan",[c["id"] for c in data["cells"]])
    data.setdefault("check_plan",plan_checks(cfg,cfg["journeys"],data["cell_plan"]))
    for cell in data["cells"]:
        ss=[s for s in data["snapshots"] if s["meta"]["browser"]==cell["browser"] and s["meta"]["device"]==cell["device"]]
        gaps=[g for s in ss for g in s["gaps"]]
        blocking={"required_detector_missing","required_detector_failed","capture_limit","detector_limit",
                  "unstable_layout","alignment_contract","fonts_pending","baseline_incompatible","required_performance_missing"}
        skipped=any(c["status"] in ("not_run","blocked") for c in data["checks"] if c["cell"]==cell["id"])
        cell["complete"]=not cell["errors"] and cell["observed_scenes"]==cell["expected_scenes"] and not skipped and not any(g["kind"] in blocking for g in gaps)
        cell["scope_gaps"]=gaps
        relevant=[f for f in data["findings"] if any(o["cell"]==cell["id"] for o in f["occurrences"])]
        cell["confirmed"]=sum(f["status"]=="confirmed" and cell["id"] in f["reproduced_cells"] for f in relevant)
        cell["candidates"]=sum(f["status"]!="suppressed" and cell["id"] not in f["reproduced_cells"] for f in relevant)
        cell["failed_checks"]=sum(c["status"]=="failed" for c in data["checks"] if c["cell"]==cell["id"])
        cell["performance_failures"]=sum(s.get("performance",{}).get("status")=="failed" for s in ss)
        cell["status"]="incomplete" if not cell["complete"] else "failed" if cell["confirmed"] or cell["failed_checks"] or cell["performance_failures"] else "observed"
    data["cells"].sort(key=lambda c:c["id"])
    data["coverage"]={"expected_cells":len(data["cells"]),"observed_cells":sum(c["observed_scenes"]>0 for c in data["cells"]),
                      "incomplete_cells":sum(not c["complete"] for c in data["cells"]),
                      "state":"incomplete" if any(not c["complete"] for c in data["cells"]) or data["run_gaps"] else "complete",
                      "unit":"browser-device","scope":"configured scenes and bounded rendered observations only"}
    data["summary"]={k:sum(f["status"]==k for f in data["findings"]) for k in ("confirmed","candidate","suppressed")}
    data["gate"]=evaluate(data)
    data["limitations"]=[
        "Confirmed means a repeatable detector/explicit UI-contract violation, not proof of product intent or a guarantee of all defects.",
        "GUI diagnosis uses rendered observations. Opt-in CDP counters and downloaded-file contracts are separately labelled; no source code or backend state was used.",
        "Device profiles are emulations, not physical iOS/Android devices. Firefox mobile uses viewport and touch without is_mobile.",
        "WebKit on Linux is not the Safari browser. Chrome/Edge/Brave share the Chromium engine.",
        "Only open shadow DOM is inspected. Frame interiors, closed shadow DOM, canvas and video need additional visual/manual coverage.",
        "Masking is selective, not a guarantee of anonymization. Use synthetic test accounts and inspect artifacts before sharing.",
        "UI assertions and filename/byte/prefix/hash checks do not prove backend persistence, semantic invoice correctness or business intent. API contracts, when run, are a separate report.",
        "Reports use a locally versioned manifest. wellmanifest/docs could not be verified publicly (404 at review time)."
    ]
    # Occurrences are already retained per finding; drop the redundant full collector finding projection.
    del data["occurrences"]
    atomic_json(root/"report.json",data)
    from .proposals import build
    proposals=build(data,root);atomic_json(root/"proposals.json",proposals)
    markdown(root,data)
    html_report(root,data)
    matrix_csv(root,data)
    junit(root,data)
    inventory=[]
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in ("manifest.json",) and "logs" not in p.relative_to(root).parts:
            inventory.append({"path":p.relative_to(root).as_posix(),"sha256":file_digest(p),"bytes":p.stat().st_size})
    atomic_json(root/"manifest.json",{"schema":"testwins.report-manifest/v1","authority":"none",
        "report":"report.json","report_sha256":file_digest(root/"report.json"),"coverage":data["coverage"],
        "assessment":data["gate"]["status"],"gate":data["gate"],
        "wellmanifest_logs":{"event_schema":"wellmanifest.logs/event/v1","upstream_contract":"0.5.0",
                              "upstream_conformance":"not_executed_here; run standards command with trusted upstream checkout"},
        "wellmanifest_docs":{"status":"unverified","reason":"Public repository returned 404; no conformity claim"},
        "redaction":{"state":"selective_masks_only","requires_review_before_publication":True},"evidence":inventory})


def representative(f: dict,d: dict) -> dict:
    """Prefer evidence where the affected geometry is actually visible, not an off-screen layout measurement."""
    sizes={c["id"]:None for c in d["cells"]}
    for s in d["snapshots"]:
        sizes[s["meta"]["browser"]+"-"+s["meta"]["device"]]=s["meta"]["viewport_profile"]
    def score(o):
        v=sizes.get(o["cell"])
        if not v:return 0
        def fraction(r):
            overlap=max(0,min(v["width"],r["x"]+r["width"])-max(0,r["x"]))*max(0,min(v["height"],r["y"]+r["height"])-max(0,r["y"]))
            return overlap/max(1,r["width"]*r["height"])
        return sum(fraction(r) for r in o["rects"])/max(1,len(o["rects"]))
    return max(f["occurrences"],key=score)


def markdown(root: Path,d: dict) -> None:
    lines=[f"# Testwins — {d['project']}","",f"Run: `{d['run_id']}`", "",
           f"Powtarzalne naruszenia: **{d['summary']['confirmed']}**; kandydaci: **{d['summary']['candidate']}**; "
           f"niepełne komórki: **{d['coverage']['incomplete_cells']}/{d['coverage']['expected_cells']}**.","",
           "## Macierz","","| Przeglądarka | Urządzenie | Transport | Stan | Naruszenia | Kandydaci |",
           "|---|---|---|---|---:|---:|"]
    for c in d["cells"]:lines.append(f"| {c['browser']} | {c['device']} | {c['transport']} | {c['status']} | {c['confirmed']} | {c['candidates']} |")
    lines += ["", "## Bramka obowiązkowych kontraktów", "", f"Wynik: **{d['gate']['status']}**, kod wyjścia: {d['gate']['exit_code']}.",
              f"Wymagane kroki: {d['gate']['expected_checks']}; zaliczone: {d['gate']['passed_checks']}; nieudane: {d['gate']['failed_checks']}; zablokowane/niewykonane: {d['gate']['blocked_checks']}.", ""]
    for c in d['checks']:
        lines.append(f"- {c['cell']} / {c['scene']} / {c['step']} / repeat {c['repeat']}: **{c['status']}**")
    for f in d["findings"]:
        lines += ["",f"## {f['rule']} — {f['status']}","",f["title"],"",f["message"],"",f"Stan: `{f['stage']}`. ID: `{f['id']}`.",""]
        for s in f["selectors"]:lines.append("    "+s.replace("\n"," "))
        o=representative(f,d);lines += ["",f"Dowód: [{o['cell']}]({o['evidence'][0]})."]
    lines += ["","## Ograniczenia",""]+d["limitations"]
    (root/"REPORT.md").write_text("\n".join(lines)+"\n","utf-8")


def matrix_csv(root: Path,d: dict) -> None:
    with (root/"matrix.csv").open("w",newline="",encoding="utf-8") as h:
        w=csv.writer(h);w.writerow(["finding_id","rule","status","stage",*[c["id"] for c in d["cells"]]])
        for f in d["findings"]:
            w.writerow([f["id"],f["rule"],f["status"],f["stage"],*[sum(o["cell"]==c["id"] for o in f["occurrences"]) or ("not_observed" if c["complete"] else "unknown") for c in d["cells"]]])


def junit(root: Path,d: dict) -> None:
    suite=ET.Element("testsuite",name="testwins")
    for c in d["cells"]:
        test=ET.SubElement(suite,"testcase",name=c["id"],classname="ui.matrix")
        if not c["complete"]:ET.SubElement(test,"error",message="Incomplete execution or evidence; never a pass").text=json.dumps(c["errors"])
        elif c["confirmed"] or c.get("performance_failures"):ET.SubElement(test,"failure",message="Repeated visual violation or explicit performance budget").text="See report.json."
    for c in d["checks"]:
        test=ET.SubElement(suite,"testcase",name=f"{c['cell']}/{c['scene']}/{c['step']}/r{c['repeat']}",classname="ui.required_contract")
        if c['status']=='failed':ET.SubElement(test,'failure',message='Mandatory assertion failed, independent of visual confidence')
        elif c['status']!='passed':ET.SubElement(test,'error',message='Mandatory step blocked or not executed')
    # Anchor gate inconsistencies, including empty or missing matrices.
    test=ET.SubElement(suite,'testcase',name='mandatory-gate',classname='execution.gate')
    if d['gate']['exit_code']:
        ET.SubElement(test,'error' if d['gate']['exit_code']==2 else 'failure',message=d['gate']['status']).text=json.dumps(d['gate']['reasons'])
    suite.set('tests',str(len(suite)))
    suite.set('failures',str(len(suite.findall('testcase/failure'))))
    suite.set('errors',str(len(suite.findall('testcase/error'))))
    ET.ElementTree(suite).write(root/"junit.xml",encoding="utf-8",xml_declaration=True)


def html_report(root: Path,d: dict) -> None:
    e=html.escape
    rows=[]
    for c in d["cells"]:
        rows.append(f"<tr><td>{e(c['browser'])}<small>{e(c['version'] or 'not launched')}</small></td><td>{e(c['device'])}</td><td>{e(c['transport'])}</td><td class='{c['status']}'>{c['status']}</td><td>{c['confirmed']}</td><td>{c['candidates']}</td></tr>")
    cards=[]
    for f in d["findings"]:
        o=representative(f,d);img=o["evidence"][0];annotation=str(Path(img).with_name("annotated.png"))
        cells=", ".join(sorted({x["cell"] for x in f["occurrences"]}))
        cards.append(f"<details class='finding'><summary><span class='badge {f['status']}'>{f['status']}</span> {e(f['title'])}<small>{e(f['rule'])} · {e(f['stage'])}</small></summary><p>{e(f['message'])}</p><pre>{e(chr(10).join(f['selectors']))}</pre><p>{e(cells)}</p><p><a href='{e(img)}'>Screenshot</a> · <a href='{e(o['evidence'][1])}'>DOM / geometry</a></p><a href='{e(annotation)}'><img loading='lazy' src='{e(annotation)}' alt='Annotated screenshot'></a></details>")
    contracts="".join(f"<tr><td>{e(c['cell'])}</td><td>{e(c['scene'])} / {e(c['step'])}</td><td>{c['repeat']}</td><td>{e(c['status'])}</td></tr>" for c in d['checks'])
    doc=f'''<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'">
<title>Testwins · {e(d['project'])}</title><style>
:root{{color-scheme:light dark}}body{{font:16px/1.55 system-ui,sans-serif;max-width:1180px;margin:40px auto;padding:0 24px;background:#101622;color:#e1e7ef}}a{{color:#83c7ff}}h1{{font-size:42px;letter-spacing:-1px;margin:8px 0}}.eyebrow{{letter-spacing:3px;font-size:12px;color:#99abc4}}.lead{{max-width:900px;color:#bac6d6}}.metrics{{display:flex;gap:16px;flex-wrap:wrap;margin:28px 0}}.metric{{border:1px solid #35455c;border-radius:12px;padding:20px 28px;min-width:160px}}.metric b{{display:block;font-size:34px}}table{{width:100%;border-collapse:collapse;overflow:auto}}th,td{{padding:13px 10px;text-align:left;border-bottom:1px solid #344155}}small{{display:block;color:#9dadbf;font-size:12px}}.failed,.confirmed{{color:#ff8c9d}}.candidate,.incomplete{{color:#f4c379}}.observed,.suppressed{{color:#99d9c0}}.finding{{margin:14px 0;border:1px solid #35455c;border-radius:10px;padding:18px}}summary{{cursor:pointer;font-weight:600}}.badge{{font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-right:10px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#1c2636;padding:14px}}img{{max-width:100%;max-height:700px;object-fit:contain;object-position:left top}}input{{box-sizing:border-box;width:100%;padding:14px;font:inherit;border:1px solid #536680;border-radius:8px;background:#182234;color:inherit}}footer{{margin:40px 0;color:#a6b7ca;font-size:13px}}.scroll{{overflow-x:auto}}@media(max-width:600px){{h1{{font-size:30px}}body{{padding:0 14px}}.metric{{flex:1;min-width:100px;padding:12px}}}}
</style><div class="eyebrow">TESTWINS / EVIDENCE FIRST</div><h1>{e(d['project'])}</h1><p class="lead">Powtarzalne naruszenia reguł, kandydaci do oceny i jawne luki pokrycia. Brak znalezionych błędów nie oznacza pełnej poprawności aplikacji.</p><small>{e(d['run_id'])}</small>
<div class="metrics"><div class="metric"><b>{d['summary']['confirmed']}</b>powtarzalnych naruszeń</div><div class="metric"><b>{d['summary']['candidate']}</b>kandydatów do oceny</div><div class="metric"><b>{d['coverage']['incomplete_cells']} / {d['coverage']['expected_cells']}</b>niepełnych komórek</div></div>
<p><a href="REPORT.md">Raport Markdown</a> · <a href="report.json">JSON</a> · <a href="matrix.csv">Macierz CSV</a> · <a href="proposals.json">Propozycje Planfile</a> · <a href="manifest.json">Manifest dowodów</a></p>
<h2>Macierz wykonania</h2><div class="scroll"><table><thead><tr><th>Browser / version</th><th>Device</th><th>Transport</th><th>Status</th><th>Confirmed</th><th>Candidates</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Bramka wykonania: {e(d['gate']['status'])}</h2><p>Kod: {d['gate']['exit_code']} · wymagane: {d['gate']['expected_checks']} · zaliczone: {d['gate']['passed_checks']} · nieudane: {d['gate']['failed_checks']} · niewykonane/zablokowane: {d['gate']['blocked_checks']}</p><div class="scroll"><table><thead><tr><th>Komórka</th><th>Scenariusz / krok</th><th>Powtórzenie</th><th>Stan</th></tr></thead><tbody>{contracts}</tbody></table></div>
<h2>Obserwacje</h2><input id="filter" aria-label="Filtruj obserwacje" placeholder="Filtruj: overlap, mobile, selektor…">{''.join(cards) or '<p>Brak obserwacji spełniających reguły. Sprawdź pokrycie powyżej.</p>'}
<footer><strong>Authority: none.</strong><p>{'<br>'.join(e(x) for x in d['limitations'])}</p></footer>
<script>document.getElementById('filter').addEventListener('input',e=>{{let q=e.target.value.toLowerCase();document.querySelectorAll('.finding').forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))}})</script></html>'''
    (root/"index.html").write_text(doc,"utf-8")
