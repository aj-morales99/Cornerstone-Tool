#!/bin/bash
# Cornerstone Tools — Mac build script
# Produces: dist/Cornerstone Tools.app
# Run from the repo root on a Mac with Python + pip deps installed.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Installing build deps..."
pip3 install pyinstaller pymupdf --quiet

echo "Building Cornerstone Tools.app..."
pyinstaller \
    --noconfirm \
    --windowed \
    --name "Cornerstone Tools" \
    --add-data "cv_parse_format/templates:cv_parse_format/templates" \
    --add-data "cv_parse_format/design:cv_parse_format/design" \
    --add-data "cv_parse_format/cv_parse_format_tool.py:cv_parse_format" \
    --add-data "import_contact/import_contact_tool.py:import_contact" \
    --add-data "mailshot_helper/mailshot_helper_tool.py:mailshot_helper" \
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
    CornerstoneTools.py

echo ""
echo "Build complete: dist/Cornerstone Tools.app"
echo ""
echo "To distribute: zip the .app and upload to the GitHub release."
echo "zip -r 'Cornerstone-Tools-macOS.zip' 'dist/Cornerstone Tools.app'"
