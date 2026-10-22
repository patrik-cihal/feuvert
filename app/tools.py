"""Tools the agent can call. Every one hits free French public data, cached in the data layer."""
import io
import json
import re
import urllib.parse

import httpx

from . import db, national_rules

HTTP = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "FeuVert-hackathon/0.1"})
APICARTO = "https://apicarto.ign.fr/api"


def _get_json(url: str, cache: bool = True):
    if cache:
        hit = db.cache_get(url)
        if hit is not None:
            return json.loads(hit)
    r = HTTP.get(url)
    r.raise_for_status()
    data = r.json()
    if cache:
        db.cache_put(url, json.dumps(data))
    return data


def _point(lon: float, lat: float) -> str:
    return urllib.parse.quote(json.dumps({"type": "Point", "coordinates": [lon, lat]}))


# --- 1. address -> coordinates (Base Adresse Nationale) ---
def geocode_address(address: str) -> dict:
    q = urllib.parse.quote(address)
    last_err = None
    for base in ("https://data.geopf.fr/geocodage/search", "https://api-adresse.data.gouv.fr/search/"):
        try:
            data = _get_json(f"{base}?q={q}&limit=1")
            feats = data.get("features") or []
            if not feats:
                return {"error": "address not found"}
            f = feats[0]
            p = f["properties"]
            lon, lat = f["geometry"]["coordinates"]
            return {"label": p.get("label"), "lon": lon, "lat": lat, "insee": p.get("citycode"),
                    "city": p.get("city"), "score": round(p.get("score", 0), 2), "source": base}
        except Exception as e:  # try the next geocoder
            last_err = e
    return {"error": f"geocoding failed: {last_err}"}


# --- 2. coordinates -> cadastre parcel (IGN API Carto) ---
def _dist_to_geom(lon: float, lat: float, geom: dict) -> float:
    """Planar distance (degrees, lon scaled by cos(lat)) from the point to the nearest polygon edge."""
    import math
    k = math.cos(math.radians(lat))
    polys = geom.get("coordinates") or []
    if geom.get("type") == "Polygon":
        polys = [polys]
    best = float("inf")
    for poly in polys:
        for ring in poly:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                ax, ay, bx, by, px, py = x1 * k, y1, x2 * k, y2, lon * k, lat
                dx, dy = bx - ax, by - ay
                t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
                best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def get_parcel(lon: float, lat: float) -> dict:
    data = _get_json(f"{APICARTO}/cadastre/parcelle?geom={_point(lon, lat)}")
    feats = data.get("features") or []
    nearest = False
    if not feats:
        # Address points often sit on the street, outside every parcel: take the nearest parcel within ~20 m.
        d = 0.0002
        box = {"type": "Polygon", "coordinates": [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]]}
        feats = _get_json(f"{APICARTO}/cadastre/parcelle?geom={urllib.parse.quote(json.dumps(box))}").get("features") or []
        feats.sort(key=lambda f: _dist_to_geom(lon, lat, f.get("geometry") or {}))
        nearest = True
    if not feats:
        return {"error": "no parcel at this point"}
    f = feats[0]
    p = f["properties"]
    out = {"parcel_id": p.get("idu"), "section": p.get("section"), "number": p.get("numero"),
           "commune": p.get("nom_com"), "insee": p.get("code_insee"), "area_m2": p.get("contenance"),
           "geometry": f.get("geometry"), "source": "IGN API Carto, module cadastre"}
    if nearest:
        out["note"] = "The address point is outside any parcel (on the street); this is the nearest parcel. Confirm with the owner's deed."
    return out


