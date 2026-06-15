@echo off
REM Cornerstone Tools — Windows build script
REM Produces: dist\Cornerstone Tools.exe
REM Run from the repo root on a Windows machine with Python installed.

echo Installing build deps...
pip install pyinstaller pymupdf --quiet

echo Building Cornerstone Tools.exe...
pyinstaller ^
    --noconfirm ^
    --windowed ^
    --name "Cornerstone Tools" ^
    --add-data "cv_parse_format\templates;cv_parse_format\templates" ^
    --add-data "cv_parse_format\design;cv_parse_format\design" ^
    --add-data "cv_parse_format\cv_parse_format_tool.py;cv_parse_format" ^
    --add-data "import_contact\import_contact_tool.py;import_contact" ^
    --add-data "mailshot_helper\mailshot_helper_tool.py;mailshot_helper" ^
    --hidden-import customtkinter ^
    --hidden-import anthropic ^
    --hidden-import pydantic ^
    --hidden-import docx ^
    --hidden-import docxtpl ^
    --hidden-import pdfplumber ^
    --hidden-import docx2pdf ^
    --hidden-import PIL ^
    --hidden-import fitz ^
    --hidden-import requests ^
    CornerstoneTools.py

echo.
echo Build complete: dist\Cornerstone Tools.exe
echo.
echo To distribute: zip the .exe and upload to the GitHub release.
