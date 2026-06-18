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
    {"id": "import",   "icon": "upload",    "label": "Import Contacts  V2.0",
     "folder": "import_contact",   "module": "contact_tool",          "cls": "BullhornImportTool", "cls_obj": BullhornImportTool},
    {"id": "mailshot", "icon": "email",     "label": "Mailshot Helper  V1.0",
     "folder": "mailshot_helper",  "module": "mailshot_helper_tool",  "cls": "MailshotHelperTool", "cls_obj": MailshotHelperTool},
]


class Shell(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CPS Tools")
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
        self._build()
        # Show startup connection check — it will call show_tool when done
        self.after(120, self._show_startup_check)
        # Auto-refresh connections every 5 minutes
        self.after(300_000, self._schedule_refresh)

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

        # Reload button pinned to sidebar bottom
        _reload_img = tool_icon("reload", size=20)
        self._reload_btn = ctk.CTkButton(
            self.sidebar, text="", image=_reload_img,
            width=42, height=42, corner_radius=10,
            fg_color="transparent", hover_color=SURFACE,
            command=self._reconnect_all)
        self._reload_btn.pack(side="bottom", pady=(0, 10), padx=8)

        # Tools / Dependency Manager button (above reload)
        _tools_img = tool_icon("tools", size=20)
        self._tools_btn = ctk.CTkButton(
            self.sidebar, text="", image=_tools_img,
            width=42, height=42, corner_radius=10,
            fg_color="transparent", hover_color=SURFACE,
            command=self._open_deps_panel)
        self._tools_btn.pack(side="bottom", pady=(0, 2), padx=8)

        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

    # ── Dependency Manager ─────────────────────────────────────────────────────

    def _open_deps_panel(self):
        """Open the Required Tools window with background download + install."""
        import platform, tempfile, urllib.request
        from cv_parse_format_tool import _find_soffice, _find_word

        def _get_lo_version():
            """Fetch the latest LibreOffice stable version from the download server."""
            import re
            try:
                with urllib.request.urlopen(
                        "https://download.documentfoundation.org/libreoffice/stable/",
                        timeout=10) as resp:
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

        WW, WH = 520, (430 if sys.platform == "win32" else 340)
        win = ctk.CTkToplevel(self)
        win.title("Required Tools")
        win.resizable(False, False)
        win.configure(fg_color=BG)
        self.update_idletasks()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        win.geometry(f"{WW}x{WH}+{px + (pw - WW)//2}+{py + (ph - WH)//2}")
        win.grab_set()
        win.lift()
        win.focus_force()

        ctk.CTkLabel(win, text="Required Tools",
                     font=ctk.CTkFont(_FF, 16, "bold"),
                     text_color=INK).pack(pady=(22, 2), padx=28, anchor="w")
        ctk.CTkLabel(win,
                     text="Applications needed for PDF export and CV formatting.",
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
            word_found = _find_word()
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
            if word_found:
                ctk.CTkLabel(word_card,
                             text="Word is installed — LibreOffice is optional.",
                             font=FONT_SM, text_color=MUTED, anchor="w").pack(
                             padx=16, pady=(2, 12), anchor="w")
            else:
                ctk.CTkLabel(word_card,
                             text="Not found. Install Microsoft Office to use Word.",
                             font=FONT_SM, text_color=MUTED, anchor="w").pack(
                             padx=16, pady=(2, 12), anchor="w")

        # ── LibreOffice card ──
        card = ctk.CTkFrame(win, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=HAIR)
        card.pack(fill="x", padx=20, pady=(0, 12))

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(top_row, text="LibreOffice", font=FONT_BOLD,
                     text_color=INK, anchor="w").pack(side="left")

        status_lbl = ctk.CTkLabel(top_row, text="", font=FONT_SM, anchor="e")
        status_lbl.pack(side="right")

        ctk.CTkLabel(card, text="PDF export  ·  CV formatting  ·  Document parsing",
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

                req = urllib.request.urlopen(url, timeout=30)
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
            _set_status("✗  Not installed", RED)
            if sys.platform in ("darwin", "win32"):
                install_btn.pack(side="left")

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
                with open(p) as f: cfg = json.load(f)
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
        with open(p) as f: cfg = json.load(f)
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

    def _chk_sheets(self):
        p = self._find_cv_config()
        if not p:
            return False, "cv_config.json missing"
        with open(p) as f: cfg = json.load(f)
        gs    = cfg.get("google_sheets", {})
        creds = gs.get("credentials_path", "")
        sid   = gs.get("spreadsheet_id", "")
        if not creds or not sid:
            return False, "Not configured"
        if not os.path.isabs(creds) or not os.path.exists(creds):
            basename = os.path.basename(creds)
            meipass  = getattr(sys, "_MEIPASS", None)
            for candidate in [
                os.path.join(meipass, "cv_parse_format", basename) if meipass else None,
                os.path.join(self._shell_dir, "cv_parse_format", basename),
            ]:
                if candidate and os.path.exists(candidate):
                    creds = candidate
                    break
        if not os.path.exists(creds):
            return False, "Credentials file missing"
        try:
            from google.oauth2.service_account import Credentials
            import googleapiclient.discovery
            c  = Credentials.from_service_account_file(
                creds, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            svc = googleapiclient.discovery.build("sheets", "v4", credentials=c)
            svc.spreadsheets().get(spreadsheetId=sid).execute()
            return True, ""
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
            ("Google Sheets", self._chk_sheets),
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

    def _reconnect_all(self):
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
                    frame.reconnect()
                except Exception as e:
                    print(f"[reconnect] {tool_id}: {e}")

    def _schedule_refresh(self):
        """Auto-refresh connections every 5 minutes."""
        self._reconnect_all()
        self.after(300_000, self._schedule_refresh)

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


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    app = Shell()
    app.mainloop()
