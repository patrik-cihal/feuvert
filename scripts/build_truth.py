"""Ground truth for the eval, from the official sources (not from any model).

zone code/type and historic-monument perimeter come straight from the Géoportail de l'Urbanisme;
the authorisation is the national thresholds applied to those facts. Spot-check 2-3 cases by hand on
https://www.geoportail-urbanisme.gouv.fr/map/ before quoting the numbers.
"""
import json
import pathlib

from app import db, national_rules, tools

db.init()
cases = json.loads(pathlib.Path("eval/cases.json").read_text())
truth = []
for c in cases:
    g = tools.geocode_address(c["address"])
    if "error" in g:
        print(c["id"], "geocode error", g); continue
    z = tools.get_zoning(g["lon"], g["lat"])
    p = tools.get_protections(g["lon"], g["lat"])
    zone = z.get("zone") or {}
    rule = national_rules.check(c["project_type"], c["area_m2"], c["existing_floor_area_m2"],
                                zone_type=zone.get("type") or "RNU", has_plu=bool(zone) or z.get("is_rnu") is False, protected=p["heritage_protected"])
    t = {"id": c["id"], "label": g["label"], "zone_code": zone.get("code"), "zone_type": zone.get("type"),
         "historic_monument_perimeter": p["historic_monument_perimeter"],
         "heritage_protected": p["heritage_protected"], "authorisation": rule["authorisation"]}
    truth.append(t)
    print(t)
pathlib.Path("eval/truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1))
