"""The FeuVert agent: a manual tool-use loop that yields every step for the live trace."""
import json
import os
import time

import anthropic

from . import db, tools

MODEL = os.environ.get("FEUVERT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("FEUVERT_EFFORT", "medium")
MAX_STEPS = 24

SYSTEM = """You are FeuVert, an agent that prepares French town-hall building authorisations (urbanisme).
Given an address and a project, find out exactly what the user must file and what could get the file rejected.

Work like a careful urbanisme consultant:
1. Geocode the address, then get the cadastre parcel, the PLU zone and the protections at that point. Check memory for the parcel.
2. Read the zone's own rules: search the PLU rules document several times with targeted French keywords that matter for this
   project (e.g. hauteur, emprise au sol, implantation par rapport aux limites séparatives / aux voies, aspect extérieur,
   toitures, piscines, panneaux solaires, clôtures, espaces verts / pleine terre). Quote only what the passages say, with page numbers.
3. Apply the national thresholds with check_national_thresholds, passing protected=true if the parcel is in a historic-monument
   perimeter (AC1) or a remarkable heritage site.
4. If something important is missing (no PLU text online, RNU commune, ambiguous zone), say so plainly instead of guessing.
5. Finish by calling submit_report exactly once. Every constraint must name its source (API, PLU page, or code article).
Be concise in any text between tool calls. Facts come from tools; never invent zone codes, rule values or page numbers."""


def _client():
    return anthropic.Anthropic()


_use_fallbacks = os.environ.get("FEUVERT_FALLBACKS", "1") == "1"


def _create(client, messages):
    global _use_fallbacks
    kw = dict(model=MODEL, max_tokens=16000, system=SYSTEM, tools=tools.TOOLS, messages=messages,
              thinking={"type": "adaptive", "display": "summarized"}, output_config={"effort": EFFORT})
    if _use_fallbacks:
        try:
            return client.messages.create(**kw, extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                                          extra_body={"fallbacks": "default"})
        except anthropic.BadRequestError as e:
            if "fallback" not in str(e).lower():
                raise
            _use_fallbacks = False  # account or SDK without the beta: run without it
    return client.messages.create(**kw)


def _for_model(name: str, result: dict) -> str:
    slim = {k: v for k, v in result.items() if k != "geometry"}
    s = json.dumps(slim, ensure_ascii=False)
    return s if len(s) < 14000 else s[:14000] + "…(truncated)"


def run(address: str, project: str, project_type: str = "", area_m2: float = 0, existing_floor_area_m2: float = 0):
    """Yield events: thinking, text, step, result, report, error, done."""
    client = _client()
    t0 = time.time()
    user = (f"Address: {address}\nProject: {project}\n"
            + (f"Project type: {project_type}\n" if project_type else "")
            + (f"New area: {area_m2} m²\n" if area_m2 else "")
            + (f"Existing floor area of the house: {existing_floor_area_m2} m²\n" if existing_floor_area_m2 else ""))
    messages = [{"role": "user", "content": user}]
    report, parcel_key, insee = None, None, None
    usage = {"input": 0, "output": 0}

    for _ in range(MAX_STEPS):
        resp = _create(client, messages)
        usage["input"] += resp.usage.input_tokens
        usage["output"] += resp.usage.output_tokens
        if resp.stop_reason == "refusal":
            yield {"type": "error", "message": "The model declined this request."}
            return
        for b in resp.content:
            if b.type == "thinking" and getattr(b, "thinking", ""):
                yield {"type": "thinking", "text": b.thinking}
            elif b.type == "text" and b.text.strip():
                yield {"type": "text", "text": b.text}
        messages.append({"role": "assistant", "content": resp.content})
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            break
        results = []
        for call in calls:
            args = call.input if isinstance(call.input, dict) else {}
            yield {"type": "step", "tool": call.name, "input": args}
            if call.name == "submit_report":
                report = args
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": "Report received."})
                continue
            t = time.time()
            out = tools.run(call.name, args)
            if call.name == "get_parcel" and out.get("parcel_id"):
                parcel_key, insee = out["parcel_id"], out.get("insee")
            yield {"type": "result", "tool": call.name, "ms": int((time.time() - t) * 1000), "data": out}
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": _for_model(call.name, out),
                            **({"is_error": True} if "error" in out else {})})
        messages.append({"role": "user", "content": results})
        if report is not None:
            break

    if report is None:
        yield {"type": "error", "message": "The agent stopped without a report."}
    else:
        for key in filter(None, (parcel_key, insee)):
            db.remember(key, "analysis", {"address": address, "project": project, "authorisation": report.get("authorisation"),
                                          "zone": report.get("zone"), "summary": report.get("summary")})
        yield {"type": "report", "report": report}
    yield {"type": "done", "seconds": round(time.time() - t0, 1), "usage": usage, "model": MODEL}
