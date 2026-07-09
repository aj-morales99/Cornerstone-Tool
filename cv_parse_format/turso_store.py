"""
Turso (libSQL/SQLite) data store for CPS Tools — primary backend.
Uses the Turso Hrana v2 HTTP API directly via requests — no libsql-client
needed, which avoids PyInstaller SSL-certificate bundling issues with httpx.
"""

import json
from datetime import datetime
import requests as _requests


# ── Minimal Hrana v2 HTTP client ──────────────────────────────────────────────

class _Result:
    __slots__ = ("rows",)
    def __init__(self, rows):
        self.rows = rows


class _TursoHTTPClient:
    """
    Sends SQL to Turso via POST /v2/pipeline (Hrana v2).
    Provides the same execute() / batch() interface that TursoStore calls.
    """
    closed = False

    def __init__(self, url: str, auth_token: str):
        self._endpoint = url.rstrip("/") + "/v2/pipeline"
        self._headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _enc(v):
        if v is None:
            return {"type": "null"}
        if isinstance(v, bool):
            return {"type": "integer", "value": "1" if v else "0"}
        if isinstance(v, int):
            return {"type": "integer", "value": str(v)}
        if isinstance(v, float):
            return {"type": "real", "value": str(v)}
        return {"type": "text", "value": str(v)}

    @staticmethod
    def _dec(v):
        if not isinstance(v, dict):
            return v
        t = v.get("type")
        if t == "null":
            return None
        val = v.get("value")
        if t == "integer":
            return int(val)
        if t == "real":
            return float(val)
        return val  # text / blob

    def _post(self, reqs: list) -> dict:
        resp = _requests.post(
            self._endpoint,
            headers=self._headers,
            json={"baton": None, "requests": reqs},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def execute(self, sql: str, args=None) -> _Result:
        stmt = {"sql": sql}
        if args:
            stmt["args"] = [self._enc(a) for a in args]
        data = self._post([{"type": "execute", "stmt": stmt}, {"type": "close"}])
        res = data["results"][0]
        if res.get("type") == "error":
            raise Exception(res.get("error", {}).get("message", "SQL error"))
        rows_raw = res["response"]["result"]["rows"]
        return _Result([tuple(self._dec(v) for v in row) for row in rows_raw])

    def batch(self, stmts) -> None:
        reqs = [
            {"type": "execute", "stmt": ({"sql": s} if isinstance(s, str) else s)}
            for s in stmts
        ]
        reqs.append({"type": "close"})
        data = self._post(reqs)
        for r in data.get("results", []):
            if r.get("type") == "error":
                raise Exception(r.get("error", {}).get("message", "batch SQL error"))


_CV_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS cv_profiles ("
    "profile_id      TEXT PRIMARY KEY,"
    "name            TEXT,"
    "job_title       TEXT,"
    "email           TEXT,"
    "phone           TEXT,"
    "linkedin_url    TEXT,"
    "county          TEXT,"
    "current_salary  TEXT,"
    "expected_salary TEXT,"
    "parsed_date     TEXT,"
    "raw_cv_link     TEXT DEFAULT '',"
    "profile_json    TEXT,"
    "cv_json         TEXT,"
    "file_hash       TEXT"
    ")"
)

_LOOKUP_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS lookup_lists ("
    "list_name   TEXT    NOT NULL,"
    "value       TEXT    NOT NULL,"
    "active      INTEGER NOT NULL DEFAULT 1,"
    "sort_order  INTEGER NOT NULL DEFAULT 0,"
    "PRIMARY KEY (list_name, value)"
    ")"
)

# Tracker table: keeps a running total so COUNT(*) is never needed for the full list
_STATS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS table_stats ("
    "table_name TEXT PRIMARY KEY,"
    "total_count INTEGER NOT NULL DEFAULT 0"
    ")"
)

# Indexes on lowercased name/job_title — used by all LOWER(x) LIKE ? search queries
_IDX_NAME    = "CREATE INDEX IF NOT EXISTS idx_cv_name      ON cv_profiles(LOWER(name))"
_IDX_JOB     = "CREATE INDEX IF NOT EXISTS idx_cv_job_title ON cv_profiles(LOWER(job_title))"

# Triggers keep table_stats in sync automatically — fired only on genuine INSERT/DELETE
_TRIGGER_INSERT = (
    "CREATE TRIGGER IF NOT EXISTS trg_profile_insert"
    " AFTER INSERT ON cv_profiles BEGIN"
    "  UPDATE table_stats SET total_count = total_count + 1"
    "  WHERE table_name = 'cv_profiles';"
    " END"
)
_TRIGGER_DELETE = (
    "CREATE TRIGGER IF NOT EXISTS trg_profile_delete"
    " AFTER DELETE ON cv_profiles BEGIN"
    "  UPDATE table_stats SET total_count = total_count - 1"
    "  WHERE table_name = 'cv_profiles';"
    " END"
)
_TRIGGER_LOOKUP_INSERT = (
    "CREATE TRIGGER IF NOT EXISTS trg_lookup_insert"
    " AFTER INSERT ON lookup_lists BEGIN"
    "  UPDATE table_stats SET total_count = total_count + 1"
    "  WHERE table_name = 'lookup_lists';"
    " END"
)
_TRIGGER_LOOKUP_DELETE = (
    "CREATE TRIGGER IF NOT EXISTS trg_lookup_delete"
    " AFTER DELETE ON lookup_lists BEGIN"
    "  UPDATE table_stats SET total_count = total_count - 1"
    "  WHERE table_name = 'lookup_lists';"
    " END"
)

# Column order for SELECT * FROM cv_profiles (matches CREATE TABLE above)
_C = {
    "profile_id": 0, "name": 1, "job_title": 2, "email": 3, "phone": 4,
    "linkedin_url": 5, "county": 6, "current_salary": 7, "expected_salary": 8,
    "parsed_date": 9, "raw_cv_link": 10, "profile_json": 11, "cv_json": 12,
    "file_hash": 13,
}


def _to_https(url: str) -> str:
    return url.replace("libsql://", "https://", 1) if url.startswith("libsql://") else url


class TursoStore:
    def __init__(self, url: str, auth_token: str):
        self._url = _to_https(url)
        self._auth_token = auth_token
        self._client = None

    def _get_client(self):
        if self._client is None or self._client.closed:
            self._client = _TursoHTTPClient(self._url, self._auth_token)
        return self._client

    def is_available(self) -> bool:
        """
        Creates all tables, indexes, triggers, and seeds the stats row if missing.
        Everything is sent in a single HTTP batch (one round trip).
        """
        try:
            client = self._get_client()
            client.batch([
                _CV_SCHEMA,
                _LOOKUP_SCHEMA,
                _STATS_SCHEMA,
                _IDX_NAME,
                _IDX_JOB,
                _TRIGGER_INSERT,
                _TRIGGER_DELETE,
                _TRIGGER_LOOKUP_INSERT,
                _TRIGGER_LOOKUP_DELETE,
                # Seed both trackers once — INSERT OR IGNORE keeps them unchanged on subsequent calls
                "INSERT OR IGNORE INTO table_stats (table_name, total_count)"
                " VALUES ('cv_profiles', (SELECT COUNT(*) FROM cv_profiles))",
                "INSERT OR IGNORE INTO table_stats (table_name, total_count)"
                " VALUES ('lookup_lists', (SELECT COUNT(*) FROM lookup_lists WHERE active = 1))",
                "SELECT 1",
            ])
            return True
        except Exception:
            self._client = None
            return False

    def count_profiles(self, search="") -> int:
        client = self._get_client()
        if not search:
            # Fast path: 1 row read regardless of how many candidates exist
            rs = client.execute(
                "SELECT total_count FROM table_stats WHERE table_name = 'cv_profiles'"
            )
            if rs.rows:
                return int(rs.rows[0][0])
        # Filtered search — uses the idx_cv_name / idx_cv_job_title indexes
        s = f"%{search.lower()}%"
        rs = client.execute(
            "SELECT COUNT(*) FROM cv_profiles"
            " WHERE LOWER(name) LIKE ? OR LOWER(job_title) LIKE ?",
            [s, s],
        )
        row = rs.rows[0] if rs.rows else None
        return int(row[0]) if row else 0

    def list_profiles(self, limit=10, offset=0, search=""):
        client = self._get_client()
        if search:
            s = f"%{search.lower()}%"
            rs = client.execute(
                "SELECT profile_id, name, job_title, email, parsed_date,"
                " COALESCE(json_array_length(json_extract(profile_json, '$.work_history')), 0) AS work_count,"
                " COALESCE(json_array_length(json_extract(profile_json, '$.education')), 0) AS edu_count"
                " FROM cv_profiles"
                " WHERE LOWER(name) LIKE ? OR LOWER(job_title) LIKE ?"
                " ORDER BY parsed_date DESC"
                " LIMIT ? OFFSET ?",
                [s, s, limit, offset],
            )
        else:
            rs = client.execute(
                "SELECT profile_id, name, job_title, email, parsed_date,"
                " COALESCE(json_array_length(json_extract(profile_json, '$.work_history')), 0) AS work_count,"
                " COALESCE(json_array_length(json_extract(profile_json, '$.education')), 0) AS edu_count"
                " FROM cv_profiles"
                " ORDER BY parsed_date DESC"
                " LIMIT ? OFFSET ?",
                [limit, offset],
            )
        return [
            {
                "profile_id":  str(row[0]),
                "name":        row[1] or "",
                "job_title":   row[2] or "",
                "email":       row[3] or "",
                "parsed_date": str(row[4] or ""),
                "work_count":  row[5] or 0,
                "edu_count":   row[6] or 0,
            }
            for row in rs.rows
        ]

    def find_by_hash(self, file_hash: str):
        if not file_hash:
            return None
        try:
            client = self._get_client()
            rs = client.execute(
                "SELECT * FROM cv_profiles WHERE file_hash = ? LIMIT 1",
                [file_hash],
            )
            if not rs.rows:
                return None
            row = rs.rows[0]
            def _d(v):
                return json.loads(v) if isinstance(v, str) else v
            return {
                "schema":     2,
                "profile_id": row[_C["profile_id"]],
                "profile":    _d(row[_C["profile_json"]]),
                "cv":         _d(row[_C["cv_json"]]),
            }
        except Exception:
            return None

    def save_profile(self, profile_id, profile_dict, cv_dict, raw_cv_link="", file_hash=""):
        if not profile_id:
            profile_id = self.next_profile_id()
        client = self._get_client()
        client.execute(
            "INSERT INTO cv_profiles"
            " (profile_id, name, job_title, email, phone, linkedin_url,"
            "  county, current_salary, expected_salary, parsed_date,"
            "  raw_cv_link, profile_json, cv_json, file_hash)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(profile_id) DO UPDATE SET"
            "  name=excluded.name, job_title=excluded.job_title,"
            "  email=excluded.email, phone=excluded.phone,"
            "  linkedin_url=excluded.linkedin_url, county=excluded.county,"
            "  current_salary=excluded.current_salary, expected_salary=excluded.expected_salary,"
            "  parsed_date=excluded.parsed_date, raw_cv_link=excluded.raw_cv_link,"
            "  profile_json=excluded.profile_json, cv_json=excluded.cv_json,"
            "  file_hash=excluded.file_hash",
            [
                profile_id,
                profile_dict.get("name", ""),
                profile_dict.get("job_title", ""),
                profile_dict.get("email", ""),
                profile_dict.get("phone", ""),
                profile_dict.get("linkedin", ""),
                profile_dict.get("county", ""),
                profile_dict.get("current_salary", ""),
                profile_dict.get("desired_salary", ""),
                datetime.now().isoformat(),
                raw_cv_link,
                json.dumps(profile_dict, ensure_ascii=False),
                json.dumps(cv_dict, ensure_ascii=False),
                file_hash or None,
            ],
        )
        return profile_id

    def load_profile(self, profile_id):
        client = self._get_client()
        rs = client.execute(
            "SELECT * FROM cv_profiles WHERE profile_id = ?",
            [str(profile_id)],
        )
        if not rs.rows:
            return None
        row = rs.rows[0]
        def _d(v):
            return json.loads(v) if isinstance(v, str) else v
        return {
            "schema":  2,
            "profile": _d(row[_C["profile_json"]]),
            "cv":      _d(row[_C["cv_json"]]),
        }

    def get_stats(self) -> dict:
        """
        Returns {table_name: count} for cv_profiles and lookup_lists in one query (2 rows).
        Used by the disk-cache sync to decide what data needs refreshing.
        """
        client = self._get_client()
        rs = client.execute(
            "SELECT table_name, total_count FROM table_stats"
            " WHERE table_name IN ('cv_profiles', 'lookup_lists')"
        )
        return {row[0]: int(row[1]) for row in rs.rows}

    def get_all_lookups(self) -> tuple:
        """
        Full fetch of every active lookup value.
        Returns (lookups_dict, max_rowid) — max_rowid becomes the watermark
        so the next sync can request only rows added after this point.
        Called on first boot or after a deletion resets the watermark.
        """
        client = self._get_client()
        rs = client.execute(
            "SELECT rowid, list_name, value FROM lookup_lists"
            " WHERE active = 1"
            " ORDER BY list_name, sort_order, value"
        )
        result: dict = {}
        max_rowid = 0
        for row in rs.rows:
            rowid, lst, val = int(row[0]), row[1], row[2]
            result.setdefault(lst, []).append(val)
            if rowid > max_rowid:
                max_rowid = rowid
        return result, max_rowid

    def list_all_profiles(self) -> list:
        """
        Fetch every profile summary (no limit) for local caching.
        Returns the same dict shape as list_profiles() but for all rows.
        Only the summary columns are fetched — no profile_json / cv_json.
        """
        client = self._get_client()
        rs = client.execute(
            "SELECT profile_id, name, job_title, email, parsed_date,"
            " COALESCE(json_array_length(json_extract(profile_json, '$.work_history')), 0),"
            " COALESCE(json_array_length(json_extract(profile_json, '$.education')), 0)"
            " FROM cv_profiles ORDER BY parsed_date DESC"
        )
        return [
            {
                "profile_id":  str(row[0]),
                "name":        row[1] or "",
                "job_title":   row[2] or "",
                "email":       row[3] or "",
                "parsed_date": str(row[4] or ""),
                "work_count":  row[5] or 0,
                "edu_count":   row[6] or 0,
            }
            for row in rs.rows
        ]

    def get_new_lookups_since(self, last_rowid: int) -> tuple:
        """
        Delta fetch: only rows added after last_rowid (additions only).
        Returns (new_entries_dict, new_max_rowid).
        new_entries_dict has the same shape as get_all_lookups() but only
        contains the newly added values — callers merge these into the cache.
        """
        client = self._get_client()
        rs = client.execute(
            "SELECT rowid, list_name, value FROM lookup_lists"
            " WHERE rowid > ? AND active = 1"
            " ORDER BY rowid",
            [last_rowid],
        )
        result: dict = {}
        new_max = last_rowid
        for row in rs.rows:
            rowid, lst, val = int(row[0]), row[1], row[2]
            result.setdefault(lst, []).append(val)
            if rowid > new_max:
                new_max = rowid
        return result, new_max

    def next_profile_id(self) -> str:
        client = self._get_client()
        rs = client.execute(
            "SELECT MAX(CAST(profile_id AS INTEGER)) FROM cv_profiles"
        )
        row = rs.rows[0] if rs.rows else None
        current = row[0] if (row and row[0] is not None) else 100000
        return str(int(current) + 1)


def from_config(cfg: dict):
    turso = cfg.get("turso", {})
    url   = turso.get("url", "")
    token = turso.get("auth_token", "")
    return TursoStore(url, token) if url and token else None
