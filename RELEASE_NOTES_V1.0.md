# CPS Tools — V1.0 Release Notes

**Release date:** 9 July 2026

---

## What's in V1.0

CPS Tools bundles three internal tools into a single desktop application for the Cornerstone Projects recruitment team.

| Tool | Version | What it does |
|------|---------|--------------|
| **CV Parse & Format** | V0.1 | Upload a candidate CV, parse it with Claude AI, review/edit, export a branded Cornerstone PDF |
| **Mailshot Helper** | V1.0 | Pull contact lists from Bullhorn, push to Instantly or Dripify email campaigns |
| **Import Contacts** | V2.0 | Load a CSV of contacts and bulk-import into Bullhorn CRM with deduplication |

---

## What's new since the last beta

### Shared team database (Supabase PostgreSQL)

CV profiles are now stored in a shared cloud database. Any team member who parses a CV can see it on anyone else's machine — no more emailing JSON files or keeping separate local copies.

- Primary storage: **Supabase PostgreSQL** (hosted, cloud, always-on)
- Fallback: Google Sheets → local JSON (in that order if Postgres is unreachable)
- Deduplication via file hash — uploading the same CV twice loads the existing record instead of re-parsing and spending credits

### Auto-save on "Continue to CV →"

If a parsed profile hasn't been saved yet and the user clicks "Continue to CV →", the profile is automatically saved to the database before navigating. No credits are wasted re-parsing CVs that were already processed.

### Settings panel with admin gate

A settings panel (⚙ gear icon) gives admins live access to all credentials and connection health checks:

- Bullhorn connection status (tests live auth)
- Anthropic API status (tests live API)
- Supabase PostgreSQL status (tests live connection)
- LibreOffice installation status with in-app installer
- Credential override panel (password-protected)

### Windows: Segoe UI font throughout

All three tools and the app shell now use **Segoe UI** on Windows — Microsoft's ClearType-optimised font — giving a much crisper UI appearance compared to the beta.

### Roboto fonts bundled for CV PDF output

The full Roboto font family is bundled with the app. LibreOffice is given the font path before every PDF conversion, so the output PDF matches the Word template exactly — no more fallback substitutions.

### macOS: SSL certificate fix for LibreOffice download

The in-app LibreOffice installer on macOS was failing with `SSL_CERTIFICATE_VERIFY_FAILED` in packaged builds. Fixed by creating a platform-appropriate SSL context for the download. Windows is unaffected (uses the OS certificate store).

### LibreOffice installer improvements

- **macOS**: Silent install to `~/Applications` — no password prompt
- **Windows**: Switched to MSI `/qn` silent mode with `CREATE_NO_WINDOW` — no CMD terminal popup during install. UAC prompts once as expected.
- **Windows detection**: Detection no longer spawns a subprocess (which could hang); checks for the executable file directly.

### UI consistency across all tools

- **Header bar height**: All three tools now use 58px — consistent across CV Parse, Mailshot Helper, and Import Contacts
- **Header font**: All tool titles use 17pt bold — matching across the whole app
- **Logo**: Removed the per-tool logo from Mailshot Helper and Import Contacts headers; the sidebar logo is sufficient
- **Sidebar tool order**: CV Parse & Format → Mailshot Helper → Import Contacts
- **Version label**: V1.0 shown at the bottom of the sidebar

### CV profile form UI improvements

- Consistent 32px side padding inside all card containers — elements no longer overflow the card's rounded corners
- Equal 50/50 column split on two-column paired rows (Name/Job Title, Location/County, etc.)
- Matched heading alignment with field content
- Balanced top/bottom padding — same breathing room on all sides

### Mailshot Helper filter panel fixes

- Filter panel rounded corners now visible on all four corners (previously the bottom corners were covered)
- Increased side padding — filter was too flush to the card edge
- Overlap artefacts on card corners eliminated (padding now exceeds `corner_radius`)

### Cross-platform robustness

All JSON and configuration file reads/writes now use `encoding="utf-8"` explicitly. Previously these defaulted to the system locale on Windows (often cp1252), which would corrupt non-ASCII characters in candidate names, addresses, and job titles.

---

## Known issues

| Issue | Workaround |
|-------|-----------|
| macOS: security warning on first open | Right-click → Open, then Privacy & Security → Open Anyway |
| Windows: SmartScreen on first run | Click More info → Run anyway |
| CV tool locked until LibreOffice installed | Click ⚙ gear → Install LibreOffice |
| Windows UAC prompt during LibreOffice install | Click Yes — expected, required for install |
| CV tool still locked after LibreOffice installs | Click ↺ refresh button in sidebar |

---

## Upgrading from the beta

No migration needed. The app reads from and writes to the shared Supabase database. Old local profile JSON files (from the beta) can be ignored — all current candidates are in the database.

---

## Installation

See the [GitHub release page](https://github.com/ajmorales/Cornerstone-Tool/releases/latest) for download links and per-platform installation instructions.
