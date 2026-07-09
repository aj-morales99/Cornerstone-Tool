"""CPS Tools — multi-tool shell.
Each tool lives in its own module and exposes an embeddable CTkFrame.
"""

import json
import os
import sys
import threading

# ── Log file (windowed mode swallows stdout/stderr) ──────────────────────────
def _setup_log():
    if not getattr(sys, "frozen", False):
        return  # dev: keep console output
    if sys.platform == "win32":
        log_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                               "CPS Tools")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), "Library", "Logs", "CPS Tools")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")
    import builtins
    _log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file
    print(f"=== CPS Tools started ===", flush=True)

_setup_log()

# Windows: per-monitor DPI awareness — must be called before any window is created
if sys.platform == "win32":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

import customtkinter as ctk
from PIL import Image, ImageDraw

ctk.set_appearance_mode("light")


def _flat_icon(kind, color="#5a6472", size=24):
    """Draw a flat outline icon (supersampled for smooth anti-aliasing)."""
    S = 8
    W = size * S
    lw = int(1.8 * S)
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def E(*xy):
        return [v * S for v in xy]

    if kind == "candidate":
        d.ellipse(E(7.5, 3, 16.5, 12), outline=color, width=lw)
        d.arc(E(3.5, 13.5, 20.5, 30), 180, 360, fill=color, width=lw)
    elif kind == "upload":
        d.line(E(4, 15, 4, 19), fill=color, width=lw)
        d.line(E(4, 19, 20, 19), fill=color, width=lw)
        d.line(E(20, 15, 20, 19), fill=color, width=lw)
        d.line(E(12, 4, 12, 14), fill=color, width=lw)
        d.line(E(7.5, 8.5, 12, 4), fill=color, width=lw)
        d.line(E(12, 4, 16.5, 8.5), fill=color, width=lw)
    elif kind == "email":
        d.rectangle(E(3, 7, 21, 17), outline=color, width=lw)
        d.line(E(3, 7, 12, 13), fill=color, width=lw)
        d.line(E(12, 13, 21, 7), fill=color, width=lw)
    elif kind == "reload":
        # Circular refresh arrow
        d.arc(E(4, 4, 20, 20), 60, 340, fill=color, width=lw)
        # Arrowhead at ~60° (top-right)
        d.line(E(17, 3, 20, 6), fill=color, width=lw)
        d.line(E(20, 6, 17, 9), fill=color, width=lw)
    elif kind == "dots":
        # Three horizontal dots (settings)
        for cx in [7.5, 12, 16.5]:
            d.ellipse(E(cx - 1.6, 10.4, cx + 1.6, 13.6), fill=color)
    elif kind == "tools":
        import math
        cx, cy, r_in, r_out = 12, 12, 5.5, 9.0
        # Inner hub circle
        d.ellipse(E(cx - 2.8, cy - 2.8, cx + 2.8, cy + 2.8), outline=color, width=lw)
        # 6 teeth: draw the 3 outline segments per tooth (left side, top, right side)
        n = 6
        half = math.radians(14)   # half angular width of each tooth
        for i in range(n):
            a = math.radians(i * 360 / n)
            a1, a2 = a - half, a + half
            ix1 = cx + math.cos(a1) * r_in;  iy1 = cy + math.sin(a1) * r_in
            ix2 = cx + math.cos(a2) * r_in;  iy2 = cy + math.sin(a2) * r_in
            ox1 = cx + math.cos(a1) * r_out; oy1 = cy + math.sin(a1) * r_out
            ox2 = cx + math.cos(a2) * r_out; oy2 = cy + math.sin(a2) * r_out
            d.line([ix1 * S, iy1 * S, ox1 * S, oy1 * S], fill=color, width=lw)
            d.line([ox1 * S, oy1 * S, ox2 * S, oy2 * S], fill=color, width=lw)
            d.line([ox2 * S, oy2 * S, ix2 * S, iy2 * S], fill=color, width=lw)
        # Connect teeth with arcs along the inner ring
        for i in range(n):
            a_end   = math.degrees(i * 2 * math.pi / n - half)
            a_start = math.degrees((i - 1) * 2 * math.pi / n + half)
            d.arc(E(cx - r_in, cy - r_in, cx + r_in, cy + r_in),
                  a_start, a_end, fill=color, width=lw)
    im = im.resize((size, size), Image.LANCZOS)
    return im


def tool_icon(kind, active=False, size=24):
    return ctk.CTkImage(light_image=_flat_icon(kind, "#b8965a" if active else "#5a6472", size),
                        size=(size, size))


# Shell palette
GOLD, GOLD_HV = "#b8965a", "#a98549"
BG, CARD      = "#edeae3", "#ffffff"
SURFACE, HAIR = "#f4f2ec", "#e1dccf"
INK, MUTED    = "#2a2a2a", "#8d8779"
ORANGE        = "#bd7a1a"
GREEN         = "#2e8f4e"
RED           = "#bf4040"

_FF       = "Segoe UI" if sys.platform == "win32" else "Arial"
FONT_SM   = (_FF, 11)
FONT_BOLD = (_FF, 13, "bold")

# Add all tool directories to sys.path before importing
_SHELL_DIR = os.path.dirname(os.path.abspath(__file__))
for _folder in ("cv_parse_format", "import_contact", "mailshot_helper"):
    _td = os.path.join(_SHELL_DIR, _folder)
    if _td not in sys.path:
        sys.path.insert(0, _td)

# Static imports — PyInstaller follows these at build time.
from cv_parse_format_tool import CVParseFormatTool      # noqa: E402
from mailshot_helper_tool import MailshotHelperTool     # noqa: E402

# contact_tool / BullhornImportTool is loaded dynamically because PyInstaller's
# static analyser silently drops modules that trigger certain import side-effects
# (observed with any module that top-level imports pandas on CI runners).
# The .py source is bundled via --add-data and compiled at startup with importlib.
import importlib as _il
import importlib.util as _ilu

def _load_contact_tool():
    modname = "contact_tool"
    if modname in sys.modules:
        return sys.modules[modname]
    try:
        # Dev mode: import_contact/ is already in sys.path via the loop above
        return _il.import_module(modname)
    except ModuleNotFoundError:
        # Frozen mode: load from the --add-data bundled source file
        py = os.path.join(getattr(sys, "_MEIPASS", "."), "contact_tool.py")
        spec = _ilu.spec_from_file_location(modname, py)
        mod = _ilu.module_from_spec(spec)
        sys.modules[modname] = mod
        spec.loader.exec_module(mod)
        return mod

BullhornImportTool = _load_contact_tool().BullhornImportTool

TOOLS = [
    {"id": "cv",       "icon": "candidate", "label": "CV Parse & Format  V0.1",
     "folder": "cv_parse_format",  "module": "cv_parse_format_tool",  "cls": "CVParseFormatTool",  "cls_obj": CVParseFormatTool},
    {"id": "mailshot", "icon": "email",     "label": "Mailshot Helper  V1.0",
     "folder": "mailshot_helper",  "module": "mailshot_helper_tool",  "cls": "MailshotHelperTool", "cls_obj": MailshotHelperTool},
    {"id": "import",   "icon": "upload",    "label": "Import Contacts  V2.0",
     "folder": "import_contact",   "module": "contact_tool",          "cls": "BullhornImportTool", "cls_obj": BullhornImportTool},
]


