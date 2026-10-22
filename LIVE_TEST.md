# FeuVert live test (PC `hp`, 2026-10-22)

## Summary
| Step | Result |
|---|---|
| 1. Code from `claude/epic-franklin-wnursa` | OK |
| 2. venv + deps | OK. `python3 -m venv` fails on this PC (no ensurepip), so I used `uv venv` + `uv pip install` |
| 3. Smoke test | OK: `smoke test OK: 19 SSE events` (before and after the fixes) |
| 4. Live public APIs | geocode, zoning, protections and risks OK. **Fixed:** parcel was always empty, rules_url was always empty |
| 5. PLU ingest + search | **Fixed** zone tagging. Versailles PSMV (117 pages, 8 s) and Montreuil PLUi (635 pages, 38 s) both ingest; searches return passages for the right zone |
| 6. build_truth | OK, 10/10 cases. eval/truth.json written |
| 7. Agent end-to-end + eval | **SKIPPED: no ANTHROPIC_API_KEY on this PC** (not in env or any .env). $0 API spend |

## What I fixed
1. **`get_parcel` always returned "no parcel at this point".** Field names were right (`idu`, `contenance`, `section`, `numero`, `nom_com`, `code_insee`). The cause: BAN/geopf address points sit on the street, outside every parcel. Now, if the point query is empty, it queries a ~20 m box and takes the parcel nearest the point (distance to polygon edges), with a `note` saying it is the nearest parcel. Versailles -> `78646000AE0181` (450 m²), Montreuil -> `93048000BH0083` (277 m²).
2. **`rules_url` was always None/"".** GPU `urlfic` is empty in practice. The rules PDF is served at `https://data.geopf.fr/annexes/gpu/documents/{partition}/{gpu_doc_id}/{nomfic}` (checked: HTTP 200, application/pdf, for both test addresses). `get_zoning` now builds that URL when `urlfic` is empty.
3. **Zone tagging in `ingest_pdf` was wrong**, so `search_zone_rules(..., 'SB', ...)` returned SC/S passages. Versailles writes zones dotted ("ZONE S.B.", "ARTICLE S. B. 6"), which the regex read as "S". The new regex handles dotted and plain codes, falls back to `ARTICLE XX n -` headings, normalises (removes dots/spaces), and ignores words like "URBAINES" (from "dispositions applicables aux zones urbaines"). Versailles chunks now: SD 60, SA 42, SC 33, SB 20, untagged 15.
4. **Search ranking (`db.search_chunks`, sqlite and PG):** exact zone first, then chunks whose zone is a prefix of the requested one. PLUi sub-zones like `UC91Jb2` then match the `UC` chapter.
5. **Heritage protection:** Versailles is in an AC4 Site patrimonial remarquable / PSMV, not AC1, so `historic_monument_perimeter` was False and build_truth treated the site as unprotected. Added `heritage_protected` (AC1, AC2, AC4 or a PSMV perimeter prescription). `build_truth` now passes that as `protected` and also writes it into truth.json.
6. **No zone ≠ RNU.** For Saint-Germain-en-Laye (case 4) the GPU has no document, but the commune is **not** RNU (`/gpu/municipality` says `is_rnu: false`); its PLU just isn't published. `get_zoning` now returns `is_rnu` and a note telling the agent to get the règlement from the mairie. `build_truth` uses `has_plu = zone found OR is_rnu is False`.

## Still open / worth knowing
- **Eval label mismatch (needs a decision):** `eval.py` scores "abf" by whether the agent mentions ABF / monument historique, against truth `historic_monument_perimeter` (AC1 only). In SPR/PSMV sites (Versailles, Le Vésinet, Sceaux, Vincennes, Fontainebleau, Saint-Germain all have `heritage_protected: true` but AC1 false), the ABF is also required, so a correct agent gets marked wrong. Suggest scoring against `heritage_protected` instead. I didn't change it since no eval could run here.
- The Montreuil address only geocodes to street level ("Rue de Paris 93100 Montreuil", score 0.81); number 20 isn't in BAN. The nearest-parcel fallback still gives a parcel, but it is approximate.
- Versailles still has 15 untagged chunks (title pages and general provisions), which is expected.
- Agent end to end (step 7) is untested live. It needs a key: run step 7 wherever one exists.

