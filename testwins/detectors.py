from __future__ import annotations
from collections import defaultdict
from statistics import median
from .model import Finding


def intersection(a: dict, b: dict) -> dict:
    x, y = max(a["x"], b["x"]), max(a["y"], b["y"])
    return {"x":x,"y":y,"width":max(0,min(a["x"]+a["width"],b["x"]+b["width"])-x),
            "height":max(0,min(a["y"]+a["height"],b["y"]+b["height"])-y)}


def area(r: dict) -> float: return max(0,r["width"])*max(0,r["height"])


def edge(r: dict, key: str) -> float:
    return {"left":r["x"],"right":r["x"]+r["width"],"top":r["y"],
            "bottom":r["y"]+r["height"],"center_x":r["x"]+r["width"]/2,
            "center_y":r["y"]+r["height"]/2}[key]


def detect(snapshot: dict, cfg: dict, device: dict) -> list[dict]:
    findings: dict[tuple, Finding] = {}
    rules = cfg["rules"]
    def emit(f: Finding) -> None:
        key = (f.rule, tuple(sorted(set(f.selectors))))
        if key not in findings: findings[key] = f
    from .overlays import assess_overlays
    overlay_findings, intentional_coverage = assess_overlays(snapshot, cfg)
    vp = snapshot["viewport"]
    if snapshot["document"]["width"] > vp["width"]+rules["clip_px"]:
        offenders = [n for n in snapshot["nodes"] if n["tag"] not in ("html","body")
                     and n["rect"]["x"]+n["rect"]["width"] > vp["width"]+2
                     and n["rect"]["y"] < vp["height"] and n["rect"]["y"]+n["rect"]["height"]>0]
        offenders.sort(key=lambda n:n["rect"]["width"])
        emit(Finding("TW-VIEWPORT-OVERFLOW","Poziome przepełnienie strony",
             f"Dokument ma {snapshot['document']['width']} CSS px przy widoku {vp['width']} CSS px.",
             ["html"], [n["rect"] for n in offenders[:5]], "high", .96,
             details={"overflow_css_px":snapshot["document"]["width"]-vp["width"],
                      "offenders":[n["selector"] for n in offenders[:10]]}))
    if device["mobile"] and snapshot.get('scope',{}).get('kind') != 'frame' and not snapshot["hasViewportMeta"]:
        emit(Finding("TW-VIEWPORT-META","Brak deklaracji mobilnego viewportu",
             "Mobilna symulacja nie znalazła meta viewport; sprawdź skalowanie tekstu i szerokość układu.",
             ["head"],[],"normal",.7,True))
    # Spatial bucketing, then actual text-range intersection. Never compare generic container boxes.
    grid: dict[tuple,list[int]] = defaultdict(list)
    seen_pairs=set(); budget=150000; comparisons=0
    texts = snapshot["texts"]
    for i,t in enumerate(texts):
        r=t["visibleRect"]
        if (t.get("localClipX") or t.get("localClipY")) and not t.get("intentional"):
            emit(Finding("TW-TEXT-CLIPPED","Tekst obcięty przez CSS overflow",
                 "Widoczny fragment tekstu wychodzi poza obszar przycinania, bez jawnego ellipsis/line-clamp.",
                 [t["selector"]],[t["rect"]],"high",.91,
                 details={"horizontal":t.get("localClipX",False),"vertical":t.get("localClipY",False)}))
        buckets=[(x,y) for x in range(int(r["x"]//128),int((r["x"]+r["width"])//128)+1)
                 for y in range(int(r["y"]//128),int((r["y"]+r["height"])//128)+1)]
        for b in buckets:
            for j in grid[b]:
                pair=(j,i)
                if pair in seen_pairs: continue
                seen_pairs.add(pair); comparisons+=1
                if comparisons>budget: break
                u=texts[j]
                if t["selector"]==u["selector"]: continue
                if t["selector"] in u.get("ancestors",[]) or u["selector"] in t.get("ancestors",[]): continue
                overlap=intersection(r,u["visibleRect"])
                fraction=area(overlap)/max(1,min(area(r),area(u["visibleRect"])))
                if overlap["width"]>rules["overlap_px"] and overlap["height"]>rules["overlap_px"] and fraction>rules["overlap_fraction"]:
                    transformed=t.get("transformed") or u.get("transformed")
                    emit(Finding("TW-TEXT-OVERLAP","Nakładające się fragmenty tekstu",
                         "Niezależne zakresy tekstowe mają wspólny obszar. Intencjonalne kompozycje wymagają jawnego wykluczenia.",
                         [t["selector"],u["selector"]],[r,u["visibleRect"]],"high",.68 if transformed else .92,
                         bool(transformed),{"intersection":overlap,"fraction":round(fraction,4)}))
            if comparisons>budget: break
            grid[b].append(i)
        if comparisons>budget:
            snapshot["gaps"].append({"kind":"detector_limit","reason":"Text-pair comparison budget exceeded."});break
    for n in snapshot["nodes"]:
        vr=n["visibleRect"]
        if not area(vr): continue
        if n["brokenImage"]:
            emit(Finding("TW-IMAGE-BROKEN","Obraz nie został wyświetlony",
                         "Element img zakończył ładowanie, ale naturalWidth wynosi zero.",
                         [n["selector"]],[vr],"normal",.97))
        if not n["interactive"] or n["disabled"] or n["inert"]: continue
        if n["hitSamples"] and n["occluded"]/n["hitSamples"]>=.6 and not any(
                c["covering"] == n["covering"] and c["occluded"] == n["occluded"]
                for c in intentional_coverage.get(n["selector"], [])):
            emit(Finding("TW-CONTROL-OCCLUDED","Kontrolka zasłonięta dla kliknięcia",
                         f"Test trafienia wskazał obcy element w {n['occluded']}/{n['hitSamples']} próbek.",
                         [n["selector"]],[vr],"high",.94,details={"covering":n["covering"]}))
        target_size=n.get("targetSize") or vr
        if device["touch"] and (target_size["width"]<rules["target_px"] or target_size["height"]<rules["target_px"]):
            if n["tag"]=="a" and n["display"]=="inline": continue
            emit(Finding("TW-TARGET-SMALL","Mały cel dotykowy — do oceny",
                         "Cel jest mniejszy niż skonfigurowany próg. Reguła nie rozstrzyga wyjątków odstępu ani równoważnych kontrolek.",
                         [n["selector"]],[vr],"low",.60,True,
                         details={"target_size":{"width":target_size["width"],"height":target_size["height"]},
                                  "visible_size":{"width":vr["width"],"height":vr["height"]},
                                  "measurement":"scroll-aware" if n.get("targetSize") else "visible-fragment"}))
    for a in snapshot.get("alignments",[]):
        nodes=a["nodes"]
        if len(nodes)<2:
            snapshot["gaps"].append({"kind":"alignment_contract","reason":f"Alignment group {a['id']} matched fewer than two visible nodes."})
            continue
        values=[edge(n["rect"],a["edge"]) for n in nodes]
        if max(values)-min(values)>a["tolerance"]:
            emit(Finding("TW-ALIGNMENT","Naruszenie kontraktu wyrównania",
                         f"Grupa {a['id']}: rozrzut {max(values)-min(values):.2f} px na krawędzi {a['edge']}.",
                         [n["selector"] for n in nodes],[n["rect"] for n in nodes],"normal",.99,
                         details={"group":a["id"],"edge":a["edge"],"spread":max(values)-min(values),"tolerance":a["tolerance"]}))
    if rules["heuristic_alignment"]:
        groups=defaultdict(list)
        for n in snapshot["nodes"]:
            if n["tag"] not in ("html","body","span","br") and area(n["visibleRect"]): groups[n["parent"]].append(n)
        for group in groups.values():
            if not 3<=len(group)<=20: continue
            xs=[n["rect"]["x"] for n in group]; widths=[n["rect"]["width"] for n in group]
            if median(widths)<30 or max(widths)-min(widths)>median(widths)*.3: continue
            m=median(xs); outliers=[n for n in group if 4<abs(n["rect"]["x"]-m)<24]
            aligned=[n for n in group if abs(n["rect"]["x"]-m)<=2]
            if len(aligned)>=2 and len(outliers)==1:
                n=outliers[0]
                emit(Finding("TW-ALIGNMENT-CANDIDATE","Możliwe odchylenie od wyrównania rodzeństwa",
                             "Podobne elementy mają wspólną lewą krawędź z jednym odstępstwem; intencja układu nie jest znana.",
                             [n["selector"]],[n["rect"]],"low",.61,True))
    return overlay_findings + [f.to_dict() for f in findings.values()]


def from_axe(result: dict) -> list[dict]:
    out=[]
    for violation in result.get("violations",[]):
        for n in violation.get("nodes",[]):
            out.append(Finding("TW-AXE-"+violation["id"].upper(),violation.get("help",violation["id"]),
                "Automatyczna reguła dostępności: "+violation["id"],
                [str(s) for s in n.get("target",[])],[],
                "high" if violation.get("impact") in ("serious","critical") else "normal",.98,
                details={"axe_id":violation["id"],"impact":violation.get("impact"),
                         "helpUrl":violation.get("helpUrl","")}).to_dict())
    return out
