"""
Google Drive backend for uploading CV files (raw and formatted).

Uses the same service account as google_sheets_store.
Share the target folders with: cornerstone-sheets@cornerstone-tools.iam.gserviceaccount.com

Folder IDs (configured in cv_config.json):
  "google_drive": {
    "credentials_path": "...",
    "raw_cv_folder_id":       "1CCV45XyyJdaOk19zi7YLNaoskl5Zg6FC",
    "formatted_cv_folder_id": "1oqQpRP4C7vX0-17_Am9abE5lsdIkH3hV"
  }
"""

import os

RAW_FOLDER_ID       = "1CCV45XyyJdaOk19zi7YLNaoskl5Zg6FC"
FORMATTED_FOLDER_ID = "1oqQpRP4C7vX0-17_Am9abE5lsdIkH3hV"

MIME_MAP = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
}


class DriveStore:
    def __init__(self, credentials_path: str):
        self._creds_path = credentials_path
        self._service    = None

    def _connect(self):
        if self._service:
            return
        try:
            from googleapiclient.discovery import build
            from google.oauth2.service_account import Credentials
        except ImportError:
            raise RuntimeError(
                "Google Drive support needs:\n  pip install google-api-python-client google-auth"
            )
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(self._creds_path, scopes=scopes)
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def upload_file(self, local_path: str, folder_id: str, filename: str = None) -> str:
        """
        Upload a file to a Drive folder.
        Auto-renames to avoid collisions (e.g. 'CV Jones (1).pdf').
        Returns the shareable web view link.
        """
        self._connect()
        from googleapiclient.http import MediaFileUpload

        if filename is None:
            filename = os.path.basename(local_path)

        final_name = self._unique_name(folder_id, filename)
        ext  = os.path.splitext(local_path)[1].lower()
        mime = MIME_MAP.get(ext, "application/octet-stream")

        metadata = {"name": final_name, "parents": [folder_id]}
        media    = MediaFileUpload(local_path, mimetype=mime, resumable=True)
        f = self._service.files().create(
            body=metadata, media_body=media, fields="id,webViewLink"
        ).execute()

        # Anyone with the link can view
        self._service.permissions().create(
            fileId=f["id"],
            body={"role": "reader", "type": "anyone"},
        ).execute()

        return f.get("webViewLink", "")

    def _unique_name(self, folder_id: str, filename: str) -> str:
        """Append (1), (2) … until the name is free in the folder."""
        self._connect()
        base, ext = os.path.splitext(filename)
        name    = filename
        counter = 1
        while True:
            safe = name.replace("'", "\\'")
            q = f"name='{safe}' and '{folder_id}' in parents and trashed=false"
            hits = self._service.files().list(q=q, fields="files(id)").execute()
            if not hits.get("files"):
                return name
            name = f"{base} ({counter}){ext}"
            counter += 1

    def is_available(self) -> bool:
        try:
            self._connect()
            return True
        except Exception as e:
            print(f"[drive] {e}")
            return False


# ── singleton factory ──────────────────────────────────────────────────────────
_instance = None

def get_drive_store(cfg: dict) -> "DriveStore | None":
    global _instance
    if _instance is not None:
        return _instance
    creds = (cfg.get("google_drive") or {}).get("credentials_path") \
            or (cfg.get("google_sheets") or {}).get("credentials_path", "")
    if not creds or not os.path.exists(creds):
        return None
    _instance = DriveStore(creds)
    return _instance if _instance.is_available() else None
