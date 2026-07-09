"""
Local disk cache for Turso data.

Stores the lookup lists and the first profile page to disk so the app only
queries Turso when something has actually changed.

Cache file:
  Windows: %APPDATA%\CPS Tools\turso_cache.json
  macOS:   ~/Library/Application Support/CPS Tools/turso_cache.json
Format:
{
  "profile_count":  <int>,
  "lookup_count":   <int>,
  "profiles_page1": [<profile-summary>, ...],   # first 10 profiles
  "lookups": {
    "<list_name>": [<value>, ...]
  }
}

Boot strategy (called from prefetch_count):
  1.  Read table_stats for both counts  →  2 row-reads
  2a. If profile count changed → fetch 10 rows, update cache
  2b. If lookup count changed  → fetch all lookup rows, update cache
  3.  Write cache to disk

On a quiet boot (nothing changed): 2 row-reads total, zero data rows.
"""

import json
import os
import sys
import threading


def _cache_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "CPS Tools")
    elif sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"),
                            "Library", "Application Support", "CPS Tools")
    else:
        return os.path.join(os.path.expanduser("~"), ".cpstools")


_CACHE_DIR  = _cache_dir()
_CACHE_FILE = os.path.join(_CACHE_DIR, "turso_cache.json")
_lock       = threading.Lock()
_mem: dict  = {}


def load() -> dict:
    """Read the cache from disk into memory. Returns the cache dict (may be {})."""
    global _mem
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            _mem = json.load(f)
    except Exception:
        _mem = {}
    return _mem


def save(data: dict) -> None:
    """Write data to disk and keep the in-memory copy in sync."""
    global _mem
    _mem = data
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with _lock:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def get() -> dict:
    """Return the in-memory cache (loading from disk on first call)."""
    if not _mem:
        return load()
    return _mem


def invalidate_lookups() -> None:
    """Remove the lookup section from the cache so the next sync re-fetches it."""
    d = get().copy()
    d.pop("lookups", None)
    d.pop("lookup_count", None)
    save(d)
