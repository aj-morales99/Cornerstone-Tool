"""
Google Sheets backend for CV profiles.

Sheet layout (one row per candidate):
  A: profile_id   B: name          C: job_title     D: email
  E: phone        F: linkedin_url  G: county        H: current_salary
  I: expected_salary               J: parsed_date   K: raw_cv_link
  L: profile_json  M: cv_json
"""

import json
import os
import threading
from datetime import datetime

HEADER = [
    "profile_id", "name", "job_title", "email",
    "phone", "linkedin_url", "county", "current_salary", "expected_salary",
    "parsed_date", "raw_cv_link",
    "profile_json", "cv_json",
]
COL = {h: i for i, h in enumerate(HEADER)}

START_ID = 100001


class SheetsStore:
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        self._creds_path     = credentials_path
        self._spreadsheet_id = spreadsheet_id
        self._lock           = threading.Lock()
        self._client         = None
        self._sheet          = None

    # ── connection ────────────────────────────────────────────────────────────

    def _connect(self):
        if self._sheet is not None:
            return
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise RuntimeError(
                "Google Sheets support needs:\n  pip install gspread google-auth"
            )
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds = Credentials.from_service_account_file(self._creds_path, scopes=scopes)
        self._client = gspread.authorize(creds)
        wb = self._client.open_by_key(self._spreadsheet_id)
        ws = wb.sheet1
        existing = ws.row_values(1)
        if existing != HEADER:
            ws.clear()
            ws.append_row(HEADER, value_input_option="RAW")
        self._sheet = ws

    # ── ID generation ─────────────────────────────────────────────────────────

    def _next_id(self) -> str:
        """Return next 6-digit numeric ID (starts at 100001)."""
        ids = []
        for val in self._sheet.col_values(COL["profile_id"] + 1)[1:]:
            try:
                n = int(val)
                if n >= START_ID:
                    ids.append(n)
            except (ValueError, TypeError):
                pass
        return str(max(ids) + 1) if ids else str(START_ID)

    # ── public API ────────────────────────────────────────────────────────────

    def list_profiles(self) -> list[dict]:
        with self._lock:
            self._connect()
            rows = self._sheet.get_all_values()[1:]
        summaries = []
        for row in rows:
            if len(row) < len(HEADER):
                row += [""] * (len(HEADER) - len(row))
            summaries.append({
                "profile_id":     row[COL["profile_id"]],
                "name":           row[COL["name"]],
                "job_title":      row[COL["job_title"]],
                "email":          row[COL["email"]],
                "phone":          row[COL["phone"]],
                "county":         row[COL["county"]],
                "current_salary": row[COL["current_salary"]],
                "expected_salary":row[COL["expected_salary"]],
                "parsed_date":    row[COL["parsed_date"]],
                "raw_cv_link":    row[COL["raw_cv_link"]],
            })
        summaries.sort(key=lambda r: r["parsed_date"], reverse=True)
        return summaries

    def load_profile(self, profile_id: str) -> dict | None:
        with self._lock:
            self._connect()
            cell = self._sheet.find(str(profile_id), in_column=COL["profile_id"] + 1)
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

    def save_profile(self, profile_id: str | None, profile: dict, cv: dict,
                     raw_cv_link: str = "") -> str:
        """
        Upsert a candidate row. Generates a new numeric ID if profile_id is None.
        Returns the profile_id used.
        """
        with self._lock:
            self._connect()
            # Resolve ID
            if not profile_id:
                profile_id = self._next_id()
            else:
                try:
                    int(profile_id)
                except (ValueError, TypeError):
                    # Legacy non-numeric ID → assign a new numeric one
                    profile_id = self._next_id()

            parsed_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            row_data = [
                profile_id,
                profile.get("name", ""),
                profile.get("job_title", ""),
                profile.get("email", ""),
                profile.get("phone", ""),
                profile.get("linkedin", ""),
                profile.get("county", ""),
                profile.get("current_salary", ""),
                profile.get("desired_salary", ""),
                parsed_date,
                raw_cv_link,
                json.dumps(profile, ensure_ascii=False),
                json.dumps(cv,      ensure_ascii=False),
            ]

            cell = self._sheet.find(str(profile_id), in_column=COL["profile_id"] + 1)
            if cell:
                end_col = _col_letter(len(HEADER))
                self._sheet.update(
                    f"A{cell.row}:{end_col}{cell.row}",
                    [row_data], value_input_option="RAW"
                )
            else:
                self._sheet.append_row(row_data, value_input_option="RAW")

        return str(profile_id)

    def update_raw_cv_link(self, profile_id: str, link: str):
        """Update just the raw_cv_link cell for an existing row."""
        with self._lock:
            self._connect()
            cell = self._sheet.find(str(profile_id), in_column=COL["profile_id"] + 1)
            if cell:
                col = COL["raw_cv_link"] + 1
                self._sheet.update_cell(cell.row, col, link)

    def delete_profile(self, profile_id: str) -> bool:
        with self._lock:
            self._connect()
            cell = self._sheet.find(str(profile_id), in_column=COL["profile_id"] + 1)
            if cell is None:
                return False
            self._sheet.delete_rows(cell.row)
        return True

    def is_available(self) -> bool:
        try:
            self._connect()
            return True
        except Exception:
            return False


# ── helpers ───────────────────────────────────────────────────────────────────

def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def from_config(cfg: dict) -> "SheetsStore | None":
    gs   = cfg.get("google_sheets") or {}
    creds = gs.get("credentials_path", "")
    sid   = gs.get("spreadsheet_id", "")
    if not creds or not sid or not os.path.exists(creds):
        return None
    return SheetsStore(creds, sid)