# --- 3. coordinates -> PLU zone (Géoportail de l'Urbanisme via API Carto GPU) ---
def get_zoning(lon: float, lat: float) -> dict:
    out = {"source": "Géoportail de l'Urbanisme (IGN API Carto, module GPU)"}
    try:
        docs = _get_json(f"{APICARTO}/gpu/document?geom={_point(lon, lat)}").get("features") or []
        out["documents"] = [{k: d["properties"].get(k) for k in ("du_type", "partition", "grid_title", "legal_status", "title")}
                            for d in docs[:3]]
    except Exception as e:
        out["documents_error"] = str(e)
    zones = _get_json(f"{APICARTO}/gpu/zone-urba?geom={_point(lon, lat)}").get("features") or []
    if not zones:
        out["zone"] = None
        try:
            muni = (_get_json(f"{APICARTO}/gpu/municipality?geom={_point(lon, lat)}").get("features") or [{}])[0].get("properties") or {}
        except Exception:
            muni = {}
        out["is_rnu"] = muni.get("is_rnu")
        if muni.get("is_rnu"):
            out["note"] = "The commune is under the national rules (RNU): no PLU applies."
        elif muni:
            out["note"] = ("The commune is not RNU but its PLU/carte communale is not published on the Géoportail: "
                           "get the règlement from the mairie; don't assume national rules only.")
        else:
            out["note"] = "No PLU zone here: the commune may be under the national rules (RNU) or a carte communale."
        return out
    p = zones[0]["properties"]
    rules_url = p.get("urlfic") or None
    if not rules_url and p.get("nomfic") and p.get("partition") and p.get("gpu_doc_id"):
        # urlfic is usually empty; the GPU serves the written rules at this path.
        rules_url = f"https://data.geopf.fr/annexes/gpu/documents/{p['partition']}/{p['gpu_doc_id']}/{p['nomfic']}"
    out["zone"] = {"code": p.get("libelle"), "label": p.get("libelong"), "type": p.get("typezone"),
                   "partition": p.get("partition"), "approved": p.get("datappro"),
                   "rules_file": p.get("nomfic"), "rules_url": rules_url}
    return out


# --- 4. protections: servitudes (historic monuments = AC1) and PLU prescriptions ---
SUP_LABELS = {"ac1": "Historic monument surroundings (ABF opinion required)", "ac2": "Classified/registered site",
              "ac4": "Site patrimonial remarquable", "pm1": "Natural risk prevention plan (PPR)",
              "pm3": "Technological risk prevention plan", "el7": "Road alignment", "t5": "Aviation clearance",
              "i4": "Electricity line easement", "as1": "Water catchment protection"}


def get_protections(lon: float, lat: float) -> dict:
    out = {"servitudes": [], "prescriptions": [], "source": "Géoportail de l'Urbanisme (SUP + PLU prescriptions)"}
    for res in ("assiette-sup-s", "assiette-sup-l", "assiette-sup-p"):
        try:
            for f in (_get_json(f"{APICARTO}/gpu/{res}?geom={_point(lon, lat)}").get("features") or [])[:10]:
                p = f["properties"]
                t = (p.get("suptype") or "").lower()
                out["servitudes"].append({"type": t, "meaning": SUP_LABELS.get(t, "see servitude list"),
                                          "name": p.get("nomass") or p.get("nomsuplitt") or p.get("idass")})
        except Exception as e:
            out.setdefault("errors", []).append(f"{res}: {e}")
    for res in ("prescription-surf", "prescription-lin", "prescription-pct"):
        try:
            for f in (_get_json(f"{APICARTO}/gpu/{res}?geom={_point(lon, lat)}").get("features") or [])[:10]:
                p = f["properties"]
                out["prescriptions"].append({"label": p.get("libelle"), "type": p.get("typepsc")})
        except Exception as e:
            out.setdefault("errors", []).append(f"{res}: {e}")
    out["historic_monument_perimeter"] = any(s["type"] == "ac1" for s in out["servitudes"])
    # Any heritage protection (AC1 monument surroundings, AC2 site, AC4 SPR, PSMV perimeter) makes the ABF review apply.
    out["heritage_protected"] = out["historic_monument_perimeter"] or any(s["type"] in ("ac2", "ac4") for s in out["servitudes"]) \
        or any("psmv" in (x.get("label") or "").lower() for x in out["prescriptions"])
    return out


# --- 5. natural risks (Géorisques) ---
def get_risks(lon: float, lat: float) -> dict:
    try:
        data = _get_json(f"https://georisques.gouv.fr/api/v1/gaspar/risques?latlon={lon},{lat}")
        items = (data.get("data") or [{}])[0].get("risques_detail") or []
        return {"risks": [i.get("libelle_risque_long") for i in items][:12], "source": "Géorisques (BRGM)"}
    except Exception as e:
        return {"error": f"Géorisques unavailable: {e}"}


