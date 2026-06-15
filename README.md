# Cornerstone Tools

Multi-tool desktop app for Cornerstone Project Source.

## Tools

| Tool | Description |
|------|-------------|
| CV Parse & Format | Parse candidate CVs (.docx / .pdf) via Claude AI, edit profile details, generate anonymised branded PDF |
| Import Contacts | Search and import contacts from Bullhorn CRM |
| Mailshot Helper | Filter Bullhorn contacts and push them to Instantly.ai campaigns |

## Setup

### Requirements

- Python 3.10+
- LibreOffice (for PDF generation) — `brew install --cask libreoffice`
- Roboto static fonts installed (Regular, Bold, Italic, BoldItalic)

### Install dependencies

```bash
pip install customtkinter anthropic pydantic python-docx docxtpl pdfplumber docx2pdf pillow requests
```

### Configuration

- **`config.json`** — Bullhorn and Instantly.ai API credentials (for Import Contacts and Mailshot Helper)
- **`cv_parse_format/cv_config.json`** — Anthropic API key and CV template settings

### Run

```bash
python CornerstoneTools.py
```

## Repository Structure

```
CornerstoneTools.py          # Main shell / launcher
config.json                  # Shared API credentials
cv_parse_format/             # CV Parse & Format tool
  cv_parse_format_tool.py
  cv_config.json
  templates/
  design/
import_contact/              # Import Contacts tool
  import_contact_tool.py
mailshot_helper/             # Mailshot Helper tool
  mailshot_helper_tool.py
```
