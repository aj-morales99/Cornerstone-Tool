#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Cornerstone Tools — macOS build script
# Produces:  dist/Cornerstone Tools.app   →   Cornerstone-Tools-macOS.zip
#
# Run from the repo root on a Mac:
#   chmod +x build_mac.sh && ./build_mac.sh
#
# No Apple Developer certificate needed.
# Ad-hoc signing + quarantine removal mean macOS won't block the app.
# ─────────────────────────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Cornerstone Tools"
ZIP_NAME="Cornerstone-Tools-macOS.zip"

echo "──────────────────────────────────────────"
echo "  Installing build dependencies…"
echo "──────────────────────────────────────────"
pip3 install pyinstaller pymupdf --quiet

echo ""
echo "──────────────────────────────────────────"
echo "  Building $APP_NAME.app…"
echo "──────────────────────────────────────────"
pyinstaller \
    --noconfirm \
    --windowed \
    --name "$APP_NAME" \
    \
    --add-data "cv_parse_format/templates:cv_parse_format/templates" \
    --add-data "cv_parse_format/design:cv_parse_format/design" \
    --add-data "cv_parse_format/cv_parse_format_tool.py:cv_parse_format" \
    --add-data "cv_parse_format/google_sheets_store.py:cv_parse_format" \
    --add-data "cv_parse_format/google_drive_store.py:cv_parse_format" \
    --add-data "import_contact/import_contact_tool.py:import_contact" \
    --add-data "mailshot_helper/mailshot_helper_tool.py:mailshot_helper" \
    \
    --add-data "mailshot_helper/config.json:mailshot_helper" \
    --add-data "cv_config.json:." \
    --add-data "cv_parse_format/service-account-key.json:cv_parse_format" \
    \
    --hidden-import "customtkinter" \
    --hidden-import "anthropic" \
    --hidden-import "pydantic" \
    --hidden-import "docx" \
    --hidden-import "docxtpl" \
    --hidden-import "pdfplumber" \
    --hidden-import "docx2pdf" \
    --hidden-import "PIL" \
    --hidden-import "fitz" \
    --hidden-import "requests" \
    --hidden-import "google.oauth2.service_account" \
    --hidden-import "google.auth.transport.requests" \
    --hidden-import "googleapiclient.discovery" \
    \
    CornerstoneTools.py

APP_PATH="dist/$APP_NAME.app"

echo ""
echo "──────────────────────────────────────────"
echo "  Ad-hoc signing (no certificate needed)…"
echo "──────────────────────────────────────────"
# Ad-hoc signing suppresses the 'app is damaged' error on newer macOS
codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || true

echo ""
echo "──────────────────────────────────────────"
echo "  Removing quarantine flag…"
echo "──────────────────────────────────────────"
# Removes the quarantine attribute so Gatekeeper won't block on this machine
xattr -cr "$APP_PATH" 2>/dev/null || true

echo ""
echo "──────────────────────────────────────────"
echo "  Zipping for distribution…"
echo "──────────────────────────────────────────"
cd dist
zip -r --symlinks "../$ZIP_NAME" "$APP_NAME.app"
cd "$SCRIPT_DIR"

echo ""
echo "══════════════════════════════════════════"
echo "  Build complete: $ZIP_NAME"
echo "══════════════════════════════════════════"
echo ""
echo "  Upload $ZIP_NAME to the GitHub release."
echo ""
echo "  ⚠  Recipients who download the zip:"
echo "     Right-click the .app → Open → Open"
echo "     (only needed on very first launch)"
echo ""