class Shell(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Hide on Windows until fully built to avoid the white-flash on startup
        if sys.platform == "win32":
            self.withdraw()
        self.title("CPS Tools  V1.0")
        self.geometry("1380x880")
        self.minsize(1100, 720)
        self.configure(fg_color=BG)
        self._shell_dir = os.path.dirname(os.path.abspath(__file__))
        self._set_window_icon()
        self.frames   = {}
        self.buttons  = {}
        self.active   = None
        self.expanded = False
        self._lo_block = None          # LibreOffice-required overlay
        self._soffice  = None          # cached result: path or False
        self._soffice_checked = False  # False = not yet checked
        self._update_info = None
        try:
            self._build()
        finally:
            self.update_idletasks()
            # Always deiconify — even if _build raised, the window must appear
            if sys.platform == "win32":
                self.deiconify()
        # Show startup connection check — it will call show_tool when done
        self.after(120, self._show_startup_check)
        # Auto-refresh connections every 5 minutes
        self.after(300_000, self._schedule_refresh)
        # Check for a newer release in the background (5 s after boot)
        self.after(5_000, self._check_for_update)

    def _set_window_icon(self):
        """Set the title bar / taskbar icon on Windows and macOS."""
        try:
            meipass = getattr(sys, "_MEIPASS", None)
            base = meipass if meipass else self._shell_dir
            if sys.platform == "win32":
                ico = os.path.join(base, "logo.ico")
                if os.path.exists(ico):
                    self.iconbitmap(ico)
            else:
                png = os.path.join(base, "logo.png")
                if os.path.exists(png):
                    from PIL import ImageTk
                    _ico = ImageTk.PhotoImage(Image.open(png).resize((32, 32), Image.LANCZOS))
                    self.iconphoto(True, _ico)
                    self._icon_ref = _ico   # keep reference so GC doesn't collect it
        except Exception as e:
            print(f"[icon] {e}", flush=True)

    def _build(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0,
                                    border_width=1, border_color=HAIR, width=58)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkButton(self.sidebar, text="☰", width=42, height=36, fg_color="transparent",
                      hover_color=SURFACE, text_color=MUTED, font=FONT_BOLD,
                      command=self.toggle).pack(pady=(10, 14))

        self.icons = {t["id"]: {"idle":   tool_icon(t["icon"]),
                                "active": tool_icon(t["icon"], active=True)}
                      for t in TOOLS}
        for tool in TOOLS:
            b = ctk.CTkButton(self.sidebar, text="", image=self.icons[tool["id"]]["idle"],
                              width=42, height=42, corner_radius=10,
                              fg_color="transparent", hover_color=SURFACE,
                              text_color=INK, font=FONT_BOLD, anchor="center",
                              command=lambda t=tool["id"]: self.show_tool(t))
            b.pack(pady=3, padx=8, fill="x")
            self.buttons[tool["id"]] = b

        # Version label (small, muted)
        try:
            import updater as _upd
            _ver_text = f"v{_upd.get_current_version()}"
        except Exception:
            _ver_text = "v1.0"
        self._version_lbl = ctk.CTkLabel(
            self.sidebar, text=_ver_text, font=(_FF, 8), text_color=MUTED
        )
        self._version_lbl.pack(side="bottom", pady=(0, 6))

        # Update chip — hidden until a newer release is detected
        self._update_btn = ctk.CTkButton(
            self.sidebar, text="",
            font=ctk.CTkFont(_FF, 11, "bold"),
            fg_color=GOLD, hover_color=GOLD_HV, text_color="#ffffff",
            height=32, corner_radius=8,
            command=self._show_update_dialog,
        )
        # Packed dynamically in _on_update_found

        # Reload button pinned to sidebar bottom
        _reload_img = tool_icon("reload", size=20)
        self._reload_btn = ctk.CTkButton(
            self.sidebar, text="", image=_reload_img,
            width=42, height=42, corner_radius=10,
            fg_color="transparent", hover_color=SURFACE,
            command=lambda: self._reconnect_all(silent=False))
        self._reload_btn.pack(side="bottom", pady=(0, 10), padx=8)

        # Settings button — reuses the existing gear icon
        _tools_img = tool_icon("tools", size=20)
        self._settings_btn = ctk.CTkButton(
            self.sidebar, text="", image=_tools_img,
            width=42, height=42, corner_radius=10,
            fg_color="transparent", hover_color=SURFACE,
            command=self._open_settings_panel)
        self._settings_btn.pack(side="bottom", pady=(0, 2), padx=8)

        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

    # ── Dependency Manager ─────────────────────────────────────────────────────

    def _open_deps_panel(self):
        """Open the Required Tools window with background download + install."""
        import platform, tempfile, urllib.request, ssl
        from cv_parse_format_tool import _find_soffice, _find_word

        # macOS PyInstaller builds don't bundle system SSL certs, so urlopen
        # raises CERTIFICATE_VERIFY_FAILED. Windows uses the OS cert store and
        # works fine, so only disable verification on macOS.
        _ssl_ctx = ssl.create_default_context()
        if sys.platform == "darwin":
            _ssl_ctx.check_hostname = False
            _ssl_ctx.verify_mode = ssl.CERT_NONE

        def _get_lo_version():
            """Fetch the latest LibreOffice stable version from the download server."""
            import re
            try:
                with urllib.request.urlopen(
                        "https://download.documentfoundation.org/libreoffice/stable/",
                        timeout=10, context=_ssl_ctx) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                versions = re.findall(r'href="(\d+\.\d+\.\d+)/"', html)
                if versions:
                    return sorted(versions,
                                  key=lambda v: [int(x) for x in v.split(".")])[-1]
            except Exception as e:
                print(f"[deps] version fetch failed: {e}", flush=True)
            return "25.2.4"   # fallback if offline

        def _lo_url_and_name(v):
            if sys.platform == "darwin":
                arch = "aarch64" if platform.machine() == "arm64" else "x86-64"
                name = f"LibreOffice_{v}_MacOS_{arch}.dmg"
                url  = (f"https://download.documentfoundation.org/libreoffice/stable/"
                        f"{v}/mac/{arch}/{name}")
            elif sys.platform == "win32":
                name = f"LibreOffice_{v}_Win_x86-64.msi"
                url  = (f"https://download.documentfoundation.org/libreoffice/stable/"
                        f"{v}/win/x86_64/{name}")
            else:
                return None, None
            return url, name

        # Determine whether Word covers PDF export (Windows only)
        word_found  = _find_word() if sys.platform == "win32" else False
        lo_optional = sys.platform == "win32" and bool(word_found)

        WW, WH = 520, (430 if sys.platform == "win32" else 340)
        win = ctk.CTkToplevel(self)
        win.title("PDF Tools")
        win.resizable(False, False)
        win.configure(fg_color=BG)
        self.update_idletasks()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        win.geometry(f"{WW}x{WH}+{px + (pw - WW)//2}+{py + (ph - WH)//2}")
        win.grab_set()
        win.lift()
        win.focus_force()

        ctk.CTkLabel(win, text="PDF Tools",
                     font=ctk.CTkFont(_FF, 16, "bold"),
                     text_color=INK).pack(pady=(22, 2), padx=28, anchor="w")
        ctk.CTkLabel(win,
                     text=("Microsoft Word detected — LibreOffice is optional."
                           if lo_optional else
                           "Applications needed for PDF export and CV formatting."),
                     font=FONT_SM, text_color=MUTED).pack(padx=28, anchor="w")
        ctk.CTkFrame(win, fg_color=HAIR, height=1).pack(fill="x", padx=20, pady=(12, 0))

        # ── Microsoft Word card (Windows only) ──
        if sys.platform == "win32":
            word_card = ctk.CTkFrame(win, fg_color=CARD, corner_radius=12,
                                     border_width=1, border_color=HAIR)
            word_card.pack(fill="x", padx=20, pady=(0, 6))
            wr = ctk.CTkFrame(word_card, fg_color="transparent")
            wr.pack(fill="x", padx=16, pady=(14, 4))
            ctk.CTkLabel(wr, text="Microsoft Word", font=FONT_BOLD,
                         text_color=INK, anchor="w").pack(side="left")
            word_status = ctk.CTkLabel(
                wr,
                text=("✓  Available" if word_found else "✗  Not found"),
                font=FONT_SM,
                text_color=(GREEN if word_found else MUTED),
                anchor="e")
            word_status.pack(side="right")
            ctk.CTkLabel(word_card,
                         text="PDF export  ·  CV formatting  ·  Document parsing",
                         font=FONT_SM, text_color=MUTED, anchor="w").pack(padx=16, anchor="w")
            hint = ("Active — being used for PDF export." if word_found else
                    "Not found — install Microsoft Office, or use LibreOffice below.")
            ctk.CTkLabel(word_card, text=hint,
                         font=FONT_SM, text_color=(GREEN if word_found else MUTED),
                         anchor="w").pack(padx=16, pady=(2, 12), anchor="w")

        # ── LibreOffice card ──
        if lo_optional:
            lo_title_text = "LibreOffice  (Optional)"
            lo_desc_text  = ("Optional — Microsoft Word is handling PDF export. "
                             "Install LibreOffice if you want it as a backup.")
        elif sys.platform == "darwin":
            lo_title_text = "LibreOffice  (Required)"
            lo_desc_text  = "Required for PDF export and CV formatting on macOS."
        else:
            lo_title_text = "LibreOffice  (Recommended)"
            lo_desc_text  = ("Recommended — Microsoft Office not found. "
                             "Install LibreOffice to enable PDF export.")

        card = ctk.CTkFrame(win, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=HAIR)
        card.pack(fill="x", padx=20, pady=(0, 12))

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(top_row, text=lo_title_text, font=FONT_BOLD,
                     text_color=INK, anchor="w").pack(side="left")

        status_lbl = ctk.CTkLabel(top_row, text="", font=FONT_SM, anchor="e")
        status_lbl.pack(side="right")

        ctk.CTkLabel(card, text=lo_desc_text,
                     font=FONT_SM, text_color=MUTED, anchor="w").pack(padx=16, anchor="w")

        # Progress area (hidden until install starts)
        prog_frame = ctk.CTkFrame(card, fg_color="transparent")
        prog_bar   = ctk.CTkProgressBar(prog_frame, width=340, height=10,
                                        fg_color=SURFACE, progress_color=GOLD)
        prog_bar.set(0)
        prog_bar.pack(fill="x", padx=0, pady=(6, 2))
        prog_lbl = ctk.CTkLabel(prog_frame, text="", font=FONT_SM, text_color=MUTED)
        prog_lbl.pack(anchor="w")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(8, 14))

        install_btn = ctk.CTkButton(btn_row, text="Install", width=90, height=32,
                                    fg_color=GOLD, hover_color=GOLD_HV,
                                    text_color="#ffffff", font=FONT_BOLD, corner_radius=8)
        cancel_btn  = ctk.CTkButton(btn_row, text="Cancel",  width=80, height=32,
                                    fg_color=SURFACE, hover_color=HAIR,
                                    text_color=INK, font=FONT_SM, corner_radius=8)

        close_btn = ctk.CTkButton(win, text="Close", width=100, height=34, corner_radius=8,
                                  fg_color=SURFACE, hover_color=HAIR, text_color=INK,
                                  font=FONT_BOLD, command=win.destroy)
        close_btn.pack(pady=(0, 20))

        _cancel_flag = [False]

        def _set_status(text, color=MUTED):
            status_lbl.configure(text=text, text_color=color)

        def _set_progress(fraction, msg):
            prog_bar.set(max(0.0, min(1.0, fraction)))
            prog_lbl.configure(text=msg)
            win.update_idletasks()

        def _show_progress():
            prog_frame.pack(fill="x", padx=16, pady=(4, 0))

        def _hide_install_btn():
            install_btn.pack_forget()
            cancel_btn.pack(side="left")

        def _install_macos(dmg_path):
            import subprocess, glob
            _set_progress(0.0, "Mounting installer…")
            r = subprocess.run(["hdiutil", "attach", "-quiet", "-noverify",
                                 "-nobrowse", dmg_path],
                                capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"Could not mount installer:\n{r.stderr.strip()}")
            # Find the mounted volume
            vols = glob.glob("/Volumes/LibreOffice*")
            if not vols:
                raise RuntimeError("Could not find mounted LibreOffice volume.")
            vol = vols[0]
            app_src = os.path.join(vol, "LibreOffice.app")
            dst_dir = os.path.expanduser("~/Applications")
            os.makedirs(dst_dir, exist_ok=True)
            _set_progress(0.85, "Copying to ~/Applications…  (this takes ~30 seconds)")
            r2 = subprocess.run(["cp", "-R", app_src, dst_dir], capture_output=True)
            subprocess.run(["hdiutil", "detach", vol, "-quiet"], capture_output=True)
            if r2.returncode != 0:
                raise RuntimeError(f"Copy failed:\n{r2.stderr.decode().strip()}")

        def _install_windows(msi_path):
            import subprocess
            _set_progress(0.85,
                "Installing…  Approve the User Account Control prompt if it appears.")
            kw = {}
            try:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0          # SW_HIDE
                kw["startupinfo"] = si
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            except Exception:
                pass
            r = subprocess.run(
                ["msiexec", "/i", msi_path, "/passive", "/norestart"],
                **kw)
            # 0 = success, 3010 = success + restart recommended, 1641 = restart initiated
            if r.returncode not in (0, 3010, 1641):
                raise RuntimeError(
                    f"Installer exited with code {r.returncode}.\n"
                    "Try running the installer manually from your Downloads folder.")

        def _do_install():
            win.after(0, lambda: _set_progress(0, "Looking up latest version…"))
            v = _get_lo_version()
            url, fname = _lo_url_and_name(v)
            if not url:
                win.after(0, lambda: _set_status("Not supported on this OS", "#bf4040"))
                return

            tmp_dir  = tempfile.mkdtemp()
            tmp_file = os.path.join(tmp_dir, fname)

            # ── Download ──
            try:
                win.after(0, lambda: _set_status("Downloading…", ORANGE))
                win.after(0, _show_progress)

                req = urllib.request.urlopen(url, timeout=30, context=_ssl_ctx)
                total = int(req.headers.get("Content-Length", 0))
                done  = 0
                chunk = 1024 * 64

                with open(tmp_file, "wb") as fh:
                    while True:
                        if _cancel_flag[0]:
                            win.after(0, lambda: _set_status("Cancelled", MUTED))
                            win.after(0, lambda: _set_progress(0, ""))
                            return
                        data = req.read(chunk)
                        if not data:
                            break
                        fh.write(data)
                        done += len(data)
                        if total:
                            pct = done / total
                            mb  = done / 1_048_576
                            tot = total / 1_048_576
                            msg = f"Downloading…  {mb:.0f} MB / {tot:.0f} MB"
                        else:
                            mb  = done / 1_048_576
                            msg = f"Downloading…  {mb:.0f} MB"
                            pct = 0.5
                        win.after(0, lambda p=pct, m=msg: _set_progress(p, m))

            except Exception as e:
                err = str(e)
                win.after(0, lambda: _set_status("Download failed", "#bf4040"))
                win.after(0, lambda: _set_progress(0, err[:80]))
                return

            if _cancel_flag[0]:
                win.after(0, lambda: _set_status("Cancelled", MUTED))
                return

            # ── Install ──
            win.after(0, lambda: _set_status("Installing…", ORANGE))
            try:
                if sys.platform == "darwin":
                    _install_macos(tmp_file)
                elif sys.platform == "win32":
                    _install_windows(tmp_file)
            except Exception as e:
                err = str(e)
                win.after(0, lambda: _set_status("Installation failed", "#bf4040"))
                win.after(0, lambda: _set_progress(1.0, err[:120]))
                return
            finally:
                try:
                    import shutil; shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

            def _on_done():
                _set_status("✓  Installed", GREEN)
                _set_progress(1.0,
                    "Done! Click the refresh (↺) button in the sidebar to load the CV tool.")
                cancel_btn.configure(text="Close", command=win.destroy)
                # Invalidate cached soffice result so next show_tool("cv") re-checks
                self.invalidate_soffice()
                self._hide_lo_block()
            win.after(0, _on_done)

        def _start_install():
            _cancel_flag[0] = False
            win.after(0, _hide_install_btn)
            threading.Thread(target=_do_install, daemon=True).start()

        install_btn.configure(command=_start_install)
        cancel_btn.configure(command=lambda: _cancel_flag.__setitem__(0, True))

        # ── Populate initial state ──
        soffice = _find_soffice()
        if soffice:
            _set_status("✓  Installed", GREEN)
        else:
            if lo_optional:
                _set_status("–  Not installed  (optional)", MUTED)
            else:
                _set_status("✗  Not installed", RED)
            if sys.platform in ("darwin", "win32"):
                install_btn.pack(side="left")

    # ── Settings Panel ─────────────────────────────────────────────────────────

    def _open_settings_panel(self):
        """Settings panel — page-navigation style."""
        import threading, urllib.parse, requests as _req, hashlib as _hl, hmac as _hm

        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.resizable(True, True)
        win.configure(fg_color=BG)
        win.withdraw()
        win.update_idletasks()
        _sw, _sh = 430, 340
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{_sw}x{_sh}+{(sw - _sw)//2}+{(sh - _sh)//2}")
        win.deiconify()
        win.minsize(380, 200)
        win.grab_set()
        win.lift()
        win.focus_force()

        cfg = self._load_credentials()
        _GATE_HASH = "c424c114ad53ad95c487c26a639183c2bbfeed2fdec8f0f9961195cfcb3c319a"

        root_frame = ctk.CTkFrame(win, fg_color=BG, corner_radius=0)
        root_frame.pack(fill="both", expand=True)
        _active_page = [None]

        def _clear_page():
            if _active_page[0]:
                _active_page[0].destroy()
                _active_page[0] = None

        def _resize(w, h):
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

        def _scroll_page(h):
            page = ctk.CTkFrame(root_frame, fg_color=BG, corner_radius=0)
            page.pack(fill="both", expand=True, padx=20, pady=(16, 20))
            _active_page[0] = page
            _resize(430, h)
            return page

        # ── Back-button header ───────────────────────────────────────────────────
        def _back_header(parent, title):
            hdr = ctk.CTkFrame(parent, fg_color="transparent")
            hdr.pack(fill="x", pady=(0, 14))
            ctk.CTkButton(hdr, text="← Back", width=72, height=28,
                          fg_color=SURFACE, hover_color=HAIR,
                          text_color=INK, border_width=1, border_color=HAIR,
                          font=ctk.CTkFont(_FF, 12),
                          command=_show_main).pack(side="left")
            ctk.CTkLabel(hdr, text=title,
                         font=ctk.CTkFont(_FF, 14, "bold"),
                         text_color=INK).pack(side="left", padx=(12, 0))

        # ── Main menu ────────────────────────────────────────────────────────────
        def _show_main():
            _clear_page()
            _resize(430, 365)
            page = ctk.CTkFrame(root_frame, fg_color=BG, corner_radius=0)
            page.pack(fill="both", expand=True, padx=20, pady=(16, 20))
            _active_page[0] = page

            ctk.CTkLabel(page, text="Settings",
                         font=ctk.CTkFont(_FF, 15, "bold"),
                         text_color=INK).pack(anchor="w", pady=(0, 10))

            def _nav_card(title, subtitle, on_click):
                card = ctk.CTkFrame(page, fg_color=CARD, corner_radius=10)
                card.pack(fill="x", pady=(0, 10))
                inner = ctk.CTkFrame(card, fg_color="transparent")
                inner.pack(fill="x", padx=16, pady=13)
                inner.columnconfigure(0, weight=1)
                ctk.CTkLabel(inner, text=title,
                             font=ctk.CTkFont(_FF, 13, "bold"),
                             text_color=INK, anchor="w").grid(row=0, column=0, sticky="w")
                ctk.CTkLabel(inner, text=subtitle,
                             font=ctk.CTkFont(_FF, 11),
                             text_color=MUTED, anchor="w").grid(row=1, column=0, sticky="w")
                ctk.CTkLabel(inner, text="›",
                             font=ctk.CTkFont(_FF, 20, "bold"),
                             text_color=MUTED).grid(row=0, column=1, rowspan=2, padx=(8, 0))
                def _bind(w):
                    w.bind("<Button-1>", lambda e: on_click())
                    try: w.configure(cursor="hand2")
                    except Exception: pass
                for w in [card, inner] + list(inner.winfo_children()):
                    _bind(w)

            _nav_card("Credentials",
                      "Bullhorn & Instantly credentials",
                      _show_credentials_gate)
            _nav_card("Modify Database Lists",
                      "Manage lookup list values",
                      _show_db_lists_gate)
            _nav_card("Install Tools",
                      "LibreOffice & required dependencies",
                      lambda: (win.grab_release(), self._open_deps_panel(), win.grab_set()))

        # ── Credentials — admin gate then edit ───────────────────────────────────
        def _show_credentials_gate():
            _clear_page()
            _resize(430, 300)
            page = ctk.CTkFrame(root_frame, fg_color=BG, corner_radius=0)
            page.pack(fill="both", expand=True, padx=28, pady=24)
            _active_page[0] = page

            _back_header(page, "Credentials")

            ctk.CTkLabel(page, text="Admin login required to edit credentials.",
                         font=ctk.CTkFont(_FF, 12), text_color=MUTED).pack(pady=(0, 14))

            _u = ctk.StringVar()
            _p = ctk.StringVar()
            ctk.CTkLabel(page, text="Username", font=ctk.CTkFont(_FF, 11),
                         text_color=MUTED, anchor="w").pack(fill="x")
            ctk.CTkEntry(page, textvariable=_u, width=320,
                         fg_color=SURFACE, border_color=HAIR, text_color=INK,
                         font=ctk.CTkFont(_FF, 12)).pack(pady=(3, 8))
            ctk.CTkLabel(page, text="Password", font=ctk.CTkFont(_FF, 11),
                         text_color=MUTED, anchor="w").pack(fill="x")
            ctk.CTkEntry(page, textvariable=_p, show="*", width=320,
                         fg_color=SURFACE, border_color=HAIR, text_color=INK,
                         font=ctk.CTkFont(_FF, 12)).pack(pady=(3, 10))
            _err = ctk.CTkLabel(page, text="", font=ctk.CTkFont(_FF, 11), text_color=RED)
            _err.pack()

            def _check():
                h = _hl.sha256(f"{_u.get()}:{_p.get()}".encode()).hexdigest()
                if _hm.compare_digest(h, _GATE_HASH):
                    _show_req_tools()
                else:
                    _err.configure(text="Incorrect credentials.")

            ctk.CTkButton(page, text="Login", fg_color=INK, text_color=BG,
                          font=ctk.CTkFont(_FF, 13, "bold"),
                          command=_check).pack(pady=(6, 0))
            win.bind("<Return>", lambda _e: _check())

        def _show_db_lists_gate():
            _clear_page()
            _resize(430, 300)
            page = ctk.CTkFrame(root_frame, fg_color=BG, corner_radius=0)
            page.pack(fill="both", expand=True, padx=28, pady=24)
            _active_page[0] = page

            _back_header(page, "Modify Database Lists")

            ctk.CTkLabel(page, text="Admin login required to modify lists.",
                         font=ctk.CTkFont(_FF, 12), text_color=MUTED).pack(pady=(0, 14))

            _u = ctk.StringVar()
            _p = ctk.StringVar()
            ctk.CTkLabel(page, text="Username", font=ctk.CTkFont(_FF, 11),
                         text_color=MUTED, anchor="w").pack(fill="x")
            ctk.CTkEntry(page, textvariable=_u, width=320,
                         fg_color=SURFACE, border_color=HAIR, text_color=INK,
                         font=ctk.CTkFont(_FF, 12)).pack(pady=(3, 8))
            ctk.CTkLabel(page, text="Password", font=ctk.CTkFont(_FF, 11),
                         text_color=MUTED, anchor="w").pack(fill="x")
            ctk.CTkEntry(page, textvariable=_p, show="*", width=320,
                         fg_color=SURFACE, border_color=HAIR, text_color=INK,
                         font=ctk.CTkFont(_FF, 12)).pack(pady=(3, 10))
            _err = ctk.CTkLabel(page, text="", font=ctk.CTkFont(_FF, 11), text_color=RED)
            _err.pack()

            def _check():
                h = _hl.sha256(f"{_u.get()}:{_p.get()}".encode()).hexdigest()
                if _hm.compare_digest(h, _GATE_HASH):
                    _show_db_lists()
                else:
                    _err.configure(text="Incorrect credentials.")

            ctk.CTkButton(page, text="Login", fg_color=INK, text_color=BG,
                          font=ctk.CTkFont(_FF, 13, "bold"),
                          command=_check).pack(pady=(6, 0))
            win.bind("<Return>", lambda _e: _check())

        def _show_req_tools():
            _clear_page()
            win.unbind("<Return>")
            outer = _scroll_page(500)
            _back_header(outer, "Credentials")

            def _make_section(parent, title, fields, verify_fn, save_keys):
                card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10)
                card.pack(fill="x", pady=(0, 10))
                header = ctk.CTkFrame(card, fg_color="transparent")
                header.pack(fill="x", padx=14, pady=10)
                header.columnconfigure(0, weight=1)
                _title_lbl = ctk.CTkLabel(header, text=f"▶  {title}",
                                          font=ctk.CTkFont(_FF, 13, "bold"),
                                          text_color=INK, anchor="w")
                _title_lbl.grid(row=0, column=0, sticky="w")
                _status_var = ctk.StringVar(value="")
                _status_lbl = ctk.CTkLabel(header, textvariable=_status_var,
                                           font=ctk.CTkFont(_FF, 12),
                                           text_color=MUTED, anchor="e")
                _status_lbl.grid(row=0, column=1, sticky="e")
                body = ctk.CTkFrame(card, fg_color="transparent")
                ctk.CTkFrame(body, height=1, fg_color=HAIR).pack(fill="x", padx=14, pady=(0, 10))
                vars_ = {}
                entries = {}
                for label, key, show_ch in fields:
                    ctk.CTkLabel(body, text=label, font=ctk.CTkFont(_FF, 11),
                                 text_color=MUTED, anchor="w").pack(fill="x", padx=14)
                    v = ctk.StringVar(value=cfg.get(key, ""))
                    e = ctk.CTkEntry(body, textvariable=v, width=330,
                                     fg_color=SURFACE, border_color=HAIR,
                                     text_color=INK, font=ctk.CTkFont(_FF, 12),
                                     state="disabled",
                                     show=show_ch if show_ch else "")
                    e.pack(padx=14, pady=(3, 10))
                    vars_[key] = v
                    entries[key] = e
                _msg = ctk.CTkLabel(body, text="", font=ctk.CTkFont(_FF, 11),
                                    text_color=MUTED, wraplength=330)
                _msg.pack(padx=14, pady=(0, 4))
                btn_row = ctk.CTkFrame(body, fg_color="transparent")
                btn_row.pack(padx=14, pady=(0, 12))
                _edit_btn   = ctk.CTkButton(btn_row, text="Edit",   width=80, height=30,
                                            fg_color=SURFACE, hover_color=HAIR,
                                            text_color=INK, border_width=1, border_color=HAIR,
                                            font=ctk.CTkFont(_FF, 12))
                _save_btn   = ctk.CTkButton(btn_row, text="Save",   width=80, height=30,
                                            fg_color=INK, text_color=BG,
                                            font=ctk.CTkFont(_FF, 12, "bold"))
                _cancel_btn = ctk.CTkButton(btn_row, text="Cancel", width=80, height=30,
                                            fg_color=SURFACE, hover_color=HAIR,
                                            text_color=INK, border_width=1, border_color=HAIR,
                                            font=ctk.CTkFont(_FF, 12))
                _orig = {}
                def _enter_edit():
                    _orig.clear()
                    for key, v in vars_.items():
                        _orig[key] = v.get()
                        entries[key].configure(state="normal", fg_color="#ffffff",
                                               show="" if entries[key].cget("show") == "" else "*")
                    _msg.configure(text="")
                    _edit_btn.pack_forget()
                    _cancel_btn.pack(side="left", padx=(0, 6))
                    _save_btn.pack(side="left")
                def _do_cancel():
                    for key, v in vars_.items():
                        v.set(_orig.get(key, ""))
                        entries[key].configure(state="disabled", fg_color=SURFACE)
                    _cancel_btn.pack_forget(); _save_btn.pack_forget()
                    _edit_btn.pack(side="left"); _msg.configure(text="")
                def _do_save():
                    values = {k: v.get().strip() for k, v in vars_.items()}
                    _msg.configure(text="Verifying…", text_color=MUTED)
                    _save_btn.configure(state="disabled")
                    _cancel_btn.configure(state="disabled")
                    def _run():
                        ok, msg = verify_fn(values)
                        def _update():
                            _msg.configure(text=msg, text_color=GREEN if ok else RED)
                            _save_btn.configure(state="normal")
                            _cancel_btn.configure(state="normal")
                            if ok:
                                self._save_credentials(**{k: values[k] for k in save_keys})
                                for key in vars_:
                                    entries[key].configure(state="disabled", fg_color=SURFACE)
                                _cancel_btn.pack_forget(); _save_btn.pack_forget()
                                _edit_btn.pack(side="left")
                                _status_var.set("● Connected")
                                _status_lbl.configure(text_color=GREEN)
                        win.after(0, _update)
                    threading.Thread(target=_run, daemon=True).start()
                _edit_btn.configure(command=_enter_edit)
                _save_btn.configure(command=_do_save)
                _cancel_btn.configure(command=_do_cancel)
                _edit_btn.pack(side="left")
                _expanded = [False]
                def _toggle(e=None):
                    if _expanded[0]:
                        body.pack_forget()
                        _title_lbl.configure(text=f"▶  {title}")
                        _expanded[0] = False
                    else:
                        body.pack(fill="x")
                        _title_lbl.configure(text=f"▼  {title}")
                        _expanded[0] = True
                header.bind("<Button-1>", _toggle)
                _title_lbl.bind("<Button-1>", _toggle)

            def _verify_bullhorn(vals):
                try:
                    cfg_root = self._load_credentials()
                    cid  = cfg_root.get("bullhorn_client_id", "")
                    redir = cfg_root.get("bullhorn_redirect_uri", "https://welcome.bullhornstaffing.com")
                    if not cid:
                        return False, "✗ Bullhorn client ID not configured."
                    pw_enc = urllib.parse.quote(vals.get("bullhorn_password", ""), safe="")
                    url = (f"https://auth-emea.bullhornstaffing.com/oauth/authorize"
                           f"?client_id={cid}&response_type=code&action=Login"
                           f"&username={vals.get('bullhorn_username','')}&password={pw_enc}&redirect_uri={redir}")
                    resp = _req.Session().get(url, allow_redirects=True, timeout=12)
                    if "code=" in resp.url:
                        return True, "✓ Connected to Bullhorn successfully."
                    return False, "✗ Could not authenticate. Check username/password."
                except Exception as ex:
                    return False, f"✗ Error: {ex}"

            def _verify_instantly(vals):
                try:
                    r = _req.get("https://api.instantly.ai/api/v2/accounts/list",
                                 headers={"Authorization": f"Bearer {vals.get('instantly_api_key','')}",
                                          "Content-Type": "application/json"},
                                 params={"limit": 1}, timeout=10)
                    if r.status_code == 200:
                        return True, "✓ Instantly API key is valid."
                    return False, f"✗ API returned {r.status_code}."
                except Exception as ex:
                    return False, f"✗ Error: {ex}"

            _make_section(outer, "Bullhorn",
                          fields=[("Username", "bullhorn_username", None),
                                  ("Password", "bullhorn_password", "*")],
                          verify_fn=_verify_bullhorn,
                          save_keys=["bullhorn_username", "bullhorn_password"])
            _make_section(outer, "Instantly",
                          fields=[("API Key", "instantly_api_key", "*")],
                          verify_fn=_verify_instantly,
                          save_keys=["instantly_api_key"])

        # ── Modify Database Lists page ───────────────────────────────────────────
        def _show_db_lists():
            _clear_page()
            win.unbind("<Return>")
            outer = _scroll_page(620)
            _back_header(outer, "Modify Database Lists")

            LIST_OPTIONS = [
                ("Custom Industry",  "custom_industry"),
                ("Custom County",    "custom_county"),
                ("Type of Work",     "type_of_work"),
                ("Address State",    "address_state"),
            ]

            def _get_db_conn():
                p = self._find_cv_config()
                if not p: return None
                try:
                    with open(p, encoding="utf-8") as f: _cfg = json.load(f)
                    from turso_store import from_config as _tc
                    store = _tc(_cfg)
                    return store._get_client() if store else None
                except Exception: return None

            sel_row = ctk.CTkFrame(outer, fg_color="transparent")
            sel_row.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(sel_row, text="List:", font=ctk.CTkFont(_FF, 12),
                         text_color=INK, width=36, anchor="w").pack(side="left")
            _sel_var = ctk.StringVar(value=LIST_OPTIONS[0][0])
            _list_name_var = [LIST_OPTIONS[0][1]]

            def _on_list_sel(choice):
                for label, name in LIST_OPTIONS:
                    if label == choice:
                        _list_name_var[0] = name
                        break
                _refresh_list()

            ctk.CTkOptionMenu(sel_row, variable=_sel_var,
                              values=[o[0] for o in LIST_OPTIONS],
                              fg_color=SURFACE, button_color=HAIR,
                              button_hover_color=HAIR, text_color=INK,
                              dropdown_fg_color=CARD, dropdown_text_color=INK,
                              font=ctk.CTkFont(_FF, 12), width=240,
                              command=_on_list_sel).pack(side="left", padx=(6, 0))

            add_row = ctk.CTkFrame(outer, fg_color="transparent")
            add_row.pack(fill="x", pady=(0, 4))
            _new_var = ctk.StringVar()
            ctk.CTkEntry(add_row, textvariable=_new_var, width=240,
                         placeholder_text="New value…",
                         fg_color=SURFACE, border_color=HAIR,
                         text_color=INK, font=ctk.CTkFont(_FF, 12)).pack(side="left")

            _db_status = ctk.StringVar()
            _db_status_lbl = ctk.CTkLabel(outer, textvariable=_db_status,
                                          font=ctk.CTkFont(_FF, 11),
                                          text_color=MUTED, anchor="w")
            _db_status_lbl.pack(fill="x", pady=(2, 6))

            ctk.CTkFrame(outer, height=1, fg_color=HAIR).pack(fill="x", pady=(0, 6))
            _list_frame = ctk.CTkScrollableFrame(
                outer, fg_color="transparent", height=400, corner_radius=0,
                scrollbar_fg_color=BG,
                scrollbar_button_color=BG,
                scrollbar_button_hover_color=BG)
            _list_frame.pack(fill="x", pady=(0, 4))

            def _refresh_list():
                for w in _list_frame.winfo_children():
                    w.destroy()
                _db_status.set("Loading…")
                _db_status_lbl.configure(text_color=MUTED)
                def _fetch():
                    conn = _get_db_conn()
                    if not conn:
                        win.after(0, lambda: (_db_status.set("✗ Database unavailable"),
                                              _db_status_lbl.configure(text_color=RED)))
                        return
                    try:
                        rs = conn.execute(
                            "SELECT value FROM lookup_lists"
                            " WHERE list_name = ? AND active = 1"
                            " ORDER BY sort_order, value",
                            [_list_name_var[0]],
                        )
                        rows = [r[0] for r in rs.rows]
                        win.after(0, lambda r=rows: _populate_list(r))
                    except Exception as ex:
                        win.after(0, lambda: (_db_status.set(f"✗ {ex}"),
                                              _db_status_lbl.configure(text_color=RED)))
                threading.Thread(target=_fetch, daemon=True).start()

            def _populate_list(values):
                for w in _list_frame.winfo_children():
                    w.destroy()
                _db_status.set(f"{len(values)} value{'s' if len(values) != 1 else ''}")
                _db_status_lbl.configure(text_color=MUTED)
                for val in values:
                    row = ctk.CTkFrame(_list_frame, fg_color="transparent")
                    row.pack(fill="x", pady=1)
                    ctk.CTkLabel(row, text=val, font=ctk.CTkFont(_FF, 12),
                                 text_color=INK, anchor="w").pack(side="left", fill="x", expand=True)
                    ctk.CTkButton(row, text="✕", width=28, height=24,
                                  fg_color=SURFACE, hover_color="#fce8e8",
                                  text_color=RED, border_width=1, border_color=HAIR,
                                  font=ctk.CTkFont(_FF, 11, "bold"),
                                  command=lambda v=val: _delete_value(v)).pack(side="right")

            def _add_value():
                import tkinter.messagebox as _mb
                val = _new_var.get().strip()
                if not val: return
                if not _mb.askyesno("Confirm Add",
                                    f'Add "{val}" to {_sel_var.get()}?',
                                    parent=win): return
                _db_status.set("Adding…")
                _db_status_lbl.configure(text_color=MUTED)
                def _do():
                    conn = _get_db_conn()
                    if not conn:
                        win.after(0, lambda: (_db_status.set("✗ Database unavailable"),
                                              _db_status_lbl.configure(text_color=RED)))
                        return
                    try:
                        exists = conn.execute(
                            "SELECT 1 FROM lookup_lists WHERE list_name = ? AND value = ?",
                            [_list_name_var[0], val],
                        ).rows
                        if exists:
                            win.after(0, lambda: (_db_status.set(f'"{val}" already exists'),
                                                  _db_status_lbl.configure(text_color=RED)))
                        else:
                            conn.execute(
                                "INSERT INTO lookup_lists (list_name, value, active, sort_order)"
                                " VALUES (?, ?, 1, 0)",
                                [_list_name_var[0], val],
                            )
                            try:
                                import lookup_store as _ls; _ls.refresh(_list_name_var[0])
                            except Exception: pass
                            win.after(0, lambda: (_new_var.set(""), _refresh_list()))
                    except Exception as ex:
                        win.after(0, lambda: (_db_status.set(f"✗ {ex}"),
                                              _db_status_lbl.configure(text_color=RED)))
                threading.Thread(target=_do, daemon=True).start()

            def _delete_value(val):
                import tkinter.messagebox as _mb
                if not _mb.askyesno("Confirm Delete",
                                    f'Remove "{val}" from {_sel_var.get()}?\nThis cannot be undone.',
                                    parent=win): return
                _db_status.set(f'Deleting "{val}"…')
                _db_status_lbl.configure(text_color=MUTED)
                def _do():
                    conn = _get_db_conn()
                    if not conn:
                        win.after(0, lambda: (_db_status.set("✗ Database unavailable"),
                                              _db_status_lbl.configure(text_color=RED)))
                        return
                    try:
                        conn.execute(
                            "DELETE FROM lookup_lists WHERE list_name = ? AND value = ?",
                            [_list_name_var[0], val],
                        )
                        try:
                            import lookup_store as _ls; _ls.refresh(_list_name_var[0])
                        except Exception: pass
                        win.after(0, _refresh_list)
                    except Exception as ex:
                        win.after(0, lambda: (_db_status.set(f"✗ {ex}"),
                                              _db_status_lbl.configure(text_color=RED)))
                threading.Thread(target=_do, daemon=True).start()

            ctk.CTkButton(add_row, text="Add", width=60, height=30,
                          fg_color=INK, text_color=BG,
                          font=ctk.CTkFont(_FF, 12, "bold"),
                          command=_add_value).pack(side="left", padx=(8, 0))
            _refresh_list()

        _show_main()

    def _load_credentials(self) -> dict:
        """Load credentials from the shared overlay file, falling back to config.json."""
        overlay = self._credentials_overlay_path()
        if os.path.exists(overlay):
            try:
                with open(overlay, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        # Fall back to root config.json
        cfg_path = os.path.join(self._shell_dir, "config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_credentials(self, **kwargs):
        """Persist credential updates to the shared overlay file and reload all tools."""
        overlay = self._credentials_overlay_path()
        os.makedirs(os.path.dirname(overlay), exist_ok=True)
        # Merge with any existing overlay values
        existing = {}
        if os.path.exists(overlay):
            try:
                with open(overlay, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.update({k: v for k, v in kwargs.items() if v})
        with open(overlay, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        # Live-reload any tools that support it
        self._reload_tool_credentials(existing)

    def _credentials_overlay_path(self) -> str:
        if sys.platform == "darwin":
            base = os.path.expanduser(
                "~/Library/Application Support/Cornerstone Tools")
        elif sys.platform == "win32":
            base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                                "Cornerstone Tools")
        else:
            base = os.path.expanduser("~/.cornerstone_tools")
        return os.path.join(base, "credentials.json")

    def _reload_tool_credentials(self, creds: dict):
        """Push updated credentials into any loaded tool modules."""
        for tool_id, frame in self.frames.items():
            if hasattr(frame, "update_credentials"):
                try:
                    frame.update_credentials(creds)
                except Exception:
                    pass

    # ── Connection checks ──────────────────────────────────────────────────────

    def _chk_bullhorn(self):
        import requests, urllib.parse
        cfg = {}
        for p in [
            os.path.join(self._shell_dir, "mailshot_helper", "config.json"),
            os.path.join(self._shell_dir, "import_contact",  "config.json"),
            os.path.join(self._shell_dir, "config.json"),
        ]:
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f: cfg = json.load(f)
                break
        cid = cfg.get("bullhorn_client_id", "")
        if not cid or "YOUR_" in cid:
            return False, "Not configured"
        usr   = cfg.get("bullhorn_username", "")
        pwd   = cfg.get("bullhorn_password", "")
        redir = cfg.get("bullhorn_redirect_uri", "https://welcome.bullhornstaffing.com")
        try:
            pw_enc = urllib.parse.quote(pwd, safe="")
            url = (
                f"https://auth-emea.bullhornstaffing.com/oauth/authorize"
                f"?client_id={cid}&response_type=code&action=Login"
                f"&username={usr}&password={pw_enc}&redirect_uri={redir}"
            )
            resp = requests.Session().get(url, allow_redirects=True, timeout=12)
            if "code=" in resp.url or "code=" in resp.text:
                return True, ""
            return False, "Auth failed"
        except Exception as e:
            return False, str(e)[:55]

    def _find_cv_config(self):
        """Return the path to cv_config.json, checking sys._MEIPASS first."""
        meipass = getattr(sys, "_MEIPASS", None)
        candidates = [
            os.path.join(meipass, "cv_config.json") if meipass else None,
            os.path.join(self._shell_dir, "cv_parse_format", "cv_config.json"),
            os.path.join(self._shell_dir, "cv_config.json"),
        ]
        for p in candidates:
            if p and os.path.exists(p):
                return p
        return None

    def _chk_anthropic(self):
        import requests
        p = self._find_cv_config()
        if not p:
            return False, "cv_config.json missing"
        with open(p, encoding="utf-8") as f: cfg = json.load(f)
        key = cfg.get("anthropic_api_key", "")
        if not key or "YOUR_" in key:
            return False, "Not configured"
        try:
            r = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                timeout=8)
            return (True, "") if r.status_code == 200 else (False, f"HTTP {r.status_code}")
        except Exception as e:
            return False, str(e)[:55]

    def _chk_postgres(self):
        # Initialise the shared store and pre-fetch the candidate count in one shot.
        # The connection stays open and the count is cached so the Candidates tab
        # renders the paginator instantly without a second round trip.
        try:
            from cv_parse_format_tool import prefetch_count
            ok, result = prefetch_count()
            return ok, "" if ok else str(result)[:55]
        except Exception as e:
            return False, str(e)[:55]

    def _show_startup_check(self):
        overlay = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        card = ctk.CTkFrame(overlay, fg_color=CARD, corner_radius=16, width=440)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(card, text="◈  CPS Tools",
                     font=ctk.CTkFont(_FF, 18, "bold"),
                     text_color=GOLD).pack(pady=(32, 4), padx=48)
        ctk.CTkLabel(card, text="Verifying connections…",
                     font=ctk.CTkFont(_FF, 12), text_color=MUTED).pack(pady=(0, 22))

        checks = [
            ("Bullhorn",      self._chk_bullhorn),
            ("Anthropic AI",  self._chk_anthropic),
            ("Database",      self._chk_postgres),
        ]
        status_labels = {}
        for name, _ in checks:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=40, pady=5)
            ctk.CTkLabel(row, text=name, width=130, anchor="w",
                         font=ctk.CTkFont(_FF, 12), text_color=INK).pack(side="left")
            lbl = ctk.CTkLabel(row, text="⟳  Checking…", text_color=MUTED,
                               font=ctk.CTkFont(_FF, 12))
            lbl.pack(side="left")
            status_labels[name] = lbl

        sep = ctk.CTkFrame(card, fg_color=HAIR, height=1)
        sep.pack(fill="x", padx=28, pady=(22, 0))

        def _proceed():
            overlay.destroy()
            self.show_tool(TOOLS[0]["id"])

        proceed = ctk.CTkButton(card, text="Continue →", command=_proceed,
                                width=160, height=38, corner_radius=8,
                                fg_color=GOLD, hover_color=GOLD_HV,
                                text_color="#ffffff",
                                font=ctk.CTkFont(_FF, 13, "bold"),
                                state="disabled")
        proceed.pack(pady=(16, 32))

        pending  = [len(checks)]
        all_ok   = [True]

        def _update(name, ok, err):
            lbl = status_labels[name]
            if ok:
                lbl.configure(text="✓  Connected", text_color="#2e8f4e")
            else:
                lbl.configure(text=f"✗  {err}" if err else "✗  Failed",
                              text_color="#bf4040")
                all_ok[0] = False
            pending[0] -= 1
            if pending[0] == 0:
                proceed.configure(state="normal")
                if all_ok[0]:
                    self.after(800, _proceed)

        def _run():
            for name, fn in checks:
                try:
                    ok, err = fn()
                except Exception as e:
                    ok, err = False, str(e)[:55]
                self.after(0, lambda n=name, o=ok, e=err: _update(n, o, e))

        threading.Thread(target=_run, daemon=True).start()

    # ── Reconnect ──────────────────────────────────────────────────────────────

    def _reconnect_all(self, silent=False):
        """Re-run connection checks and call reconnect() on all loaded tools."""
        self.invalidate_soffice()   # re-check LibreOffice on every refresh
        # If CV is blocked and LO is now available, reload it
        if self.active == "cv" and self._check_soffice():
            self._hide_lo_block()
            self.active = None
            self.show_tool("cv")
        for tool_id, frame in self.frames.items():
            if hasattr(frame, "reconnect"):
                try:
                    frame.reconnect(silent=silent)
                except Exception as e:
                    print(f"[reconnect] {tool_id}: {e}")

    def _schedule_refresh(self):
        """Auto-refresh connections every 5 minutes."""
        self._reconnect_all(silent=True)
        self.after(300_000, self._schedule_refresh)

    # ── Update checker ─────────────────────────────────────────────────────────

    def _check_for_update(self):
        def _bg():
            try:
                import updater
                info = updater.check_update()
                _log(f"[update] check result: {info}")
            except Exception as e:
                _log(f"[update] check failed: {e}")
                info = None
            if info:
                self.after(0, lambda: self._on_update_found(info))

        threading.Thread(target=_bg, daemon=True).start()

    def _on_update_found(self, info):
        self._update_info = info
        label = f"↓  Update v{info['version']}" if self.expanded else "↓"
        self._update_btn.configure(text=label)
        self._update_btn.pack(side="bottom", fill="x", padx=10, pady=(0, 4))

    def _show_update_dialog(self):
        import threading
        info = self._update_info
        if not info:
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Update Available")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BG)
        # Hide while building content — avoids blank flash on macOS and Windows
        dlg.withdraw()

        pad = {"padx": 28}

        ctk.CTkLabel(dlg, text=f"CPS Tools v{info['version']} is available",
                     font=(_FF, 14, "bold"), text_color=INK
                     ).pack(pady=(24, 4), **pad)
        ctk.CTkLabel(dlg, text=f"You have v{info['current']} installed.",
                     font=FONT_SM, text_color=MUTED
                     ).pack(pady=0, **pad)

        if info.get("notes"):
            notes = info["notes"][:160] + ("…" if len(info["notes"]) > 160 else "")
            ctk.CTkLabel(dlg, text=notes, font=(_FF, 10), text_color=MUTED,
                         wraplength=360, justify="left"
                         ).pack(pady=(8, 0), **pad)

        progress = ctk.CTkProgressBar(dlg, width=360)

        status_lbl = ctk.CTkLabel(dlg, text="", font=FONT_SM, text_color=MUTED)
        status_lbl.pack(pady=(12, 0), **pad)

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(pady=(10, 20), **pad)

        def _start_install():
            install_btn.configure(state="disabled")
            later_btn.configure(state="disabled")
            progress.pack(pady=(0, 6), **pad)
            progress.set(0)
            status_lbl.configure(text="Downloading…")

            def _bg():
                try:
                    import updater
                    updater.install_update(
                        info["download_url"],
                        progress_cb=lambda f: self.after(0, lambda v=f: (
                            progress.set(v),
                            status_lbl.configure(text=f"Downloading… {int(v*100)}%"),
                        )),
                    )
                except Exception as e:
                    self.after(0, lambda: status_lbl.configure(
                        text=f"Update failed: {e}", text_color=RED
                    ))

            threading.Thread(target=_bg, daemon=True).start()

        install_btn = ctk.CTkButton(btn_row, text="Install & Restart",
                                    fg_color=GOLD, hover_color=GOLD_HV,
                                    text_color="#ffffff", font=FONT_BOLD,
                                    width=160, command=_start_install)
        install_btn.pack(side="left", padx=(0, 10))

        later_btn = ctk.CTkButton(btn_row, text="Later",
                                  fg_color=SURFACE, hover_color=HAIR,
                                  text_color=MUTED, font=FONT_SM,
                                  width=80, command=dlg.destroy)
        later_btn.pack(side="left")

        # Measure content, center over parent, then reveal
        dlg.update_idletasks()
        W, H = 420, dlg.winfo_reqheight()
        px = self.winfo_rootx() + self.winfo_width()  // 2
        py = self.winfo_rooty() + self.winfo_height() // 2
        dlg.geometry(f"{W}x{H}+{px - W // 2}+{py - H // 2}")
        dlg.deiconify()
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def toggle(self):
        self.expanded = not self.expanded
        self.sidebar.configure(width=240 if self.expanded else 58)
        for tool in TOOLS:
            b = self.buttons[tool["id"]]
            if self.expanded:
                b.configure(text=tool["label"], anchor="w", compound="left")
            else:
                b.configure(text="", anchor="center")
        # Update button shows icon-only when collapsed, full label when expanded
        if self._update_info:
            ver = self._update_info["version"]
            self._update_btn.configure(
                text=f"↓  Update v{ver}" if self.expanded else "↓"
            )

    # ── LibreOffice block overlay ──────────────────────────────────────────────

    def _check_soffice(self):
        """Return truthy if any PDF engine is available (Word or LibreOffice)."""
        if not self._soffice_checked:
            from cv_parse_format_tool import _find_soffice, _find_word
            result = _find_soffice()
            if not result and sys.platform == "win32":
                result = _find_word() or False
            self._soffice = result if result else False
            self._soffice_checked = True
        return self._soffice or None

    def invalidate_soffice(self):
        """Force a fresh LibreOffice check on the next show_tool("cv") call."""
        self._soffice_checked = False
        self._soffice = None

    def _show_lo_block(self):
        """Place the LibreOffice-required overlay over the content area."""
        if self._lo_block is None or not self._lo_block.winfo_exists():
            block = ctk.CTkFrame(self.content, fg_color=BG)
            ctk.CTkLabel(block,
                         text="PDF Engine Required",
                         font=ctk.CTkFont(_FF, 18, "bold"),
                         text_color=INK).pack(pady=(100, 8))
            body = (
                "CV Parse & Format needs Microsoft Word or LibreOffice\n"
                "to export PDFs.\n\n"
                "Click  ⚙ Open Tools Manager  to check what's installed\n"
                "or to install LibreOffice, then click ↺ to reload."
                if sys.platform == "win32" else
                "CV Parse & Format needs LibreOffice to export PDFs.\n\n"
                "Click  ⚙ Open Tools Manager  below to install it,\n"
                "then click the refresh (↺) button to reload."
            )
            ctk.CTkLabel(block, text=body,
                         font=ctk.CTkFont(_FF, 13),
                         text_color=MUTED, justify="center").pack()
            ctk.CTkButton(block, text="⚙  Open Tools Manager",
                          fg_color=GOLD, hover_color=GOLD_HV,
                          text_color="#ffffff", font=ctk.CTkFont(_FF, 13, "bold"),
                          height=40, width=220, corner_radius=10,
                          command=self._open_deps_panel).pack(pady=24)
            self._lo_block = block
        self._lo_block.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._lo_block.lift()

    def _hide_lo_block(self):
        if self._lo_block and self._lo_block.winfo_exists():
            self._lo_block.place_forget()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def show_tool(self, tool_id):
        import traceback

        # CV tool requires LibreOffice — show a blocking overlay if missing
        if tool_id == "cv" and not self._check_soffice():
            self._show_lo_block()
            # Update sidebar highlight even when blocked
            for tid, b in self.buttons.items():
                active = tid == tool_id
                b.configure(fg_color=SURFACE if active else "transparent",
                            image=self.icons[tid]["active" if active else "idle"])
            self.active = tool_id
            return

        # Switching to any other tool — hide block overlay if visible
        self._hide_lo_block()

        if self.active == tool_id:
            return

        # On Windows, cover the content area during the switch so the widget
        # construction isn't drawn incrementally (macOS compositor hides this naturally)
        cover = None
        if sys.platform == "win32":
            cover = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0)
            cover.place(relx=0, rely=0, relwidth=1, relheight=1)
            cover.lift()
            self.update_idletasks()

        for fid, frame in self.frames.items():
            frame.pack_forget()
        if tool_id not in self.frames:
            tool = next(t for t in TOOLS if t["id"] == tool_id)
            try:
                self.frames[tool_id] = tool["cls_obj"](self.content)
            except Exception:
                err = traceback.format_exc()
                print(f"[show_tool] {tool_id} failed:\n{err}", flush=True)
                frame = ctk.CTkFrame(self.content, fg_color=BG)
                ctk.CTkLabel(frame, text=f"⚠  {tool['label']} failed to load",
                             font=ctk.CTkFont(_FF, 14, "bold"),
                             text_color=RED).pack(pady=(80, 12))
                display = err if len(err) <= 1200 else "…" + err[-1200:]
                ctk.CTkLabel(frame, text=display, font=ctk.CTkFont("Courier", 10),
                             text_color=MUTED, wraplength=700, justify="left").pack(padx=40)
                self.frames[tool_id] = frame
        self.frames[tool_id].pack(fill="both", expand=True)
        self.active = tool_id
        for tid, b in self.buttons.items():
            active = tid == tool_id
            b.configure(fg_color=SURFACE if active else "transparent",
                        image=self.icons[tid]["active" if active else "idle"])

        if cover:
            self.update_idletasks()
            cover.destroy()


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    app = Shell()
    app.mainloop()
