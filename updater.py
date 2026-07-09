"""
CPS Tools auto-updater.

check_update()   — background-safe; returns update dict or None
install_update() — downloads zip, writes platform helper, quits current app
"""

import os
import sys
import tempfile
import zipfile

GITHUB_REPO = "aj-morales99/Cornerstone-Tool"
_API_URL    = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_ASSET_MAC  = "CPS-Tools-macOS.zip"
_ASSET_WIN  = "CPS-Tools-Windows.zip"


# ── Version helpers ───────────────────────────────────────────────────────────

def get_current_version() -> str:
    meipass = getattr(sys, "_MEIPASS", None)
    search  = ([meipass] if meipass else []) + [os.path.dirname(os.path.abspath(__file__))]
    for base in search:
        try:
            with open(os.path.join(base, "VERSION")) as f:
                return f.read().strip().lstrip("v")
        except Exception:
            pass
    return "0.0.0"


def _version_gt(a: str, b: str) -> bool:
    def parse(v):
        try:
            return tuple(int(x) for x in v.lstrip("v").split("."))
        except Exception:
            return (0, 0, 0)
    return parse(a) > parse(b)


# ── Update check ─────────────────────────────────────────────────────────────

def check_update() -> dict | None:
    """
    Hit the GitHub Releases API and return update info if a newer version exists.
    Returns None if up-to-date or on any network error.
    Safe to call from a background thread.
    """
    try:
        import requests
        r = requests.get(_API_URL, timeout=8,
                         headers={"Accept": "application/vnd.github.v3+json"})
        if r.status_code != 200:
            return None
        data    = r.json()
        latest  = data["tag_name"].lstrip("v")
        current = get_current_version()
        if not _version_gt(latest, current):
            return None
        asset_name = _ASSET_MAC if sys.platform == "darwin" else _ASSET_WIN
        for asset in data.get("assets", []):
            if asset["name"] == asset_name:
                return {
                    "version":      latest,
                    "current":      current,
                    "download_url": asset["browser_download_url"],
                    "notes":        (data.get("body") or "").strip(),
                }
    except Exception:
        pass
    return None


# ── Install ───────────────────────────────────────────────────────────────────

def _data_dir() -> str:
    if sys.platform == "win32":
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "CPS Tools")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "CPS Tools")
    return os.path.join(os.path.expanduser("~"), ".cpstools")


def _current_app_path() -> str:
    """
    macOS: path to the .app bundle  (/path/to/CPS Tools.app)
    Windows: path to the install folder  (C:\\...\\CPS Tools)
    Only valid inside a PyInstaller frozen bundle.
    """
    if not getattr(sys, "frozen", False):
        raise RuntimeError(
            "install_update() must be called from a frozen app, not from source."
        )
    if sys.platform == "darwin":
        # sys.executable = /.../CPS Tools.app/Contents/MacOS/CPS Tools
        return os.path.normpath(
            os.path.join(os.path.dirname(sys.executable), "..", "..")
        )
    return os.path.dirname(sys.executable)


def install_update(download_url: str, progress_cb=None):
    """
    1. Download the release zip (streaming, with progress callback)
    2. Extract to a temp directory
    3. Write a platform-specific helper script that runs AFTER this process exits
    4. Launch the helper and call sys.exit()

    progress_cb(fraction: float) is called with 0.0–1.0 during download.
    """
    import requests, subprocess

    # ── 1. Download ───────────────────────────────────────────────────────────
    data_dir = _data_dir()
    os.makedirs(data_dir, exist_ok=True)
    zip_path = os.path.join(data_dir, "update.zip")

    r = requests.get(download_url, stream=True, timeout=120)
    total      = int(r.headers.get("content-length", 0))
    downloaded = 0
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total:
                    progress_cb(downloaded / total)
    if progress_cb:
        progress_cb(1.0)

    # ── 2. Extract ────────────────────────────────────────────────────────────
    tmp_dir = tempfile.mkdtemp(prefix="cpstools_update_")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_dir)

    current  = _current_app_path()
    dest_dir = os.path.dirname(current)

    # ── 3+4. Write helper and launch ─────────────────────────────────────────
    if sys.platform == "darwin":
        new_app = os.path.join(tmp_dir, "CPS Tools.app")
        dest    = os.path.join(dest_dir, "CPS Tools.app")
        script  = "\n".join([
            "#!/bin/bash",
            "sleep 2",
            f'rm -rf "{dest}"',
            f'mv "{new_app}" "{dest}"',
            f'open "{dest}"',
            'rm -- "$0"',
            "",
        ])
        sh = os.path.join(tmp_dir, "cpstools_update.sh")
        with open(sh, "w") as f:
            f.write(script)
        os.chmod(sh, 0o755)
        subprocess.Popen(["bash", sh])

    else:  # Windows
        new_dir  = os.path.join(tmp_dir, "CPS Tools")
        new_exe  = os.path.join(current, "CPS Tools.exe")
        bat = "\r\n".join([
            "@echo off",
            "timeout /t 3 /nobreak > nul",
            f'robocopy "{new_dir}" "{current}" /E /IS /IT /IM /NFL /NDL /NJH /NJS > nul',
            f'start "" "{new_exe}"',
            'del "%~f0"',
            "",
        ])
        bat_path = os.path.join(tmp_dir, "cpstools_update.bat")
        with open(bat_path, "w") as f:
            f.write(bat)
        subprocess.Popen(
            ["cmd", "/c", bat_path],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )

    os._exit(0)
