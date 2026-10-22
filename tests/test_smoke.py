"""Offline smoke test: mocked public APIs + a scripted model. Run: python -m tests.test_smoke"""
import json
import os
import tempfile
from types import SimpleNamespace as NS

os.environ["SQLITE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.pop("DATABASE_URL", None)
os.environ["FEUVERT_RUNS_DIR"] = tempfile.mkdtemp()  # keep the fake run out of runs/last.json (the demo replay)

from app import agent, db, national_rules, tools  # noqa: E402

db.init()

FAKE = {
    "geocodage": {"features": [{"geometry": {"coordinates": [2.13, 48.80]}, "properties": {"label": "12 Rue de la Paroisse 78000 Versailles", "citycode": "78646", "city": "Versailles", "score": 0.97}}]},
    "cadastre/parcelle": {"features": [{"geometry": {"type": "Polygon", "coordinates": [[[2.13, 48.8], [2.1301, 48.8], [2.1301, 48.8001], [2.13, 48.8]]]},
                                        "properties": {"idu": "78646000AB0123", "section": "AB", "numero": "0123", "nom_com": "Versailles", "code_insee": "78646", "contenance": 412}}]},
    "gpu/document": {"features": [{"properties": {"du_type": "PLU", "partition": "DU_78646"}}]},
    "gpu/zone-urba": {"features": [{"properties": {"libelle": "UA", "libelong": "Zone urbaine centrale", "typezone": "U", "partition": "DU_78646", "urlfic": "https://example.org/reglement.pdf"}}]},
    "assiette-sup-s": {"features": [{"properties": {"suptype": "ac1", "nomass": "Église Notre-Dame"}}]},
    "georisques": {"data": [{"risques_detail": [{"libelle_risque_long": "Retrait-gonflement des argiles"}]}]},
}


class Resp:
    def __init__(self, data): self.data = data
    def raise_for_status(self): pass
    def json(self): return self.data


def fake_get(url, **kw):
    for k, v in FAKE.items():
        if k in url:
            return Resp(v)
    return Resp({"features": []})


tools.HTTP.get = fake_get
db.add_chunks("https://example.org/reglement.pdf", "https://example.org/reglement.pdf", [
    {"page": 41, "zone": "UA", "text": "Article UA 10 - Hauteur maximale des constructions : la hauteur ne peut excéder 12 mètres."},
    {"page": 38, "zone": "UA", "text": "Article UA 7 - Implantation par rapport aux limites séparatives : retrait minimal de 3 mètres."},
])


def tu(i, name, inp):
    return NS(type="tool_use", id=f"t{i}", name=name, input=inp)


SCRIPT = [
    [NS(type="thinking", thinking="Start with the address."), tu(1, "geocode_address", {"address": "12 rue de la Paroisse, Versailles"})],
    [tu(2, "get_parcel", {"lon": 2.13, "lat": 48.8}), tu(3, "get_zoning", {"lon": 2.13, "lat": 48.8}), tu(4, "get_protections", {"lon": 2.13, "lat": 48.8}), tu(5, "recall_memory", {"key": "78646000AB0123"})],
    [tu(6, "search_zone_rules", {"rules_url": "https://example.org/reglement.pdf", "zone": "UA", "query": "hauteur maximale"}),
     tu(7, "check_national_thresholds", {"project_type": "extension", "area_m2": 25, "existing_floor_area_m2": 110, "zone_type": "U", "has_plu": True, "protected": True})],
    [NS(type="text", text="Done."), tu(8, "submit_report", {"summary": "DP needed.", "authorisation": "declaration_prealable", "zone": "UA", "constraints": [{"title": "Height", "detail": "12 m max", "source": "PLU p.41"}],
                                                          "documents": ["DPMI1 plan de situation"], "next_steps": ["File online"], "confidence": "high"})],
]


class FakeMessages:
    def __init__(self): self.i = 0
    def create(self, **kw):
        assert kw["model"] == agent.MODEL and kw["tools"] and "temperature" not in kw
        content = SCRIPT[self.i]; self.i += 1
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return NS(content=content, stop_reason=stop, usage=NS(input_tokens=100, output_tokens=20))


agent._client = lambda: NS(messages=FakeMessages())
events = list(agent.run("12 rue de la Paroisse, Versailles", "extension 25 m²", "extension", 25, 110))
kinds = [e["type"] for e in events]
print(kinds)
res = {e["tool"]: e["data"] for e in events if e["type"] == "result"}
assert res["get_zoning"]["zone"]["code"] == "UA"
assert res["get_protections"]["historic_monument_perimeter"] is True
assert res["search_zone_rules"]["passages"][0]["page"] == 41, res["search_zone_rules"]
assert res["check_national_thresholds"]["authorisation"] == "declaration_prealable"
assert res["check_national_thresholds"]["review_time_months"] == 2
assert kinds[-2:] == ["report", "done"]
assert db.recall("78646000AB0123")[0]["data"]["authorisation"] == "declaration_prealable"

# national thresholds
c = national_rules.check
assert c("extension", 30, 110, "U")["authorisation"] == "declaration_prealable"
assert c("extension", 30, 130, "U")["authorisation"] == "permis_de_construire"   # passes 150 m2
assert c("extension", 30, 110, "N")["authorisation"] == "permis_de_construire"
assert c("extension", 50, 120, "U")["architect_required"] is True
assert c("pool", 32)["authorisation"] == "declaration_prealable"
assert c("pool", 8, protected=True)["authorisation"] == "declaration_prealable"
assert c("pool", 120)["authorisation"] == "permis_de_construire"

# API + SSE
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
agent._client = lambda: NS(messages=FakeMessages())
cl = TestClient(app)
assert cl.get("/").status_code == 200
print(cl.get("/api/stats").json())
body = cl.post("/api/analyze", json={"address": "x", "project": "y"}).text
evs = [json.loads(l[6:]) for l in body.split("\n\n") if l.startswith("data: ")]
assert evs[-1]["type"] == "done", evs[-1]
print("smoke test OK:", len(evs), "SSE events")

# replay: the successful run above was recorded and plays back
import app.main as m  # noqa: E402
rep = cl.get("/api/replay?speed=100").text
revs = [json.loads(l[6:]) for l in rep.split("\n\n") if l.startswith("data: ")]
assert revs and revs[-1]["type"] == "done" and any(e["type"] == "report" for e in revs), revs[-3:]
assert cl.get("/api/last_request").json()["address"] == "x"
print("replay OK:", len(revs), "events")