## Follow-up (after pulling the replay-mode update, 04fddec)
- Pulled app/main.py, static/index.html, tests/test_smoke.py, .gitignore and README.md from the branch. They don't touch my fixed files, so there were no conflicts. Smoke test: `smoke test OK: 19 SSE events` + `replay OK: 19 events`.
- **Fixed a demo hazard:** the smoke test POSTs to /api/analyze with the scripted fake run, and main.py saved it as `runs/last.json`. So running the smoke test replaced the real recording with fake Versailles data (example.org, parcel AB0123), and `/api/replay` then played that fake run. Fix: `RUNS` now reads `FEUVERT_RUNS_DIR` (default `runs/`), and the smoke test points it at a temp dir. Verified: after the smoke test, `runs/` doesn't exist. **If any machine already ran the smoke test, delete its runs/last.json before recording the demo run.**
- Web app: `uvicorn app.main:app --port 8000` starts. `GET /` 200. `/api/stats` shows both ingested PLUs (1316 chunks). `/api/replay` -> "no recorded run yet". POST /api/analyze for the Montreuil · solar preset streams one clean error event: `TypeError: Could not resolve authentication method...` (no key). So **priorities 2–4 (agent run, live run through the UI to record runs/last.json, eval) are blocked here on the missing ANTHROPIC_API_KEY.** The app is still running on the PC at localhost:8000.
- Fixes committed on branch `feuvert-live-fixes` of the core repo (based on claude/epic-franklin-wnursa @04fddec): app/tools.py, app/db.py, app/main.py, scripts/build_truth.py, tests/test_smoke.py, eval/truth.json, LIVE_TEST.md. No keys, no runs/, no .db.

## Step 4 output (trimmed, after fixes)
```
GEO {'label': '12 Rue de la Paroisse 78000 Versailles', 'lon': 2.125997, 'lat': 48.808135, 'insee': '78646', 'city': 'Versailles', 'score': 0.98}
ZONING zone {'code': 'SB', 'label': "Zone d'habitation dense ...", 'type': 'U', 'partition': 'PSMV_78646', 'rules_file': '78646_reglement_20221215.pdf',
  'rules_url': 'https://data.geopf.fr/annexes/gpu/documents/PSMV_78646/124d29d3654b2055efa314153f8965ba/78646_reglement_20221215.pdf'}; documents [PSMV VERSAILLES]
PARCEL {'parcel_id': '78646000AE0181', 'section': 'AE', 'number': '0181', 'commune': 'Versailles', 'area_m2': 450, 'note': 'nearest parcel ...'}
PROTECTIONS servitudes [ac4 Site patrimonial remarquable de Versailles]; prescriptions ['Espace soumis à prescription particulière' (07), 'Périmètre du PSMV' (99)];
  historic_monument_perimeter False, heritage_protected True
RISKS ['Transport de marchandises dangereuses']

GEO {'label': 'Rue de Paris 93100 Montreuil', 'lon': 2.425466, 'lat': 48.856152, 'insee': '93048', 'score': 0.81}
ZONING zone {'code': 'UC91Jb2', 'label': 'Centralite', 'type': 'U', 'partition': 'DU_200057875',
  'rules_url': 'https://data.geopf.fr/annexes/gpu/documents/DU_200057875/0e161f20de055afa3646fd6ae246118a/200057875_reglement_20260223.pdf'}; documents [PLUi EST ENSEMBLE]
PARCEL {'parcel_id': '93048000BH0083', 'section': 'BH', 'area_m2': 277, 'note': 'nearest parcel ...'}
PROTECTIONS servitudes [pm1 PPRmt Montreuil]; prescriptions: OAP (18), mixité sociale (17), 500 m perimeters (04), ...; heritage_protected False
RISKS ['Inondation', 'Transport de marchandises dangereuses']
```