# --- 6. PLU rules text: ingest the zone's rules PDF once, then full-text search ---
# Zone codes appear plain ("zone UA", "zone 1AUh") or dotted ("ZONE S.B.", "ARTICLE S. B. 6").
_ZCODE = r"((?:[0-9]?[A-Z](?:\s?\.\s?[A-Z0-9'’]){1,4}\.?)|(?:[0-9]?[A-Z]{1,3}[A-Za-z0-9\-]{0,5}))"
ZONE_HEADING = re.compile(r"(?:dispositions\s+applicables\s+(?:à|a|aux)\s+(?:la\s+)?(?:zones?|secteurs?)|^\s*zone)\s+" + _ZCODE + r"(?![A-Za-z0-9])",
                          re.IGNORECASE | re.MULTILINE)
ARTICLE_HEADING = re.compile(r"ARTICLE\s+([0-9]?[A-Z](?:\s?\.?\s?[A-Z0-9]){0,4}?)\s?\.?\s+\d{1,2}\s*[-–:]")


_NOT_ZONES = {"URBAINES", "URBAINE", "NATURELLES", "NATURELLE", "AGRICOLES", "AGRICOLE", "URBANISER", "DE", "ET", "LA", "LES"}


def _norm_zone(code: str) -> str:
    return re.sub(r"[\s.'’]", "", code).upper()


def ingest_pdf(doc_key: str, url: str, pdf_bytes: bytes | None = None, max_pages: int = 900) -> dict:
    from pypdf import PdfReader
    if pdf_bytes is None:
        r = HTTP.get(url, timeout=120)
        r.raise_for_status()
        pdf_bytes = r.content
        if not pdf_bytes.startswith(b"%PDF"):
            return {"error": "rules_url is not a PDF (maybe a zip or HTML page); ingest it with scripts/ingest_plu.py"}
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks, zone = [], ""
    for i, page in enumerate(reader.pages[:max_pages]):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        m = ZONE_HEADING.search(text[:600]) or ARTICLE_HEADING.search(text[:400])
        if m and _norm_zone(m.group(1)) not in _NOT_ZONES:
            zone = _norm_zone(m.group(1))
        for j in range(0, len(text), 1500):
            chunks.append({"page": i + 1, "zone": zone, "text": text[j:j + 1700]})
    db.add_chunks(doc_key, url, chunks)
    return {"ingested_pages": min(len(reader.pages), max_pages), "chunks": len(chunks)}


def search_zone_rules(rules_url: str, zone: str, query: str) -> dict:
    if not rules_url:
        return {"error": "no rules_url for this zone; the commune's PLU text is not on the Géoportail. Say so and rely on national rules."}
    doc_key = rules_url
    info = {}
    if not db.has_doc(doc_key):
        try:
            info = ingest_pdf(doc_key, rules_url)
        except Exception as e:
            return {"error": f"could not download/parse the rules PDF: {e}"}
        if "error" in info:
            return info
    hits = db.search_chunks(doc_key, query, zone=(zone or "").upper())
    return {"zone": zone, "query": query, "ingested_now": info or None, "source_url": rules_url,
            "passages": [{"page": h["page"], "zone": h["zone"], "text": h["text"][:1200]} for h in hits]}


# --- 7. national thresholds (deterministic) ---
def check_national_thresholds(**kw) -> dict:
    return national_rules.check(**kw)


# --- 8. memory: past analyses of this parcel / commune ---
def recall_memory(key: str) -> dict:
    return {"key": key, "past": db.recall(key)}


