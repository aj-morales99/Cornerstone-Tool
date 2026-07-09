"""
PostgreSQL data store for CPS Tools — primary backend (Supabase).
Implements the same interface as google_sheets_store so the rest of the app
is unchanged. Falls back to Google Sheets → local JSON when unavailable.
"""

import json
import psycopg2
import psycopg2.extras
from datetime import datetime


class PostgresStore:
    def __init__(self, database_url: str):
        self._url = database_url
        self._conn = None

    def _connect(self):
        if not self._conn or self._conn.closed:
            url = self._url
            if "sslmode" not in url:
                url = url + ("&" if "?" in url else "?") + "sslmode=require"
            self._conn = psycopg2.connect(url, connect_timeout=20)
        return self._conn

    def is_available(self) -> bool:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute("SELECT 1")
            conn.commit()
            # Non-destructive migration: add file_hash column if missing — ignore any failure
            try:
                cur.execute(
                    "ALTER TABLE cv_profiles ADD COLUMN IF NOT EXISTS file_hash TEXT")
                conn.commit()
            except Exception:
                conn.rollback()
            return True
        except Exception:
            self._conn = None
            return False

    def find_by_hash(self, file_hash: str):
        """Return stored profile dict if a record with this file_hash exists, else None."""
        if not file_hash:
            return None
        try:
            with self._connect().cursor(
                    cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM cv_profiles WHERE file_hash = %s LIMIT 1",
                    (file_hash,))
                row = cur.fetchone()
            if not row:
                return None
            def _d(v):
                return json.loads(v) if isinstance(v, str) else v
            return {
                "schema": 2,
                "profile_id": row["profile_id"],
                "profile": _d(row["profile_json"]),
                "cv": _d(row["cv_json"]),
            }
        except Exception:
            return None

    def save_profile(self, profile_id, profile_dict, cv_dict, raw_cv_link="", file_hash=""):
        if not profile_id:
            profile_id = self.next_profile_id()
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cv_profiles
                    (profile_id, name, job_title, email, phone, linkedin_url,
                     county, current_salary, expected_salary, parsed_date,
                     raw_cv_link, profile_json, cv_json, file_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (profile_id) DO UPDATE SET
                    name            = EXCLUDED.name,
                    job_title       = EXCLUDED.job_title,
                    email           = EXCLUDED.email,
                    phone           = EXCLUDED.phone,
                    linkedin_url    = EXCLUDED.linkedin_url,
                    county          = EXCLUDED.county,
                    current_salary  = EXCLUDED.current_salary,
                    expected_salary = EXCLUDED.expected_salary,
                    parsed_date     = EXCLUDED.parsed_date,
                    raw_cv_link     = EXCLUDED.raw_cv_link,
                    profile_json    = EXCLUDED.profile_json,
                    cv_json         = EXCLUDED.cv_json,
                    file_hash       = EXCLUDED.file_hash
            """, (
                profile_id,
                profile_dict.get("name", ""),
                profile_dict.get("job_title", ""),
                profile_dict.get("email", ""),
                profile_dict.get("phone", ""),
                profile_dict.get("linkedin", ""),
                profile_dict.get("county", ""),
                profile_dict.get("current_salary", ""),
                profile_dict.get("desired_salary", ""),
                datetime.now(),
                raw_cv_link,
                json.dumps(profile_dict, ensure_ascii=False),
                json.dumps(cv_dict, ensure_ascii=False),
                file_hash or None,
            ))
        conn.commit()
        return profile_id

    def load_profile(self, profile_id):
        with self._connect().cursor(
                cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM cv_profiles WHERE profile_id = %s",
                (profile_id,))
            row = cur.fetchone()
        if not row:
            return None
        def _d(v):
            return json.loads(v) if isinstance(v, str) else v

        return {
            "schema": 2,
            "profile": _d(row["profile_json"]),
            "cv":      _d(row["cv_json"]),
        }

    def list_profiles(self):
        with self._connect().cursor(
                cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    profile_id,
                    name,
                    job_title,
                    email,
                    parsed_date,
                    COALESCE(jsonb_array_length(profile_json -> 'work_history'), 0) AS work_count,
                    COALESCE(jsonb_array_length(profile_json -> 'education'),    0) AS edu_count
                FROM cv_profiles
                ORDER BY parsed_date DESC NULLS LAST
            """)
            rows = cur.fetchall()
        return [
            {
                "profile_id":  r["profile_id"],
                "name":        r["name"] or "",
                "job_title":   r["job_title"] or "",
                "email":       r["email"] or "",
                "parsed_date": str(r["parsed_date"] or ""),
                "work_count":  r["work_count"],
                "edu_count":   r["edu_count"],
            }
            for r in rows
        ]

    def next_profile_id(self) -> str:
        with self._connect().cursor() as cur:
            cur.execute("SELECT MAX(CAST(profile_id AS INTEGER)) FROM cv_profiles")
            row = cur.fetchone()
        current = row[0] if row and row[0] else 100000
        return str(current + 1)


def from_config(cfg: dict):
    url = cfg.get("postgres", {}).get("database_url", "")
    return PostgresStore(url) if url else None
