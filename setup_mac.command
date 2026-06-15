#!/bin/bash
# Cornerstone Tools — Mac Setup
# Double-click this file to install everything needed.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "============================================"
echo "  Cornerstone Tools — Mac Setup"
echo "============================================"
echo ""

# ── 1. Homebrew ──────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "[1/6] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH for Apple Silicon
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "[1/6] Homebrew already installed ✓"
fi

# ── 2. Python 3 ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "[2/6] Installing Python 3..."
    brew install python
else
    echo "[2/6] Python 3 already installed ✓"
fi

# ── 3. Python packages ───────────────────────────────────────────────────────
echo "[3/6] Installing Python packages..."
python3 -m pip install --upgrade pip --quiet
python3 -m pip install \
    customtkinter anthropic pydantic python-docx docxtpl \
    pdfplumber docx2pdf pillow requests pymupdf --quiet
echo "      Python packages installed ✓"

# ── 4. LibreOffice ───────────────────────────────────────────────────────────
if [[ ! -d "/Applications/LibreOffice.app" ]]; then
    echo "[4/6] Installing LibreOffice (this may take a few minutes)..."
    brew install --cask libreoffice
else
    echo "[4/6] LibreOffice already installed ✓"
fi

# ── 5. Poppler (pdftoppm for CV preview) ─────────────────────────────────────
if ! command -v pdftoppm &>/dev/null; then
    echo "[5/6] Installing Poppler..."
    brew install poppler
else
    echo "[5/6] Poppler already installed ✓"
fi

# ── 6. Roboto fonts ──────────────────────────────────────────────────────────
FONT_DIR="$HOME/Library/Fonts"
FONTS_SRC="$SCRIPT_DIR/cv_parse_format/fonts"
if [[ -d "$FONTS_SRC" ]]; then
    echo "[6/6] Installing Roboto fonts..."
    cp "$FONTS_SRC"/*.ttf "$FONT_DIR/" 2>/dev/null && echo "      Fonts installed ✓" || echo "      Fonts already up to date ✓"
else
    echo "[6/6] Roboto fonts: downloading via brew..."
    brew install --cask font-roboto 2>/dev/null || echo "      (font-roboto not in tap — skipping, app will fall back to Arial)"
fi

echo ""
echo "============================================"
echo "  Setup complete!"
echo ""
echo "  To run the app:"
echo "  python3 \"$SCRIPT_DIR/CornerstoneTools.py\""
echo ""
echo "  Fill in your credentials:"
echo "    config.json          (Bullhorn + Instantly)"
echo "    cv_parse_format/cv_config.json  (Anthropic API key)"
echo "============================================"
echo ""

# Open the folder so the user sees the files
open "$SCRIPT_DIR"

echo ""
echo "  To UNINSTALL everything this script installed, run:"
echo "    brew uninstall --cask libreoffice"
echo "    brew uninstall --cask font-roboto"
echo "    pip3 uninstall customtkinter anthropic pydantic python-docx docxtpl pdfplumber docx2pdf pillow requests pymupdf -y"
echo "  (Python and Homebrew itself can be kept for other uses)"
echo ""

read -p "Press Enter to close..."