TOOLS = [
    {"name": "geocode_address", "description": "Find coordinates, INSEE commune code and normalised label for a French address (Base Adresse Nationale).",
     "input_schema": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]}},
    {"name": "get_parcel", "description": "Cadastre parcel at a point: parcel id, section, number, area in m².",
     "input_schema": {"type": "object", "properties": {"lon": {"type": "number"}, "lat": {"type": "number"}}, "required": ["lon", "lat"]}},
    {"name": "get_zoning", "description": "Planning document (PLU/PLUi/carte communale/RNU) and PLU zone at a point, with the URL of the zone's rules PDF.",
     "input_schema": {"type": "object", "properties": {"lon": {"type": "number"}, "lat": {"type": "number"}}, "required": ["lon", "lat"]}},
    {"name": "get_protections", "description": "Public-utility servitudes (e.g. AC1 historic-monument surroundings needing the ABF) and PLU prescriptions (protected trees, reserved land) at a point.",
     "input_schema": {"type": "object", "properties": {"lon": {"type": "number"}, "lat": {"type": "number"}}, "required": ["lon", "lat"]}},
    {"name": "get_risks", "description": "Natural and technological risks known for the commune at this point (Géorisques).",
     "input_schema": {"type": "object", "properties": {"lon": {"type": "number"}, "lat": {"type": "number"}}, "required": ["lon", "lat"]}},
    {"name": "search_zone_rules", "description": "Full-text search in the PLU rules document for the zone (downloads and indexes it on first use). Use French keywords, e.g. 'hauteur maximale', 'emprise au sol', 'implantation limites séparatives', 'piscine', 'panneaux solaires', 'clôture'. Call several times with different queries.",
     "input_schema": {"type": "object", "properties": {"rules_url": {"type": "string"}, "zone": {"type": "string"}, "query": {"type": "string"}},
                      "required": ["rules_url", "zone", "query"]}},
    {"name": "check_national_thresholds", "description": "Apply the Code de l'urbanisme thresholds: which authorisation (none / déclaration préalable / permis de construire), which CERFA form, review time, architect requirement.",
     "input_schema": {"type": "object", "properties": {
         "project_type": {"type": "string", "enum": national_rules.PROJECT_TYPES},
         "area_m2": {"type": "number", "description": "new floor area / footprint / pool area"},
         "existing_floor_area_m2": {"type": "number"}, "zone_type": {"type": "string", "description": "U, AU, A, N, or RNU"},
         "has_plu": {"type": "boolean"}, "protected": {"type": "boolean", "description": "historic-monument surroundings or remarkable heritage site"},
         "pool_cover_height_m": {"type": "number"}}, "required": ["project_type"]}},
    {"name": "recall_memory", "description": "Past analyses stored for a parcel id or INSEE code (what was found before, what changed).",
     "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}},
    {"name": "submit_report", "description": "Submit the final structured answer. Call this exactly once, at the end.",
     "input_schema": {"type": "object", "additionalProperties": False, "properties": {
         "summary": {"type": "string", "description": "2-3 sentences for the user"},
         "authorisation": {"type": "string", "enum": ["none", "declaration_prealable", "permis_de_construire", "check_commune", "uncertain"]},
         "form": {"type": "string"},
         "review_time_months": {"type": "number"},
         "architect_required": {"type": "boolean"},
         "parcel": {"type": "string"}, "zone": {"type": "string"},
         "constraints": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
             "title": {"type": "string"}, "detail": {"type": "string"}, "source": {"type": "string"}}, "required": ["title", "detail", "source"]}},
         "documents": {"type": "array", "items": {"type": "string"}},
         "risks_of_rejection": {"type": "array", "items": {"type": "string"}},
         "next_steps": {"type": "array", "items": {"type": "string"}},
         "cover_letter_fr": {"type": "string", "description": "short draft cover note to the mairie, in French"},
         "confidence": {"type": "string", "enum": ["low", "medium", "high"]}},
         "required": ["summary", "authorisation", "constraints", "documents", "next_steps", "confidence"]}},
]

FUNCS = {"geocode_address": geocode_address, "get_parcel": get_parcel, "get_zoning": get_zoning,
         "get_protections": get_protections, "get_risks": get_risks, "search_zone_rules": search_zone_rules,
         "check_national_thresholds": check_national_thresholds, "recall_memory": recall_memory}


def run(name: str, args: dict) -> dict:
    fn = FUNCS.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"bad arguments: {e}"}
    except httpx.HTTPError as e:
        return {"error": f"public API error: {e}"}