## Step 5 output (trimmed)
```
ingest_plu Versailles -> {'ingested_pages': 117, 'chunks': 170}  (8 s)
search_zone_rules(<versailles rules_url>, 'SB', 'hauteur maximale') -> 6 passages, top: p40 SB "ARTICLE S. B. 8 ...", p39 SB "ARTICLE S. B. 6 ...", p41 SB "sous-secteur SBa ..."
ingest_plu Montreuil -> {'ingested_pages': 635, 'chunks': 1146}  (38 s)
search_zone_rules(<montreuil rules_url>, 'UC91Jb2', 'hauteur maximale') -> p255 UC, p264 UC "d. Hauteur des constructions 3. Fiche d'indices ...", p268 UC
```
(Before fix 3 the Versailles 'SB' search returned p56 SC and p16 S passages.)

## Step 6 output (eval/truth.json)
```
{'id': 1, 'label': '12 Rue de la Paroisse 78000 Versailles', 'zone_code': 'SB', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': True, 'authorisation': 'declaration_prealable'}
{'id': 2, 'label': 'Rue de Paris 93100 Montreuil', 'zone_code': 'UC91Jb2', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': False, 'authorisation': 'declaration_prealable'}
{'id': 3, 'label': '8 Rue du Maréchal Foch 78110 Le Vésinet', 'zone_code': 'UA', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': True, 'authorisation': 'declaration_prealable'}
{'id': 4, 'label': '5 Rue au Pain 78100 Saint-Germain-en-Laye', 'zone_code': None, 'zone_type': None, 'historic_monument_perimeter': False, 'heritage_protected': True, 'authorisation': 'declaration_prealable'}
{'id': 5, 'label': '15 Rue Houdan 92330 Sceaux', 'zone_code': 'U2b', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': True, 'authorisation': 'permis_de_construire'}
{'id': 6, 'label': 'Rue de Fontenay 94300 Vincennes', 'zone_code': 'UA1', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': True, 'authorisation': 'declaration_prealable'}
{'id': 7, 'label': '10 Rue du Général Leclerc 92130 Issy-les-Moulineaux', 'zone_code': 'U1-C-1', 'zone_type': 'U', 'historic_monument_perimeter': True, 'heritage_protected': True, 'authorisation': 'permis_de_construire'}
{'id': 8, 'label': 'Rue de la Roue 92260 Fontenay-aux-Roses', 'zone_code': 'U1a*', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': False, 'authorisation': 'declaration_prealable'}
{'id': 9, 'label': '14 Rue Grande 77300 Fontainebleau', 'zone_code': 'UAf', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': True, 'authorisation': 'declaration_prealable'}
{'id': 10, 'label': '25 Boulevard de la République 78400 Chatou', 'zone_code': 'UV', 'zone_type': 'U', 'historic_monument_perimeter': False, 'heritage_protected': False, 'authorisation': 'declaration_prealable'}
```

## Step 7
Skipped: no ANTHROPIC_API_KEY on this PC. API spend: $0.

