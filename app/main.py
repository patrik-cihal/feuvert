import json
import os
import pathlib
import time

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import agent, db

app = FastAPI(title="FeuVert")
ROOT = pathlib.Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
RUNS = pathlib.Path(os.environ.get("FEUVERT_RUNS_DIR", ROOT / "runs"))
RUNS.mkdir(exist_ok=True)
db.init()


class Ask(BaseModel):
    address: str
    project: str
    project_type: str = ""
    area_m2: float = 0
    existing_floor_area_m2: float = 0


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/stats")
def stats():
    return {**db.stats(), "documents": db.count_chunks()}


@app.post("/api/analyze")
def analyze(q: Ask):
    def events():
        log, t0 = [], time.time()
        try:
            for ev in agent.run(q.address, q.project, q.project_type, q.area_m2, q.existing_floor_area_m2):
                log.append({"t": round(time.time() - t0, 2), "ev": ev})
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:  # surface failures in the UI instead of a dead stream
            yield f"data: {json.dumps({'type': 'error', 'message': f'{type(e).__name__}: {e}'})}\n\n"
        if any(x["ev"]["type"] == "report" for x in log):  # keep successful runs for replay
            rec = json.dumps({"request": q.model_dump(), "events": log}, ensure_ascii=False, default=str)
            (RUNS / f"{int(t0)}.json").write_text(rec)
            (RUNS / "last.json").write_text(rec)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/replay")
def replay(speed: float = 1.0):
    """Play back the last successful run (demo safety net when the venue network is slow)."""
    f = RUNS / "last.json"
    if not f.exists():
        return {"error": "no recorded run yet: do one live run first"}
    rec = json.loads(f.read_text())

    def events():
        prev = 0.0
        for x in rec["events"]:
            time.sleep(max(0.0, min(2.5, (x["t"] - prev) / max(speed, 0.1))))
            prev = x["t"]
            yield f"data: {json.dumps(x['ev'], ensure_ascii=False)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/last_request")
def last_request():
    f = RUNS / "last.json"
    return json.loads(f.read_text())["request"] if f.exists() else {}
