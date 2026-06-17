@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM Cornerstone Tools — Windows build script
REM Produces:  dist\Cornerstone Tools\  →  Cornerstone-Tools-Windows.zip
REM
REM Run from the repo root on a Windows machine with Python installed:
REM   build_windows.bat
REM
REM No code-signing certificate needed.
REM The version info metadata reduces Windows SmartScreen warnings.
REM If SmartScreen still appears: click "More info" then "Run anyway".
REM ─────────────────────────────────────────────────────────────────────────────

setlocal

set APP_NAME=Cornerstone Tools
set ZIP_NAME=Cornerstone-Tools-Windows.zip

echo.
echo ==========================================
echo   Installing build dependencies...
echo ==========================================
pip install pyinstaller pymupdf --quiet

echo.
echo ==========================================
echo   Building %APP_NAME%.exe...
echo ==========================================

pyinstaller ^
    --noconfirm ^
    --windowed ^
    --name "%APP_NAME%" ^
    --version-file version_info.txt ^
    ^
    --add-data "cv_parse_format\templates;cv_parse_format\templates" ^
    --add-data "cv_parse_format\design;cv_parse_format\design" ^
    --add-data "cv_parse_format\cv_parse_format_tool.py;cv_parse_format" ^
    --add-data "cv_parse_format\google_sheets_store.py;cv_parse_format" ^
    --add-data "cv_parse_format\google_drive_store.py;cv_parse_format" ^
    --add-data "import_contact\import_contact_tool.py;import_contact" ^
    --add-data "mailshot_helper\mailshot_helper_tool.py;mailshot_helper" ^
    ^
    --add-data "mailshot_helper\config.json;mailshot_helper" ^
    --add-data "cv_config.json;." ^
    --add-data "cv_parse_format\service-account-key.json;cv_parse_format" ^
    ^
    --hidden-import "customtkinter" ^
    --hidden-import "anthropic" ^
    --hidden-import "pydantic" ^
    --hidden-import "docx" ^
    --hidden-import "docxtpl" ^
    --hidden-import "pdfplumber" ^
    --hidden-import "docx2pdf" ^
    --hidden-import "PIL" ^
    --hidden-import "fitz" ^
    --hidden-import "requests" ^
    --hidden-import "google.oauth2.service_account" ^
    --hidden-import "google.auth.transport.requests" ^
    --hidden-import "googleapiclient.discovery" ^
    ^
    CornerstoneTools.py

echo.
echo ==========================================
echo   Zipping for distribution...
echo ==========================================

REM Use PowerShell to create the zip (available on all modern Windows)
powershell -Command "Compress-Archive -Path 'dist\%APP_NAME%' -DestinationPath '%ZIP_NAME%' -Force"

echo.
echo ==========================================
echo   Build complete: %ZIP_NAME%
echo ==========================================
echo.
echo   Upload %ZIP_NAME% to the GitHub release.
echo.
echo   Recipients: unzip and run "%APP_NAME%.exe" inside the folder.
echo   If SmartScreen appears: click "More info" ^> "Run anyway"
echo   This only happens on first run.
echo.
endlocal