## Diff
```diff
diff --git a/app/db.py b/app/db.py
index 126d690..9fa3d2a 100644
--- a/app/db.py
+++ b/app/db.py
@@ -63,13 +63,13 @@ def search_chunks(doc_key: str, query: str, zone: str = "", limit: int = 6) -> l
         if PG:
             rows = c.execute(
                 """SELECT page, zone, text, ts_rank(tsv, q) AS r FROM rule_chunks, websearch_to_tsquery('french', %s) q
-                   WHERE doc_key = %s AND tsv @@ q ORDER BY (zone = %s) DESC, r DESC LIMIT %s""",
-                (" OR ".join(words), doc_key, zone, limit)).fetchall()
+                   WHERE doc_key = %s AND tsv @@ q ORDER BY (zone = %s) DESC, (zone <> '' AND %s LIKE zone || '%%') DESC, r DESC LIMIT %s""",
+                (" OR ".join(words), doc_key, zone, zone, limit)).fetchall()
             return [{"page": r[0], "zone": r[1], "text": r[2]} for r in rows]
         fts = " OR ".join(f'"{w}"' for w in words)
         rows = c.execute(
             """SELECT page, zone, text FROM rule_chunks WHERE rule_chunks MATCH ? AND doc_key = ?
-               ORDER BY (zone = ?) DESC, rank LIMIT ?""", (fts, doc_key, zone, limit)).fetchall()
+               ORDER BY (zone = ?) DESC, (zone <> '' AND ? LIKE zone || '%') DESC, rank LIMIT ?""", (fts, doc_key, zone, zone, limit)).fetchall()
         return [{"page": r["page"], "zone": r["zone"], "text": r["text"]} for r in rows]
 
 
diff --git a/app/tools.py b/app/tools.py
index 813bd40..3b3f38a 100644
--- a/app/tools.py
+++ b/app/tools.py
@@ -50,16 +50,45 @@ def geocode_address(address: str) -> dict:
 
 
 # --- 2. coordinates -> cadastre parcel (IGN API Carto) ---
+def _dist_to_geom(lon: float, lat: float, geom: dict) -> float:
+    """Planar distance (degrees, lon scaled by cos(lat)) from the point to the nearest polygon edge."""
+    import math
+    k = math.cos(math.radians(lat))
+    polys = geom.get("coordinates") or []
+    if geom.get("type") == "Polygon":
+        polys = [polys]
+    best = float("inf")
+    for poly in polys:
+        for ring in poly:
+            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
+                ax, ay, bx, by, px, py = x1 * k, y1, x2 * k, y2, lon * k, lat
+                dx, dy = bx - ax, by - ay
+                t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
+                best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
+    return best
+
+
 def get_parcel(lon: float, lat: float) -> dict:
     data = _get_json(f"{APICARTO}/cadastre/parcelle?geom={_point(lon, lat)}")
     feats = data.get("features") or []
+    nearest = False
+    if not feats:
+        # Address points often sit on the street, outside every parcel: take the nearest parcel within ~20 m.
+        d = 0.0002
+        box = {"type": "Polygon", "coordinates": [[[lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d], [lon - d, lat + d], [lon - d, lat - d]]]}
+        feats = _get_json(f"{APICARTO}/cadastre/parcelle?geom={urllib.parse.quote(json.dumps(box))}").get("features") or []
+        feats.sort(key=lambda f: _dist_to_geom(lon, lat, f.get("geometry") or {}))
+        nearest = True
     if not feats:
         return {"error": "no parcel at this point"}
     f = feats[0]
     p = f["properties"]
-    return {"parcel_id": p.get("idu"), "section": p.get("section"), "number": p.get("numero"),
-            "commune": p.get("nom_com"), "insee": p.get("code_insee"), "area_m2": p.get("contenance"),
-            "geometry": f.get("geometry"), "source": "IGN API Carto, module cadastre"}
+    out = {"parcel_id": p.get("idu"), "section": p.get("section"), "number": p.get("numero"),
+           "commune": p.get("nom_com"), "insee": p.get("code_insee"), "area_m2": p.get("contenance"),
+           "geometry": f.get("geometry"), "source": "IGN API Carto, module cadastre"}
+    if nearest:
+        out["note"] = "The address point is outside any parcel (on the street); this is the nearest parcel. Confirm with the owner's deed."
+    return out
 
 
 # --- 3. coordinates -> PLU zone (Géoportail de l'Urbanisme via API Carto GPU) ---
@@ -74,12 +103,27 @@ def get_zoning(lon: float, lat: float) -> dict:
     zones = _get_json(f"{APICARTO}/gpu/zone-urba?geom={_point(lon, lat)}").get("features") or []
     if not zones:
         out["zone"] = None
-        out["note"] = "No PLU zone here: the commune may be under the national rules (RNU) or a carte communale."
+        try:
+            muni = (_get_json(f"{APICARTO}/gpu/municipality?geom={_point(lon, lat)}").get("features") or [{}])[0].get("properties") or {}
+        except Exception:
+            muni = {}
+        out["is_rnu"] = muni.get("is_rnu")
+        if muni.get("is_rnu"):
+            out["note"] = "The commune is under the national rules (RNU): no PLU applies."
+        elif muni:
+            out["note"] = ("The commune is not RNU but its PLU/carte communale is not published on the Géoportail: "
+                           "get the règlement from the mairie; don't assume national rules only.")
+        else:
+            out["note"] = "No PLU zone here: the commune may be under the national rules (RNU) or a carte communale."
         return out
     p = zones[0]["properties"]
+    rules_url = p.get("urlfic") or None
+    if not rules_url and p.get("nomfic") and p.get("partition") and p.get("gpu_doc_id"):
+        # urlfic is usually empty; the GPU serves the written rules at this path.
+        rules_url = f"https://data.geopf.fr/annexes/gpu/documents/{p['partition']}/{p['gpu_doc_id']}/{p['nomfic']}"
     out["zone"] = {"code": p.get("libelle"), "label": p.get("libelong"), "type": p.get("typezone"),
                    "partition": p.get("partition"), "approved": p.get("datappro"),
-                   "rules_file": p.get("nomfic"), "rules_url": p.get("urlfic")}
+                   "rules_file": p.get("nomfic"), "rules_url": rules_url}
     return out
 
 
@@ -109,6 +153,9 @@ def get_protections(lon: float, lat: float) -> dict:
         except Exception as e:
             out.setdefault("errors", []).append(f"{res}: {e}")
     out["historic_monument_perimeter"] = any(s["type"] == "ac1" for s in out["servitudes"])
+    # Any heritage protection (AC1 monument surroundings, AC2 site, AC4 SPR, PSMV perimeter) makes the ABF review apply.
+    out["heritage_protected"] = out["historic_monument_perimeter"] or any(s["type"] in ("ac2", "ac4") for s in out["servitudes"]) \
+        or any("psmv" in (x.get("label") or "").lower() for x in out["prescriptions"])
     return out
 
 
@@ -123,8 +170,18 @@ def get_risks(lon: float, lat: float) -> dict:
 
 
 # --- 6. PLU rules text: ingest the zone's rules PDF once, then full-text search ---
-ZONE_HEADING = re.compile(r"(?:dispositions\s+applicables\s+(?:à|a|aux)\s+(?:la\s+)?zones?|^\s*zone)\s+([A-Z]{1,3}[A-Za-z0-9\-]{0,5})\b",
+# Zone codes appear plain ("zone UA", "zone 1AUh") or dotted ("ZONE S.B.", "ARTICLE S. B. 6").
+_ZCODE = r"((?:[0-9]?[A-Z](?:\s?\.\s?[A-Z0-9'’]){1,4}\.?)|(?:[0-9]?[A-Z]{1,3}[A-Za-z0-9\-]{0,5}))"
+ZONE_HEADING = re.compile(r"(?:dispositions\s+applicables\s+(?:à|a|aux)\s+(?:la\s+)?(?:zones?|secteurs?)|^\s*zone)\s+" + _ZCODE + r"(?![A-Za-z0-9])",
                           re.IGNORECASE | re.MULTILINE)
+ARTICLE_HEADING = re.compile(r"ARTICLE\s+([0-9]?[A-Z](?:\s?\.?\s?[A-Z0-9]){0,4}?)\s?\.?\s+\d{1,2}\s*[-–:]")
+
+
+_NOT_ZONES = {"URBAINES", "URBAINE", "NATURELLES", "NATURELLE", "AGRICOLES", "AGRICOLE", "URBANISER", "DE", "ET", "LA", "LES"}
+
+
+def _norm_zone(code: str) -> str:
+    return re.sub(r"[\s.'’]", "", code).upper()
 
 
 def ingest_pdf(doc_key: str, url: str, pdf_bytes: bytes | None = None, max_pages: int = 900) -> dict:
@@ -141,9 +198,9 @@ def ingest_pdf(doc_key: str, url: str, pdf_bytes: bytes | None = None, max_pages
         text = (page.extract_text() or "").strip()
         if not text:
             continue
-        m = ZONE_HEADING.search(text[:600])
-        if m:
-            zone = m.group(1).upper()
+        m = ZONE_HEADING.search(text[:600]) or ARTICLE_HEADING.search(text[:400])
+        if m and _norm_zone(m.group(1)) not in _NOT_ZONES:
+            zone = _norm_zone(m.group(1))
         for j in range(0, len(text), 1500):
             chunks.append({"page": i + 1, "zone": zone, "text": text[j:j + 1700]})
     db.add_chunks(doc_key, url, chunks)
diff --git a/scripts/build_truth.py b/scripts/build_truth.py
index 0703ec4..6a8139c 100644
--- a/scripts/build_truth.py
+++ b/scripts/build_truth.py
@@ -20,9 +20,10 @@ for c in cases:
     p = tools.get_protections(g["lon"], g["lat"])
     zone = z.get("zone") or {}
     rule = national_rules.check(c["project_type"], c["area_m2"], c["existing_floor_area_m2"],
-                                zone_type=zone.get("type") or "RNU", has_plu=bool(zone), protected=p["historic_monument_perimeter"])
+                                zone_type=zone.get("type") or "RNU", has_plu=bool(zone) or z.get("is_rnu") is False, protected=p["heritage_protected"])
     t = {"id": c["id"], "label": g["label"], "zone_code": zone.get("code"), "zone_type": zone.get("type"),
-         "historic_monument_perimeter": p["historic_monument_perimeter"], "authorisation": rule["authorisation"]}
+         "historic_monument_perimeter": p["historic_monument_perimeter"],
+         "heritage_protected": p["heritage_protected"], "authorisation": rule["authorisation"]}
     truth.append(t)
     print(t)
 pathlib.Path("eval/truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1))
```

