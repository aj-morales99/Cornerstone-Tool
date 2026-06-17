#!/bin/bash
# Local macOS build — mirrors the GitHub Actions release workflow.
# Run from the project root: bash build_local.sh
set -e
cd "$(dirname "$0")"

echo "=== CPS Tools — local build ==="

# ── Sanity checks ─────────────────────────────────────────────────────────────
for f in mailshot_helper/config.json cv_config.json cv_parse_format/service-account-key.json logo.png; do
  [ -f "$f" ] || { echo "ERROR: $f not found — needed for build"; exit 1; }
done

# ── Generate logo.icns ────────────────────────────────────────────────────────
echo "→ Generating logo.icns…"
python3 - <<'PYEOF'
from PIL import Image
import os, subprocess
img = Image.open("logo.png").convert("RGBA")
iconset = "logo.iconset"
os.makedirs(iconset, exist_ok=True)
for s in [16,32,64,128,256,512]:
    img.resize((s,s),   Image.LANCZOS).save(f"{iconset}/icon_{s}x{s}.png")
    img.resize((s*2,s*2), Image.LANCZOS).save(f"{iconset}/icon_{s}x{s}@2x.png")
subprocess.run(["iconutil","-c","icns",iconset,"-o","logo.icns"], check=True)
import shutil; shutil.rmtree(iconset)
print("logo.icns ready")
PYEOF

# ── PyInstaller ───────────────────────────────────────────────────────────────
echo "→ Running PyInstaller…"
pyinstaller \
  --noconfirm --windowed --name "CPS Tools" \
  --icon "logo.icns" \
  --add-data "logo.png:." \
  --add-data "cv_parse_format/templates:cv_parse_format/templates" \
  --add-data "cv_parse_format/design:cv_parse_format/design" \
  --add-data "cv_parse_format/cv_parse_format_tool.py:cv_parse_format" \
  --add-data "cv_parse_format/google_sheets_store.py:cv_parse_format" \
  --add-data "cv_parse_format/google_drive_store.py:cv_parse_format" \
  --add-data "import_contact/import_contact_tool.py:import_contact" \
  --add-data "mailshot_helper/mailshot_helper_tool.py:mailshot_helper" \
  --add-data "mailshot_helper/config.json:mailshot_helper" \
  --add-data "cv_config.json:." \
  --add-data "cv_parse_format/service-account-key.json:cv_parse_format" \
  --hidden-import customtkinter --hidden-import anthropic --hidden-import pydantic \
  --hidden-import docx --hidden-import docxtpl --hidden-import pdfplumber \
  --hidden-import docx2pdf --hidden-import PIL --hidden-import fitz \
  --hidden-import requests --hidden-import google.oauth2.service_account \
  --hidden-import google.auth.transport.requests --hidden-import googleapiclient.discovery \
  --hidden-import gspread --hidden-import pandas --hidden-import openpyxl \
  --hidden-import pdfminer --hidden-import pdfminer.high_level \
  --hidden-import pdfminer.layout --hidden-import pdfminer.pdfpage \
  --hidden-import jinja2 \
  CornerstoneTools.py

# ── Ad-hoc codesign + remove quarantine ──────────────────────────────────────
echo "→ Codesigning…"
codesign --force --deep --sign - "dist/CPS Tools.app" || true
xattr -cr "dist/CPS Tools.app" || true

echo ""
echo "✓ Done. App is at: dist/CPS Tools.app"
echo "  Right-click → Open if macOS blocks it on first launch."
