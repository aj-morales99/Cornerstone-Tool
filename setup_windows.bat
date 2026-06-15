@echo off
REM Cornerstone Tools — Windows Setup
REM Run this once to install everything needed.

echo.
echo ============================================
echo   Cornerstone Tools — Windows Setup
echo ============================================
echo.

SET SCRIPT_DIR=%~dp0

REM ── 1. Python ────────────────────────────────────────────────────────────────
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [1/6] Installing Python 3...
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    REM Refresh PATH
    SET "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
) ELSE (
    echo [1/6] Python already installed ^✓
)

REM ── 2. Python packages ───────────────────────────────────────────────────────
echo [2/6] Installing Python packages...
python -m pip install --upgrade pip --quiet
python -m pip install customtkinter anthropic pydantic python-docx docxtpl pdfplumber docx2pdf pillow requests --quiet
echo       Python packages installed ^✓

REM ── 3. LibreOffice ───────────────────────────────────────────────────────────
IF NOT EXIST "C:\Program Files\LibreOffice\program\soffice.exe" (
    echo [3/6] Installing LibreOffice (this may take a few minutes)...
    winget install TheDocumentFoundation.LibreOffice --silent --accept-package-agreements --accept-source-agreements
) ELSE (
    echo [3/6] LibreOffice already installed ^✓
)

REM ── 4. Poppler (pdftoppm for CV preview) ─────────────────────────────────────
pdftoppm -v >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [4/6] Installing Poppler...
    winget install osdn.poppler --silent --accept-package-agreements --accept-source-agreements 2>nul
    IF %ERRORLEVEL% NEQ 0 (
        echo       Poppler not found in winget — downloading manually...
        powershell -Command "& { Invoke-WebRequest -Uri 'https://github.com/oscartools/poppler-windows/releases/latest/download/poppler-windows.zip' -OutFile '%TEMP%\poppler.zip'; Expand-Archive '%TEMP%\poppler.zip' -DestinationPath 'C:\poppler' -Force }"
        setx PATH "%PATH%;C:\poppler\bin" /M
        echo       Poppler installed to C:\poppler ^✓
    )
) ELSE (
    echo [4/6] Poppler already installed ^✓
)

REM ── 5. Roboto fonts ──────────────────────────────────────────────────────────
echo [5/6] Installing Roboto fonts...
SET FONTS_SRC=%SCRIPT_DIR%cv_parse_format\fonts
IF EXIST "%FONTS_SRC%" (
    FOR %%F IN ("%FONTS_SRC%\*.ttf") DO (
        copy /Y "%%F" "%LOCALAPPDATA%\Microsoft\Windows\Fonts\" >nul
    )
    echo       Roboto fonts installed ^✓
) ELSE (
    echo       fonts folder not found — skipping (app will fall back to Arial)
)

REM ── 6. Create launcher shortcut ──────────────────────────────────────────────
echo [6/6] Creating desktop shortcut...
powershell -Command "& { $ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Cornerstone Tools.lnk'); $s.TargetPath = 'python'; $s.Arguments = '\"%SCRIPT_DIR%CornerstoneTools.py\"'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = 'python.exe'; $s.Save() }"
echo       Shortcut created on Desktop ^✓

echo.
echo ============================================
echo   Setup complete!
echo.
echo   Fill in your credentials:
echo     config.json
echo     cv_parse_format\cv_config.json
echo.
echo   Then double-click "Cornerstone Tools" on your Desktop
echo   or run: python CornerstoneTools.py
echo ============================================
echo.

start "" "%SCRIPT_DIR%"
pause