Code with fixes: `~/feuvert` on PC hp (local git, base commit = branch snapshot; `git -C ~/feuvert diff HEAD` shows the change). Not pushed anywhere.

## Live runs with the key (14:14–14:20 Paris)
- The app doesn't load `.env` itself; I started it with `set -a; . ./.env; set +a; uvicorn app.main:app --port 8000`.
- **Run 1 (Montreuil · solar, via POST /api/analyze):** OK in 38 s, 31,243 input / 3,272 output tokens. 10 tool steps: geocode, parcel, zoning, protections, risks, memory, 2× search_zone_rules, memory, thresholds, then submit_report. Verdict: déclaration préalable, CERFA 16702, 1 month, no architect, parcel 93048000BH0083 (flagged as nearest, street-level match), zone UC91Jb2. Constraints quote the PLUi p.79, p.80, p.128 and p.259. It recorded runs/last.json, and `/api/replay` plays it back (25 events).
- **Demo video (Playwright, headless system Chrome, 1920×1080):** a second live run, result after 34.5 s (21,548 / 3,238 tokens). Saved as `pitch/demo-live-run.mp4` (53 s, H.264, yuv420p) plus `pitch/demo-1-trace-mid-run.png`, `demo-2-result-top.png` and `demo-3-result-bottom.png`. Same verdict as run 1. This run is now runs/last.json.
- **eval --n 3:** 2 min 31 s. eval/RESULTS.md:

| Metric | Baseline (one LLM call, no data) | FeuVert agent |
|---|---|---|
| PLU zone correct | 0/3 | 3/3 |
| Historic-monument perimeter correct | 1/3 | 0/3 |
| Authorisation type correct | 3/3 | 3/3 |

  **The 0/3 ABF row is a scoring artefact, not an agent error.** In all 3 cases the truth is AC1 = false. eval.py sets the agent's value to True whenever its report text contains "abf" or "monument(s) historique(s)". The agent always mentions them, even to say "no historic-monument perimeter, no ABF opinion needed" (see the Montreuil report). Versailles and Le Vésinet are SPR/PSMV sites where the ABF *is* required (`heritage_protected: true`). Fix before quoting this row: score against `heritage_protected`, and read the flag from a structured field instead of matching keywords. Otherwise drop the row from the pitch.
- API spend: 2 live runs plus the 3-case eval (3 agent runs + 3 baseline calls), about 8 Opus calls. Probably ~$1–2 in total; I didn't sum the eval's tokens.
