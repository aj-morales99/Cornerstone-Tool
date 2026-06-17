"""Cornerstone Tools — multi-tool shell.
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
                               "Cornerstone Tools")
    else:
        log_dir = os.path.join(os.path.expanduser("~"), "Library", "Logs", "Cornerstone Tools")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")
    import builtins
    _log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file
    print(f"=== Cornerstone Tools started ===", flush=True)

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

FONT_SM   = ("Arial", 11)
FONT_BOLD = ("Arial", 13, "bold")

TOOLS = [
    {"id": "cv",       "icon": "candidate", "label": "CV Parse & Format  V0.1",
     "folder": "cv_parse_format",  "module": "cv_parse_format_tool",  "cls": "CVParseFormatTool"},
    {"id": "import",   "icon": "upload",    "label": "Import Contacts  V2.0",
     "folder": "import_contact",   "module": "import_contact_tool",   "cls": "BullhornImportTool"},
    {"id": "mailshot", "icon": "email",     "label": "Mailshot Helper  V1.0",
     "folder": "mailshot_helper",  "module": "mailshot_helper_tool",  "cls": "MailshotHelperTool"},
]


class Shell(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Cornerstone Tools")
        self.geometry("1380x880")
        self.minsize(1100, 720)
        self.configure(fg_color=BG)
        self._shell_dir = os.path.dirname(os.path.abspath(__file__))
        self.frames  = {}
        self.buttons = {}
        self.active  = None
        self.expanded = False
        self._build()
        # Show startup connection check — it will call show_tool when done
        self.after(120, self._show_startup_check)
        # Auto-refresh connections every 5 minutes
        self.after(300_000, self._schedule_refresh)

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
        self._reload_btn.pack(side="bottom", pady=10, padx=8)

        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

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

        ctk.CTkLabel(card, text="◈  Cornerstone Tools",
                     font=ctk.CTkFont("Arial", 18, "bold"),
                     text_color=GOLD).pack(pady=(32, 4), padx=48)
        ctk.CTkLabel(card, text="Verifying connections…",
                     font=ctk.CTkFont("Arial", 12), text_color=MUTED).pack(pady=(0, 22))

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
                         font=ctk.CTkFont("Arial", 12), text_color=INK).pack(side="left")
            lbl = ctk.CTkLabel(row, text="⟳  Checking…", text_color=MUTED,
                               font=ctk.CTkFont("Arial", 12))
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
                                font=ctk.CTkFont("Arial", 13, "bold"),
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

    def show_tool(self, tool_id):
        import importlib
        if self.active == tool_id:
            return
        for fid, frame in self.frames.items():
            frame.pack_forget()
        if tool_id not in self.frames:
            tool = next(t for t in TOOLS if t["id"] == tool_id)
            tool_dir = os.path.join(self._shell_dir, tool["folder"])
            if tool_dir not in sys.path:
                sys.path.insert(0, tool_dir)
            mod = importlib.import_module(tool["module"])
            if hasattr(mod, "_bootstrap_dependencies"):
                mod._bootstrap_dependencies()
            self.frames[tool_id] = getattr(mod, tool["cls"])(self.content)
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
