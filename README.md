# FeuVert: your green light from the town hall

An agent that prepares French building authorisations. Give it an address and a project; it finds the cadastre parcel,
the PLU zone and protections (free government APIs), reads the zone's rules in the town's PLU, applies the national
thresholds, and returns which file you need (déclaration préalable / permis de construire), the CERFA, the review time,
every constraint with its source, the documents to attach, and a draft note to the mairie.
Built at Accel AI Innovate, Paris, 2026-10-22.

## Run it (5 minutes)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # put ANTHROPIC_API_KEY (hackathon credits); DATABASE_URL = Aiven Postgres URI, or leave empty for SQLite
set -a; source .env; set +a
python -m tests.test_smoke      # offline check, no API calls
uvicorn app.main:app --reload   # http://localhost:8000
```

**First 5 minutes on the venue Wi-Fi:** check the public APIs answer:
```bash
python -c "from app import tools,db; db.init(); g=tools.geocode_address('12 rue de la Paroisse, Versailles'); print(g); print(tools.get_zoning(g['lon'],g['lat']))"
```
If `get_zoning` returns a zone with a `rules_url`, pre-index that PLU before the demo (big PDFs take a minute):
`python -m scripts.ingest_plu "12 rue de la Paroisse, 78000 Versailles"`

## Demo safety net
Every successful run is saved to `runs/last.json`. If the venue network is slow, open `http://localhost:8000/?replay` and
click the button: it plays the last real run back with the same live trace, map and result card.

## Data layer (Aiven)
- **PostgreSQL** (`DATABASE_URL`): `rule_chunks` (PLU text per page and zone, French full-text index), `memory` (past analyses per
  parcel and commune; the agent recalls them), `api_cache` (every public-API answer, so repeat runs are instant).
- `GET /api/stats` shows the counts; the header of the UI shows them live.

## Evidence (before / after)
```bash
python -m scripts.build_truth   # ground truth from the official Géoportail (no model involved)
python -m scripts.eval          # baseline = one Claude call with no data, vs the agent; writes eval/RESULTS.md (~$3-5 of credits)
```
Spot-check 2-3 truth rows on https://www.geoportail-urbanisme.gouv.fr/map/ before quoting the numbers.

## Deploy
`Dockerfile` runs `uvicorn app.main:app` on `$PORT`. Set `ANTHROPIC_API_KEY` and `DATABASE_URL`.

## Code
- `app/agent.py`: tool-use loop (Claude Opus 5.5, adaptive thinking), streams every step
- `app/tools.py`: Base Adresse Nationale, IGN API Carto (cadastre, GPU zones, servitudes, prescriptions), Géorisques, PLU PDF indexing and search, memory
- `app/national_rules.py`: Code de l'urbanisme thresholds (DP / PC / architect / review time / CERFA)
- `app/db.py`: Postgres or SQLite
- `static/index.html`: the UI (map, live agent trace, result card)

---

# Hackathon notes: Accel AI Innovate, Paris

Thursday 2026-10-22, 08:00–20:00, Metafore Boétie (St Augustin), 5 rue La Boétie, Paris.
Run by Accel × Iterate on BuilderBase. Sponsor for infra: **Aiven**. Patrik entered solo, open to a team.

- [`docs/CRITERIA.md`](docs/CRITERIA.md): the five judging criteria, word for word, and what scores on each
- [`docs/SUBMISSION.md`](docs/SUBMISSION.md): the five submission items and a checklist
- [`docs/PLAN.md`](docs/PLAN.md): how to win: time plan, what judges need to see, idea options scored
- [`pitch/`](pitch/): one-liner, 3-minute demo script, one pitch slide (fill in once the idea is picked)
- [`CLAUDE.md`](CLAUDE.md): rules for Claude sessions building here

## The challenge (organiser mail, 2026-10-21)

> Build a working product where one or more agents depend on data to deliver value for a specific user. That
> could mean querying large datasets, reacting to event streams, keeping long-term memory, combining many sources
> or improving over time from past runs. You choose the customer and the problem.
>
> Use any models, frameworks and tools you like. Deploy your app to our sponsor Aiven's Runtime, and use their
> managed data infrastructure for your data layer where relevant (PostgreSQL, ClickHouse, Valkey, OpenSearch and
> more) with free credits for every team. Strong teams need more than code. Product thinking, design and a credible
> route to first users all count.

## Judging criteria (slide, transcribed from photos)

| # | Criterion | Question on the slide |
|---|---|---|
| 01 | **Customer problem & product value** | Is it a real problem for a clear user, and would they adopt the product? |
| 02 | **Agent capability** | Does it show advanced agent behaviour, such as multi-step reasoning, autonomy, teamwork or learning, beyond a single LLM call? |
| 03 | **Data at the core** | Does the product depend on using data well (freshness, scale, grounding, memory), or is the data just decoration? |
| 04 | **Evidence it works** | Is there a measurable result, such as accuracy, cost, latency, success rate or time saved? |
| 05 | **Execution & pitch** | "… point of difference and a credible route to first users?" (start of the line hidden in the photo) |

Organisers said on stage: **pitching and explaining clearly what it is is very valuable.**

## Submission (slide, transcribed from photos)

1. Project name and one-line pitch
2. 3 minute demo
3. The data layer in action
4. Before and after / comparison benchmarks
5. One pitch slide

The small button labels under each item (format: URL / video / file) were unreadable in the photos. Check them on
the BuilderBase challenge page.

## Credits on the day

Anthropic $100 / person · OpenAI $50 / person · Modal $100 / person · Vercel $120 AI Gateway / person ·
ElevenLabs 110k credits / person · Supabase $25 / person · Lovable credits · n8n Cloud Pro 1 month ·
Lightdash Cloud Pro 1 month / team · Miro enterprise 1 month · Aiven credits per team.

Side event: 18:00 fireside with Mati Staniszewski (ElevenLabs CEO), separate Luma sign-up: https://luma.com/kbh75rj8
