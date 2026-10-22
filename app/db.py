"""Data layer: PLU rule chunks (full-text search) and agent memory.

Postgres (Aiven) when DATABASE_URL is set, else a local SQLite file, same API.
"""
import json
import os
import sqlite3
import time

DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG = DATABASE_URL.startswith("postgres")

if PG:
    import psycopg


def _conn():
    if PG:
        return psycopg.connect(DATABASE_URL, autocommit=True)
    c = sqlite3.connect(os.environ.get("SQLITE_PATH", "feuvert.db"))
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        if PG:
            c.execute("""CREATE TABLE IF NOT EXISTS rule_chunks (
                id SERIAL PRIMARY KEY, doc_key TEXT, source_url TEXT, page INT, zone TEXT, text TEXT,
                tsv tsvector GENERATED ALWAYS AS (to_tsvector('french', text)) STORED)""")
            c.execute("CREATE INDEX IF NOT EXISTS rule_chunks_tsv ON rule_chunks USING GIN (tsv)")
            c.execute("CREATE INDEX IF NOT EXISTS rule_chunks_doc ON rule_chunks (doc_key)")
            c.execute("""CREATE TABLE IF NOT EXISTS memory (
                id SERIAL PRIMARY KEY, key TEXT, kind TEXT, data JSONB, created_at DOUBLE PRECISION)""")
            c.execute("CREATE INDEX IF NOT EXISTS memory_key ON memory (key)")
            c.execute("""CREATE TABLE IF NOT EXISTS api_cache (url TEXT PRIMARY KEY, body TEXT, created_at DOUBLE PRECISION)""")
        else:
            c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS rule_chunks USING fts5(
                doc_key UNINDEXED, source_url UNINDEXED, page UNINDEXED, zone UNINDEXED, text, tokenize='unicode61 remove_diacritics 2')""")
            c.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY, key TEXT, kind TEXT, data TEXT, created_at REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS api_cache (url TEXT PRIMARY KEY, body TEXT, created_at REAL)")


def has_doc(doc_key: str) -> bool:
    with _conn() as c:
        q = "SELECT 1 FROM rule_chunks WHERE doc_key = %s LIMIT 1" if PG else "SELECT 1 FROM rule_chunks WHERE doc_key = ? LIMIT 1"
        return c.execute(q, (doc_key,)).fetchone() is not None


def add_chunks(doc_key: str, source_url: str, chunks: list[dict]):
    with _conn() as c:
        q = ("INSERT INTO rule_chunks (doc_key, source_url, page, zone, text) VALUES (%s,%s,%s,%s,%s)" if PG
             else "INSERT INTO rule_chunks (doc_key, source_url, page, zone, text) VALUES (?,?,?,?,?)")
        for ch in chunks:
            c.execute(q, (doc_key, source_url, ch["page"], ch.get("zone") or "", ch["text"]))


def search_chunks(doc_key: str, query: str, zone: str = "", limit: int = 6) -> list[dict]:
    words = [w for w in "".join(ch if ch.isalnum() else " " for ch in query).split() if len(w) > 2]
    if not words:
        return []
    with _conn() as c:
        if PG:
            rows = c.execute(
                """SELECT page, zone, text, ts_rank(tsv, q) AS r FROM rule_chunks, websearch_to_tsquery('french', %s) q
                   WHERE doc_key = %s AND tsv @@ q ORDER BY (zone = %s) DESC, (zone <> '' AND %s LIKE zone || '%%') DESC, r DESC LIMIT %s""",
                (" OR ".join(words), doc_key, zone, zone, limit)).fetchall()
            return [{"page": r[0], "zone": r[1], "text": r[2]} for r in rows]
        fts = " OR ".join(f'"{w}"' for w in words)
        rows = c.execute(
            """SELECT page, zone, text FROM rule_chunks WHERE rule_chunks MATCH ? AND doc_key = ?
               ORDER BY (zone = ?) DESC, (zone <> '' AND ? LIKE zone || '%') DESC, rank LIMIT ?""", (fts, doc_key, zone, zone, limit)).fetchall()
        return [{"page": r["page"], "zone": r["zone"], "text": r["text"]} for r in rows]


def count_chunks() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT doc_key, COUNT(*) FROM rule_chunks GROUP BY doc_key").fetchall()
        return {r[0]: r[1] for r in rows}


def remember(key: str, kind: str, data: dict):
    with _conn() as c:
        q = ("INSERT INTO memory (key, kind, data, created_at) VALUES (%s,%s,%s,%s)" if PG
             else "INSERT INTO memory (key, kind, data, created_at) VALUES (?,?,?,?)")
        c.execute(q, (key, kind, json.dumps(data, ensure_ascii=False), time.time()))


def recall(key: str, limit: int = 5) -> list[dict]:
    with _conn() as c:
        q = ("SELECT kind, data, created_at FROM memory WHERE key = %s ORDER BY created_at DESC LIMIT %s" if PG
             else "SELECT kind, data, created_at FROM memory WHERE key = ? ORDER BY created_at DESC LIMIT ?")
        rows = c.execute(q, (key, limit)).fetchall()
        out = []
        for r in rows:
            data = r[1] if isinstance(r[1], dict) else json.loads(r[1])
            out.append({"kind": r[0], "data": data, "at": time.strftime("%Y-%m-%d %H:%M", time.localtime(r[2]))})
        return out


def cache_get(url: str, max_age_s: float = 7 * 86400):
    with _conn() as c:
        q = "SELECT body, created_at FROM api_cache WHERE url = %s" if PG else "SELECT body, created_at FROM api_cache WHERE url = ?"
        r = c.execute(q, (url,)).fetchone()
        if r and time.time() - r[1] < max_age_s:
            return r[0]
    return None


def cache_put(url: str, body: str):
    with _conn() as c:
        if PG:
            c.execute("INSERT INTO api_cache (url, body, created_at) VALUES (%s,%s,%s) ON CONFLICT (url) DO UPDATE SET body = EXCLUDED.body, created_at = EXCLUDED.created_at",
                      (url, body, time.time()))
        else:
            c.execute("INSERT OR REPLACE INTO api_cache (url, body, created_at) VALUES (?,?,?)", (url, body, time.time()))


def stats() -> dict:
    with _conn() as c:
        out = {"backend": "postgres" if PG else "sqlite"}
        for t in ("rule_chunks", "memory", "api_cache"):
            out[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return out
