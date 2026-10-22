"""Before / after: one LLM call with no data (baseline) vs the FeuVert agent, scored against eval/truth.json.

Costs real API money (about $3-5 for 10 cases with Opus; paid from the hackathon Anthropic credits).
Usage: python -m scripts.eval [--only-baseline] [--n 10]
"""
import argparse
import json
import pathlib
import time

import anthropic

from app import agent

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=10)
ap.add_argument("--only-baseline", action="store_true")
a = ap.parse_args()

cases = json.loads(pathlib.Path("eval/cases.json").read_text())[: a.n]
truth = {t["id"]: t for t in json.loads(pathlib.Path("eval/truth.json").read_text())}
client = anthropic.Anthropic()

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["zone_code", "historic_monument_perimeter", "authorisation"],
          "properties": {"zone_code": {"type": "string"}, "historic_monument_perimeter": {"type": "boolean"},
                         "authorisation": {"type": "string", "enum": ["none", "declaration_prealable", "permis_de_construire", "check_commune", "uncertain"]}}}


def baseline(c):
    r = client.messages.create(
        model=agent.MODEL, max_tokens=4000, output_config={"effort": agent.EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"French urbanisme question. Address: {c['address']}. Project: {c['project']} "
                   f"(type {c['project_type']}, {c['area_m2']} m², existing house {c['existing_floor_area_m2']} m²). "
                   "Give the PLU zone code at this address, whether it is inside a historic-monument perimeter (ABF), "
                   "and which authorisation is needed. Answer with your best guess."}])
    return json.loads(next(b.text for b in r.content if b.type == "text"))


def run_agent(c):
    rep, zone, ac1 = {}, None, None
    for ev in agent.run(c["address"], c["project"], c["project_type"], c["area_m2"], c["existing_floor_area_m2"]):
        if ev["type"] == "report":
            rep = ev["report"]
    text = json.dumps(rep, ensure_ascii=False).lower()
    return {"zone_code": rep.get("zone") or "", "authorisation": rep.get("authorisation"),
            "historic_monument_perimeter": any(k in text for k in ("abf", "architecte des bâtiments", "monument historique", "monuments historiques"))}


def score(pred, t):
    zc = (t["zone_code"] or "").upper()
    return {"zone": bool(zc) and zc in (pred.get("zone_code") or "").upper().replace(" ", ""),
            "abf": pred.get("historic_monument_perimeter") == t["historic_monument_perimeter"],
            "auth": pred.get("authorisation") == t["authorisation"]}


rows = []
for c in cases:
    t = truth.get(c["id"])
    if not t:
        continue
    b = baseline(c)
    row = {"id": c["id"], "baseline": score(b, t), "baseline_raw": b}
    if not a.only_baseline:
        t0 = time.time()
        g = run_agent(c)
        row.update({"agent": score(g, t), "agent_raw": g, "agent_s": round(time.time() - t0, 1)})
    rows.append(row)
    print(row)

n = len(rows)
lines = ["# Eval results", "", f"{n} cases (eval/cases.json), truth from the Géoportail de l'Urbanisme (scripts/build_truth.py), model {agent.MODEL}.", "",
         "| Metric | Baseline (one LLM call, no data) | FeuVert agent |", "|---|---|---|"]
for k, name in (("zone", "PLU zone correct"), ("abf", "Historic-monument perimeter correct"), ("auth", "Authorisation type correct")):
    bs = sum(r["baseline"][k] for r in rows)
    ag = sum(r["agent"][k] for r in rows) if not a.only_baseline else None
    lines.append(f"| {name} | {bs}/{n} | {'' if ag is None else f'{ag}/{n}'} |")
pathlib.Path("eval/RESULTS.md").write_text("\n".join(lines) + "\n\n```\n" + json.dumps(rows, ensure_ascii=False, indent=1) + "\n```\n")
print("\n".join(lines))
