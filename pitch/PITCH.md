# Pitch: FeuVert

## Name and one-liner
**FeuVert.** For renovation and solar installers (and homeowners) who need town-hall approval, FeuVert is an agent that reads
the parcel, the zoning and the local plan for any French address and prepares the right file, so it doesn't get bounced.

## One pitch slide
1. **Problem:** about 1.35M permit / declaration files a year in France; about 35% get a request for missing documents, which
   restarts the review clock. Consultants charge €250–2,000 a file. Rules just changed again (decree of 2026-07-27).
2. **Product:** address + project → parcel, zone, protections, the zone's own rules, national thresholds → which form, what
   limits apply, what will get it rejected, documents to attach, draft note. Every claim cites its source.
3. **Why data:** free official sources (cadastre, Géoportail de l'Urbanisme, Géorisques, each commune's PLU text) indexed in
   Postgres, plus memory of every past case per parcel and commune. Without it, an LLM guesses the zone.
4. **Proof:** baseline (one LLM call) vs agent on N addresses: zone correct _/N → _/N; protection detected _/N → _/N;
   authorisation correct _/N → _/N (fill from eval/RESULTS.md).
5. **First users:** solar and heat-pump installers file a déclaration for nearly every client; start with installer networks
   in Île-de-France. Accel backed this model in the US (PermitFlow, $54M Series B, Dec 2025); France's human-led player went
   into receivership in 2023.

## 3-minute demo script
| Time | Show |
|---|---|
| 0:00–0:20 | "I want a 25 m² extension in Versailles. Declaration or permit? What's allowed?" One in three files gets bounced. |
| 0:20–1:40 | Live run: pin drops, parcel outlined, zone found, historic-monument perimeter detected, agent reads the PLU article on height, applies thresholds, returns the card with sources |
| 1:40–2:10 | Data layer: header counts (PLU passages, memories, cached answers); second run on the same parcel recalls memory |
| 2:10–2:40 | Before / after table from eval/RESULTS.md |
| 2:40–3:00 | Installers as first users, PermitFlow/Accel proof, France then Europe |
