# CLAUDE.md

Hackathon repo for **Accel AI Innovate, Paris, 2026-10-22** (one day, 08:00–20:00). Patrik builds here, with Claude.

Read `README.md` and `docs/CRITERIA.md` first. Every decision is judged against the five criteria; when choosing
what to build next, pick what moves a criterion the judges will see in the 3-minute demo.

## Rules

- **Patrik decides** the idea, the scope and the cuts. Lay out options and trade-offs; build what he picks.
- **Demo first.** Keep `main` demoable at all times; commit small and often. Polish only the demo path.
- **Evidence early.** The eval set and baseline exist before the agent is tuned; results go in `docs/RESULTS.md`
  with the number of cases and how they were picked. Never inflate or fabricate a benchmark.
- **Data layer on Aiven** (sponsor): PostgreSQL / ClickHouse / Valkey / OpenSearch, app deployed on Aiven Runtime.
- **Money:** hackathon credits (Anthropic, OpenAI, Modal, Vercel, ElevenLabs, Supabase, Aiven) are free to use.
  Anything charged to Patrik's own cards over ~$5 needs his yes first, with the plan and the expected cost.
- **Secrets:** API keys in `.env` (git-ignored), never committed.
- Dates `YYYY-MM-DD`, times Paris.
