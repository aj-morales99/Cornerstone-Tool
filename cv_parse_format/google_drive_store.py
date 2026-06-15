"""
Google Drive backend for uploading CV files (raw and formatted).

Uses OAuth 2.0 (Desktop app) so uploads count against the real user's
Google Drive quota — service accounts have no quota of their own.

One-time setup:
1. Google Cloud Console → APIs & Services → Credentials
2. Create Credentials → OAuth client ID → Desktop app → download JSON
3. Add to cv_config.json:
     "google_drive": {
       "oauth_client_path": "/path/to/drive-oauth-client.json",
       "token_path":        "/path/to/drive-token.json"   (auto-created on first run)
     }
4. First time the app uploads, a browser tab opens for a one-time Google login.
   After that the token is reused silently.

Folder IDs (hardcoded — share these folders with your Google account):
  RAW CV:       1CCV45XyyJdaOk19zi7YLNaoskl5Zg6FC
  FORMATTED CV: 1oqQpRP4C7vX0-17_Am9abE5lsdIkH3hV
"""

import os

RAW_FOLDER_ID       = "1CCV45XyyJdaOk19zi7YLNaoskl5Zg6FC"
FORMATTED_FOLDER_ID = "1oqQpRP4C7vX0-17_Am9abE5lsdIkH3hV"
SCOPES              = ["https://www.googleapis.com/auth/drive"]

MIME_MAP = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
}


class DriveStore:
    def __init__(self, oauth_client_path: str, token_path: str):
        self._oauth_client = oauth_client_path
        self._token_path   = token_path
        self._service      = None

    def _connect(self):
        if self._service:
            return
        try:
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            raise RuntimeError(
                "Google Drive support needs:\n"
                "  pip install google-api-python-client google-auth-oauthlib"
            )

        creds = None
        if os.path.exists(self._token_path):
            creds = Credentials.from_authorized_user_file(self._token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self._oauth_client, SCOPES
                )
                # Opens a browser tab for one-time login
                creds = flow.run_local_server(port=0)
            # Save token for future runs
            with open(self._token_path, "w") as f:
                f.write(creds.to_json())

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
            body=metadata, media_body=media, fields="id,webViewLink",
            supportsAllDrives=True,
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
            q    = f"name='{safe}' and '{folder_id}' in parents and trashed=false"
            hits = self._service.files().list(
                q=q, fields="files(id)", supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
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
    gd = cfg.get("google_drive") or {}
    client = gd.get("oauth_client_path", "")
    token  = gd.get("token_path", "")
    if not client or not os.path.exists(client):
        print("[drive] No OAuth client configured — Drive upload disabled")
        return None
    if not token:
        token = os.path.join(os.path.dirname(client), "drive-token.json")
    store = DriveStore(client, token)
    _instance = store
    return _instance
