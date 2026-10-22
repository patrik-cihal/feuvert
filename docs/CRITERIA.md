# Judging criteria

Source: the organiser's slide, photographed 2026-10-22 (four photos, two of the criteria slide). Text is verbatim
where readable. Criterion 05 is **Execution & pitch** (Patrik, from the room); the start of its question was hidden in the
photos, it ends "…point of difference and a credible route to first users?". The organisers said on stage that
pitching and explaining clearly what it is is very valuable. The organiser mail adds "product thinking, design and
a credible route to first users all count".

No weights were shown; assume equal until told otherwise.

---

## 01 · Customer problem & product value
> Is it a real problem for a clear user, and would they adopt the product?

What scores:
- One named user type, narrow enough to picture ("indie game devs on Steam with 1–3 games", not "businesses").
- The problem in their words, with a cost (hours a week, money lost, a missed chance).
- Proof of adoption: you are the user, or you talked to one today, or someone at the hackathon tried it.

## 02 · Agent capability
> Does it show advanced agent behaviour, such as multi-step reasoning, autonomy, teamwork or learning, beyond a
> single LLM call?

What scores:
- A visible loop: plan → call tools / query data → check result → act again. Show the trace on screen.
- At least one of: acts on its own on a trigger (autonomy), several agents with roles (teamwork), gets better
  from past runs (learning). Learning is the rarest and fits 03 too.
- Not a chat box over one prompt.

## 03 · Data at the core
> Does the product depend on using data well (freshness, scale, grounding, memory), or is the data just decoration?

What scores:
- Remove the data and the product is useless. Say that sentence in the pitch.
- Hit the four words on the slide on purpose: **freshness** (live / event stream), **scale** (real volume, a
  number of rows), **grounding** (answers cite the rows they came from), **memory** (it remembers past runs).
- Use the sponsor's stack (Aiven: PostgreSQL, ClickHouse, Valkey, OpenSearch) and deploy on Aiven Runtime. The
  submission item "the data layer in action" exists to show this.

## 04 · Evidence it works
> Is there a measurable result, such as accuracy, cost, latency, success rate or time saved?

What scores:
- A number with a baseline: "single LLM call: 41% correct → our agent with data: 83% on 50 held-out cases".
- The baseline is the "before" in the submission's "before and after / comparison benchmarks".
- Build the eval set early (by midday), not at the end. Small and honest beats large and vague.

## 05 · Execution & pitch
> "… point of difference and a credible route to first users?"

The organisers stressed this one out loud: pitching and explaining what it is counts a lot.

What scores:
- A judge can repeat what it is after 15 seconds. One sentence: who it's for, what it does, why it needs data.
- A rehearsed 3 minutes that lands on time (practise it out loud at least twice).
- It works live, deployed, on a URL the judges can open. Polished enough that nothing breaks in the demo.
- One clear "why us / why not ChatGPT": the data you have that others don't, or the loop nobody else closes.
- Named first users and the channel to them (a community you're in, a list, your own product's users).
