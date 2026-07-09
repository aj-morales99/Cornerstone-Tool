"""
Shared lookup-list store — reads from the Turso (libSQL) lookup_lists table.
No fallback. If the database is unreachable the list will be empty.

Table schema is auto-created on first connect.
"""

import json
import os
import sys

_cache: dict = {}
_client = None


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


def _turso_creds() -> tuple:
    p = _find_config()
    if not p:
        return "", ""
    try:
        with open(p) as f:
            cfg = json.load(f)
        turso = cfg.get("turso", {})
        return turso.get("url", ""), turso.get("auth_token", "")
    except Exception:
        return "", ""


def _get_client():
    global _client
    import libsql_client
    if _client and not _client.closed:
        return _client
    url, token = _turso_creds()
    if not url or not token:
        return None
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://", 1)
    _client = libsql_client.create_client_sync(url=url, auth_token=token)
    return _client


def get_list(list_name: str) -> list:
    """
    Return the named list. Priority:
      1. In-memory cache (populated for this session)
      2. Disk cache written by prefetch_count() at startup
      3. Live Turso fetch (also saves result to disk cache)
    """
    if list_name in _cache:
        return _cache[list_name]

    # Try disk cache — populated by turso_cache at startup
    try:
        import turso_cache
        disk = turso_cache.get()
        lookups = disk.get("lookups", {})
        if list_name in lookups:
            _cache[list_name] = lookups[list_name]
            return _cache[list_name]
    except Exception:
        pass

    # Fall back to live Turso query and persist into disk cache
    values = _fetch(list_name)
    _cache[list_name] = values
    try:
        import turso_cache
        d = turso_cache.get()
        d.setdefault("lookups", {})[list_name] = values
        turso_cache.save(d)
    except Exception:
        pass
    return values


def clear_memory(list_name: str = None) -> None:
    """Clear only the in-memory session cache. Disk cache stays valid."""
    if list_name is None:
        _cache.clear()
    else:
        _cache.pop(list_name, None)


def refresh(list_name: str = None):
    """
    Clear memory cache so the next get_list() re-fetches.
    Also marks the disk cache lookup section as stale so that the
    next get_list() will re-query Turso instead of returning stale disk data.
    """
    if list_name is None:
        _cache.clear()
    else:
        _cache.pop(list_name, None)
    try:
        import turso_cache
        turso_cache.invalidate_lookups()
    except Exception:
        pass


def search(list_name: str, term: str, limit: int = 20) -> list:
    """Live search — returns values containing `term` (case-insensitive)."""
    try:
        client = _get_client()
        if not client:
            return []
        rs = client.execute(
            "SELECT value FROM lookup_lists"
            " WHERE list_name = ? AND active = 1"
            " AND LOWER(value) LIKE ?"
            " ORDER BY sort_order, value LIMIT ?",
            [list_name, f"%{term.lower()}%", limit],
        )
        return [row[0] for row in rs.rows]
    except Exception as e:
        global _client
        _client = None
        print(f"[lookup_store] search '{list_name}' failed: {e}")
        return []


def _fetch(list_name: str) -> list:
    try:
        client = _get_client()
        if not client:
            return []
        rs = client.execute(
            "SELECT value FROM lookup_lists"
            " WHERE list_name = ? AND active = 1"
            " ORDER BY sort_order, value",
            [list_name],
        )
        return [row[0] for row in rs.rows]
    except Exception as e:
        global _client
        _client = None
        print(f"[lookup_store] fetch '{list_name}' failed: {e}")
        return []
