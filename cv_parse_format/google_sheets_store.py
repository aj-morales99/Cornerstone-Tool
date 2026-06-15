"""
Google Sheets backend for CV profiles.

Sheet layout (one row per candidate):
  A: profile_id      B: name            C: job_title
  D: email           E: parsed_date     F: work_count
  G: edu_count       H: profile_json    I: cv_json

profile_json and cv_json store the full dicts as JSON strings.
The app treats this sheet as the source of truth; local JSON is a
read-through cache written only when the sheet is unreachable.
"""

import json
import os
import threading
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HEADER = [
    "profile_id", "name", "job_title", "email",
    "parsed_date", "work_count", "edu_count",
    "profile_json", "cv_json",
]
COL = {h: i for i, h in enumerate(HEADER)}   # name → 0-based index


# ---------------------------------------------------------------------------
# SheetsStore
# ---------------------------------------------------------------------------
class SheetsStore:
    """
    Thread-safe Google Sheets profile store.

    Requires in cv_config.json:
      "google_sheets": {
        "credentials_path": "/path/to/service-account-key.json",
        "spreadsheet_id":   "1AbCd..."
      }
    """

    def __init__(self, credentials_path: str, spreadsheet_id: str):
        self._creds_path      = credentials_path
        self._spreadsheet_id  = spreadsheet_id
        self._lock            = threading.Lock()
        self._client          = None   # gspread client (lazy)
        self._sheet           = None   # worksheet (lazy)

    # ── connection ────────────────────────────────────────────────────────────

    def _connect(self):
        """Open / reuse the gspread client and worksheet."""
        if self._sheet is not None:
            return
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise RuntimeError(
                "Google Sheets support needs two packages:\n"
                "  pip install gspread google-auth"
            )

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds = Credentials.from_service_account_file(self._creds_path, scopes=scopes)
        self._client = gspread.authorize(creds)
        wb = self._client.open_by_key(self._spreadsheet_id)

        # Use first sheet; create header row if the sheet is blank
        ws = wb.sheet1
        existing = ws.row_values(1)
        if existing != HEADER:
            ws.clear()
            ws.append_row(HEADER, value_input_option="RAW")
        self._sheet = ws

    def _reconnect(self):
        """Force a fresh connection (e.g. after a token error)."""
        self._sheet  = None
        self._client = None
        self._connect()

    # ── public API ────────────────────────────────────────────────────────────

    def list_profiles(self) -> list[dict]:
        """
        Return a list of summary dicts (no full JSON blobs) sorted by
        parsed_date descending (most recent first).
        """
        with self._lock:
            self._connect()
            rows = self._sheet.get_all_values()[1:]   # skip header

        summaries = []
        for row in rows:
            if len(row) < len(HEADER):
                row += [""] * (len(HEADER) - len(row))
            summaries.append({
                "profile_id":   row[COL["profile_id"]],
                "name":         row[COL["name"]],
                "job_title":    row[COL["job_title"]],
                "email":        row[COL["email"]],
                "parsed_date":  row[COL["parsed_date"]],
                "work_count":   _safe_int(row[COL["work_count"]]),
                "edu_count":    _safe_int(row[COL["edu_count"]]),
            })

        summaries.sort(key=lambda r: r["parsed_date"], reverse=True)
        return summaries

    def load_profile(self, profile_id: str) -> dict | None:
        """
        Return the full {"schema":2, "profile":{...}, "cv":{...}} dict
        for the given profile_id, or None if not found.
        """
        with self._lock:
            self._connect()
            cell = self._sheet.find(profile_id, in_column=COL["profile_id"] + 1)
            if cell is None:
                return None
            row = self._sheet.row_values(cell.row)

        if len(row) < len(HEADER):
            row += [""] * (len(HEADER) - len(row))

        try:
            profile = json.loads(row[COL["profile_json"]] or "{}")
            cv      = json.loads(row[COL["cv_json"]]      or "{}")
        except json.JSONDecodeError:
            return None

        return {"schema": 2, "profile": profile, "cv": cv}

    def save_profile(self, profile_id: str, profile: dict, cv: dict) -> str:
        """
        Upsert a candidate row.  Returns the profile_id (unchanged or new).
        """
        parsed_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        work_count  = len(profile.get("work_history") or [])
        edu_count   = len(profile.get("education")    or [])

        row_data = [
            profile_id,
            profile.get("name", ""),
            profile.get("job_title", ""),
            profile.get("email", ""),
            parsed_date,
            work_count,
            edu_count,
            json.dumps(profile, ensure_ascii=False),
            json.dumps(cv,      ensure_ascii=False),
        ]

        with self._lock:
            self._connect()
            cell = self._sheet.find(profile_id, in_column=COL["profile_id"] + 1)
            if cell:
                # Update existing row
                col_letter_end = _col_letter(len(HEADER))
                rng = f"A{cell.row}:{col_letter_end}{cell.row}"
                self._sheet.update(rng, [row_data], value_input_option="RAW")
            else:
                # Append new row
                self._sheet.append_row(row_data, value_input_option="RAW")

        return profile_id

    def delete_profile(self, profile_id: str) -> bool:
        """Delete the row for profile_id. Returns True if found and deleted."""
        with self._lock:
            self._connect()
            cell = self._sheet.find(profile_id, in_column=COL["profile_id"] + 1)
            if cell is None:
                return False
            self._sheet.delete_rows(cell.row)
        return True

    def is_available(self) -> bool:
        """Quick connectivity check — False means fall back to local JSON."""
        try:
            self._connect()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(val) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _col_letter(n: int) -> str:
    """Convert 1-based column index to A, B, … Z, AA, AB …"""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------------------
# Factory — build from cv_config.json section
# ---------------------------------------------------------------------------

def from_config(cfg: dict) -> "SheetsStore | None":
    """
    Build a SheetsStore from the 'google_sheets' section of cv_config.
    Returns None if the section is missing or incomplete.
    """
    gs = cfg.get("google_sheets") or {}
    creds = gs.get("credentials_path", "")
    sid   = gs.get("spreadsheet_id", "")
    if not creds or not sid:
        return None
    if not os.path.exists(creds):
        return None
    return SheetsStore(creds, sid)
