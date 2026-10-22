# FeuVert: your green light from the town hall

**For solar and renovation installers in France.** Give FeuVert a client's address and the job (e.g. "18 m² of solar
panels on the roof"). An AI agent finds the plot, its planning zone and protections in free government data, reads
that town's own planning rules, applies the national thresholds, and tells you which file to submit to the town hall
(déclaration préalable or permis de construire), which form, the review time, every constraint with its source, the
documents to attach and a draft note to the mairie.

Built in one day at Accel AI Innovate, Paris, 2026-10-22.

- **Live app:** https://feuvert-paris.fly.dev (live runs call Claude; each takes 30–60 s)
- **Recorded live run (no API call):** https://feuvert-paris.fly.dev/?replay
- **Demo video:** [`pitch/demo-live-run.mp4`](pitch/demo-live-run.mp4) · **Pitch slide:** [`pitch/feuvert-pitch-slide.png`](pitch/feuvert-pitch-slide.png)

## Why

About 1 in 3 French permit and declaration files comes back incomplete, which restarts the review clock. Installers
file one for nearly every solar job, by hand or through consultants (€250–2,000 a file). A general chatbot can explain
the rules, but it doesn't know which zone a specific plot is in, whether it sits in a heritage or flood-risk area, or
what that town's own rules say.

## How it works

```
address + job
  └─ agent (Claude Opus 5.5, tool use) decides which source to query next:
       geocode_address      Base Adresse Nationale (data.geopf.fr)
       get_parcel           cadastre plot + area (IGN API Carto)
       get_zoning           planning zone, plan type, link to the town's rules PDF (Géoportail de l'Urbanisme)
       get_protections      heritage / historic-monument / risk-plan easements and plan prescriptions
       get_risks            Géorisques
       recall_memory        past analyses of this plot / town
       search_zone_rules    full-text search in that zone's rules (PDF downloaded and indexed on first use)
       check_national_thresholds   Code de l'urbanisme: DP vs PC, form, review time, architect
  └─ submit_report: authorisation, form, timeline, constraints (each with its source), documents, next steps
```

Data layer (`app/db.py`): SQLite locally and in the live demo, PostgreSQL when `DATABASE_URL` is set.
- `rule_chunks`: each town's rules split into zone-tagged passages with a full-text index (1,316 passages in the demo:
  Versailles PSMV 117 pages, Montreuil PLUi 635 pages)
- `api_cache`: every government answer, so repeat lookups are instant
- `memory`: every analysis stored per plot and per town and recalled on the next run

## Results (3 live runs, 2026-10-22)

| Metric | One Claude call, no data | FeuVert agent |
|---|---|---|
| Zone of the plot correct | 0/3 | 3/3 |
| Authorisation type correct | 3/3 | 3/3 |

Ground truth comes from the Géoportail de l'Urbanisme (`scripts/build_truth.py`), not from a model. Small sample;
details in [`eval/RESULTS.md`](eval/RESULTS.md). Ignore the "historic-monument perimeter" row there: its keyword
scoring was too crude to mean anything.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # set ANTHROPIC_API_KEY; optional DATABASE_URL (PostgreSQL), else SQLite
set -a; source .env; set +a
python -m tests.test_smoke        # offline test, no API calls
uvicorn app.main:app --reload     # http://localhost:8000
```

Optional: pre-index a town's rules so the first run is fast:
`python -m scripts.ingest_plu "20 rue de Paris, 93100 Montreuil"`.
Benchmark: `python -m scripts.build_truth && python -m scripts.eval --n 3` (costs a few dollars of API usage).
Deploy: the `Dockerfile` runs `uvicorn app.main:app` on `$PORT` (the live demo runs on Fly.io).

## Limitations (honest list)

- When the address point falls on the street, it uses the nearest plot and says so.
- Some towns publish their rules as a zip or don't publish them at all; the agent then says it couldn't read them.
- National thresholds and CERFA numbers were checked against notary and town-hall guides, not legal advice.
- Learning from town-hall outcomes (accepted / bounced / which document was requested) is the next step; today the
  memory stores past analyses per plot and town.
- No login or rate limit: it's a hackathon demo.

## Repo map

- `app/agent.py`: the tool-use loop, streams every step to the UI
- `app/tools.py`: government data clients, rules indexing and search, memory
- `app/national_rules.py`: Code de l'urbanisme thresholds
- `static/index.html`: UI (map, live agent trace, result card, replay mode)
- `scripts/`: rules ingestion, ground truth, benchmark · `eval/`: cases, truth, results · `pitch/`: slide, demo video, screenshots
- `docs/`: hackathon brief and judging criteria
