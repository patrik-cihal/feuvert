# Eval results

3 cases (eval/cases.json), truth from the Géoportail de l'Urbanisme (scripts/build_truth.py), model claude-opus-5-5.

| Metric | Baseline (one LLM call, no data) | FeuVert agent |
|---|---|---|
| PLU zone correct | 0/3 | 3/3 |
| Historic-monument perimeter correct | 1/3 | 0/3 |
| Authorisation type correct | 3/3 | 3/3 |

```
[
 {
  "id": 1,
  "baseline": {
   "zone": false,
   "abf": false,
   "auth": true
  },
  "baseline_raw": {
   "zone_code": "UA",
   "historic_monument_perimeter": true,
   "authorisation": "declaration_prealable"
  },
  "agent": {
   "zone": true,
   "abf": false,
   "auth": true
  },
  "agent_raw": {
   "zone_code": "SB – PSMV de Versailles",
   "authorisation": "declaration_prealable",
   "historic_monument_perimeter": true
  },
  "agent_s": 60.1
 },
 {
  "id": 2,
  "baseline": {
   "zone": false,
   "abf": true,
   "auth": true
  },
  "baseline_raw": {
   "zone_code": "UM",
   "historic_monument_perimeter": false,
   "authorisation": "declaration_prealable"
  },
  "agent": {
   "zone": true,
   "abf": false,
   "auth": true
  },
  "agent_raw": {
   "zone_code": "UC91Jb2 – Centralité (zone U), PLUi Est Ensemble",
   "authorisation": "declaration_prealable",
   "historic_monument_perimeter": true
  },
  "agent_s": 31.3
 },
 {
  "id": 3,
  "baseline": {
   "zone": false,
   "abf": false,
   "auth": true
  },
  "baseline_raw": {
   "zone_code": "UG",
   "historic_monument_perimeter": true,
   "authorisation": "declaration_prealable"
  },
  "agent": {
   "zone": true,
   "abf": false,
   "auth": true
  },
  "agent_raw": {
   "zone_code": "UA – Secteur de centralité dense (PLU Le Vésinet); not confirmed",
   "authorisation": "declaration_prealable",
   "historic_monument_perimeter": true
  },
  "agent_s": 37.8
 }
]
```
