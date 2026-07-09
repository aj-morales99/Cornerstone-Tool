"""
Shared lookup-list store — always reads from the Supabase lookup_lists table.
No fallback. If the database is unreachable the list will be empty.

Table schema (run once in Supabase SQL editor):

    CREATE TABLE IF NOT EXISTS lookup_lists (
        list_name   TEXT    NOT NULL,
        value       TEXT    NOT NULL,
        active      BOOLEAN NOT NULL DEFAULT TRUE,
        sort_order  INT     NOT NULL DEFAULT 0,
        PRIMARY KEY (list_name, value)
    );

Manage values directly in the Supabase table editor.
Set active = false to hide a value without deleting it.
sort_order controls display order within the list (ascending).
"""

import json
import os
import sys

_cache: dict = {}
_db_url: str = ""
_conn = None  # persistent connection — reused across all queries


def _find_config() -> str:
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(os.path.join(meipass, "cv_config.json"))
    root = os.path.dirname(os.path.abspath(__file__))
    candidates += [
        os.path.join(root, "cv_parse_format", "cv_config.json"),
        os.path.join(root, "cv_config.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def _get_db_url() -> str:
    global _db_url
    if _db_url:
        return _db_url
    p = _find_config()
    if not p:
        return ""
    try:
        with open(p) as f:
            cfg = json.load(f)
        _db_url = cfg.get("postgres", {}).get("database_url", "")
    except Exception:
        pass
    return _db_url


def get_list(list_name: str) -> list:
    """Return the named list from Supabase. Cached for the session."""
    if list_name in _cache:
        return _cache[list_name]
    values = _fetch(list_name)
    _cache[list_name] = values
    return values


def refresh(list_name: str = None):
    """Clear cache so the next get_list() re-fetches from Supabase."""
    if list_name is None:
        _cache.clear()
    else:
        _cache.pop(list_name, None)


def _get_conn():
    """Return a persistent connection, reconnecting if dropped."""
    global _conn
    import psycopg2
    try:
        if _conn and not _conn.closed:
            _conn.cursor().execute("SELECT 1")
            return _conn
    except Exception:
        _conn = None
    url = _get_db_url()
    if not url:
        return None
    if "sslmode" not in url:
        url = url + ("&" if "?" in url else "?") + "sslmode=require"
    _conn = psycopg2.connect(url, connect_timeout=20)
    _conn.autocommit = True
    return _conn


def search(list_name: str, term: str, limit: int = 20) -> list:
    """Live search — returns values containing `term` (case-insensitive)."""
    try:
        conn = _get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM lookup_lists "
                "WHERE list_name = %s AND active = TRUE AND value ILIKE %s "
                "ORDER BY sort_order, value LIMIT %s",
                (list_name, f"%{term}%", limit),
            )
            return [r[0] for r in cur.fetchall()]
    except Exception as e:
        global _conn
        _conn = None
        print(f"[lookup_store] search '{list_name}' failed: {e}")
        return []


def _fetch(list_name: str) -> list:
    try:
        conn = _get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute(
                "SELECT value FROM lookup_lists "
                "WHERE list_name = %s AND active = TRUE "
                "ORDER BY sort_order, value",
                (list_name,),
            )
            return [r[0] for r in cur.fetchall()]
    except Exception as e:
        global _conn
        _conn = None
        print(f"[lookup_store] fetch '{list_name}' failed: {e}")
        return []
