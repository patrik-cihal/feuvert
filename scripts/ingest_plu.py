"""Pre-index a commune's PLU rules PDF before the demo (so the live run doesn't wait on a big download).

Usage:
  python -m scripts.ingest_plu "12 rue de la Paroisse, 78000 Versailles"   # finds the zone's rules PDF via the Géoportail
  python -m scripts.ingest_plu --url https://.../reglement.pdf
  python -m scripts.ingest_plu --file reglement.pdf --key <rules_url the agent will see>
"""
import argparse
import pathlib

from app import db, tools

ap = argparse.ArgumentParser()
ap.add_argument("address", nargs="?")
ap.add_argument("--url")
ap.add_argument("--file")
ap.add_argument("--key")
a = ap.parse_args()
db.init()

url = a.url
if a.address and not url:
    g = tools.geocode_address(a.address)
    print("geocode:", g)
    z = tools.get_zoning(g["lon"], g["lat"])
    print("zoning:", z)
    url = (z.get("zone") or {}).get("rules_url")
    if not url:
        raise SystemExit("No rules_url on the Géoportail for this zone. Download the règlement PDF from the commune and use --file.")
key = a.key or url
if db.has_doc(key):
    raise SystemExit(f"already indexed: {key}")
data = pathlib.Path(a.file).read_bytes() if a.file else None
print(tools.ingest_pdf(key, url or key, pdf_bytes=data))
print(db.stats())
