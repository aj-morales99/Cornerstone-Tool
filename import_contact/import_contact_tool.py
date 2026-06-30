import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import re
import pandas as pd
import requests
import threading
import json
import os
from datetime import datetime
import urllib.parse
from urllib.parse import urlparse, parse_qs
import sys

# ── Resource path (PyInstaller compat) ─────────────────────────────────────────
def resource_path(relative_path):
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)

# ── Credentials ────────────────────────────────────────────────────────────────
def load_config():
    # Search order: bundled mailshot config (same Bullhorn creds), local folder, cwd
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(os.path.join(meipass, "mailshot_helper", "config.json"))
    candidates += [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mailshot_helper", "config.json"),
        os.path.abspath("config.json"),
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                with open(p) as f:
                    return json.load(f)
        except Exception:
            continue
    return {}

CONFIG = load_config()

BH_CLIENT_ID     = CONFIG.get("bullhorn_client_id",     "72e7e477-b21a-40ae-83d2-6726c57c87b0")
BH_CLIENT_SECRET = CONFIG.get("bullhorn_client_secret", "iKzPHZxvQpmG2WurpNU1el0H")
BH_USERNAME      = CONFIG.get("bullhorn_username",      "cornerstonevisionclaudegit.api")
BH_PASSWORD      = CONFIG.get("bullhorn_password",      "ClaudeTest2026##")
BH_REDIRECT_URI  = CONFIG.get("bullhorn_redirect_uri",  "https://welcome.bullhornstaffing.com")
INSTANTLY_KEY    = CONFIG.get("instantly_api_key",      "OTI0Zjk0ZTQtOWM3Yi00NzgxLWJlMzMtNzE4ODcwNTg1MWM4Om9mbkp4WFFUcXlKQQ==")
MILLION_API_KEY  = "D5O4NwiijFbS1jlMFviRFDTtF"

BH_AUTH_URL  = "https://auth-emea.bullhornstaffing.com"
BH_LOGIN_URL = "https://rest-emea.bullhornstaffing.com"
IN_BASE_URL  = "https://api.instantly.ai/api/v2"

def update_credentials(creds: dict):
    """Live-update module-level credentials from the settings overlay."""
    import sys
    mod = sys.modules[__name__]
    mapping = {
        "bullhorn_username": "BH_USERNAME",
        "bullhorn_password": "BH_PASSWORD",
        "instantly_api_key": "INSTANTLY_KEY",
    }
    for cfg_key, mod_attr in mapping.items():
        if cfg_key in creds and creds[cfg_key]:
            setattr(mod, mod_attr, creds[cfg_key])

def instantly_headers():
    return {"Authorization": f"Bearer {INSTANTLY_KEY}", "Content-Type": "application/json"}


# ── Company enrichment ─────────────────────────────────────────────────────────

_GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "live.com", "msn.com", "aol.com", "protonmail.com", "mail.com",
    "me.com", "googlemail.com", "ymail.com", "hotmail.co.uk", "yahoo.co.uk",
}

_SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


def _extract_domain(email: str) -> str | None:
    """Return the domain part of an email, or None if generic/blank."""
    email = (email or "").strip().lower()
    if "@" not in email:
        return None
    domain = email.split("@")[-1].strip()
    if not domain or domain in _GENERIC_DOMAINS:
        return None
    return domain


def _scrape_linkedin_about(linkedin_raw: str, log=None) -> str:
    """
    Scrape the About text from a LinkedIn company page.
    linkedin_raw may be a full URL or just the slug (e.g. 'acme-corp').
    Returns plain text or empty string on failure.
    """
    if not linkedin_raw:
        return ""
    raw = linkedin_raw.strip().rstrip("/")
    if "linkedin.com" in raw:
        slug = raw.split("linkedin.com/company/")[-1].split("/")[0].split("?")[0]
    else:
        slug = raw.lstrip("/")
    url = f"https://www.linkedin.com/company/{slug}/about/"
    try:
        resp = requests.get(url, headers=_SCRAPE_HEADERS, timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            if log:
                log(f"  LinkedIn about: HTTP {resp.status_code} for {url}")
            return ""
        html = resp.text
        # LinkedIn embeds description in <p class="break-words"> or og:description
        import re as _re
        # Try og:description first (most reliable without JS render)
        og = _re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html)
        if og:
            return og.group(1).strip()
        # Fallback: first substantial <p> inside the about section
        paras = _re.findall(r'<p[^>]*class="[^"]*break-words[^"]*"[^>]*>(.*?)</p>',
                            html, _re.DOTALL)
        for p in paras:
            text = _re.sub(r'<[^>]+>', '', p).strip()
            if len(text) > 60:
                return text
        return ""
    except Exception as ex:
        if log:
            log(f"  LinkedIn about scrape failed: {ex}")
        return ""


def _scrape_website_domains(website_url: str, log=None) -> list[str]:
    """
    Fetch the company website and extract all unique non-generic email domains
    found in mailto: links or plain-text email addresses.
    """
    if not website_url:
        return []
    url = website_url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, headers=_SCRAPE_HEADERS, timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            return []
        html = resp.text
        import re as _re
        found = set()
        # mailto: links
        for m in _re.finditer(r'mailto:([^\s"\'<>?]+)', html, _re.IGNORECASE):
            d = _extract_domain(m.group(1))
            if d:
                found.add(d)
        # Plain email patterns in text
        for m in _re.finditer(r'[\w.+-]+@([\w.-]+\.[a-z]{2,})', html, _re.IGNORECASE):
            d = m.group(1).lower()
            if d and d not in _GENERIC_DOMAINS:
                found.add(d)
        return sorted(found)
    except Exception as ex:
        if log:
            log(f"  Website domain scrape failed: {ex}")
        return []


def enrich_company(email: str, website_url: str, linkedin_raw: str,
                   log=None) -> dict:
    """
    Returns a dict with optional keys:
      companyDescription  – scraped from LinkedIn /about
      customTextBlock1    – @ -prefixed email domains joined with ' . '
      status              – always "Active Account"
    """
    result = {"status": "Active Account"}

    # ── Email domains ──────────────────────────────────────────────────────
    domains: set[str] = set()
    d = _extract_domain(email)
    if d:
        domains.add(d)
    for d in _scrape_website_domains(website_url, log=log):
        domains.add(d)
    if domains:
        result["customTextBlock1"] = " . ".join(
            f"@{d}" for d in sorted(domains))

    # ── LinkedIn About ─────────────────────────────────────────────────────
    about = _scrape_linkedin_about(linkedin_raw, log=log)
    if about:
        result["companyDescription"] = about

    return result


# ── Theme — light paper (matches CV Parse & Format tool) ───────────────────────
GOLD    = "#b8965a"   # accent
GOLD_HV = "#a98549"
BG      = "#edeae3"   # app background
CARD    = "#ffffff"   # raised surface
SURFACE = "#f4f2ec"   # inputs / wells
HAIR    = "#e1dccf"   # hairline border
WHITE   = "#2a2a2a"   # primary text (dark ink on paper)
MUTED   = "#8d8779"   # secondary text
GREEN   = "#2e8f4e"
BLUE    = "#3a6fc4"
ORANGE  = "#bd7a1a"
PURPLE  = "#7a4fb0"
RED     = "#bf4040"

# Child row colours
CON_CHILD_BG = "#e8f3ec"
CON_CHILD_FG = "#2e7d4f"
CO_CHILD_BG  = "#eef1fb"
CO_CHILD_FG  = "#3a5bb0"

FONT = "Segoe UI" if sys.platform == "win32" else "Arial"

# appearance mode is set by the host (Cornerstone Tools shell or _standalone)

# normal arrow cursor everywhere — no pointing hand on buttons
for _cls in ("CTkButton", "CTkCheckBox", "CTkSwitch", "CTkOptionMenu",
             "CTkSlider", "CTkSegmentedButton", "CTkRadioButton"):
    try:
        getattr(ctk, _cls)._set_cursor = lambda self: None
    except AttributeError:
        pass

# ── Helpers ─────────────────────────────────────────────────────────────────────
def solid_btn(parent, text, cmd=None, width=120, height=32, fg=GOLD, hover=GOLD_HV,
              text_color="#ffffff", **kw):
    """Filled accent button — for the single primary action in a group."""
    return ctk.CTkButton(
        parent, text=text, fg_color=fg, hover_color=hover,
        text_color=text_color, font=ctk.CTkFont(FONT, 12, "bold"),
        corner_radius=8, width=width, height=height, command=cmd, **kw)

def ghost_btn(parent, text, cmd=None, width=110, height=32, accent=WHITE, **kw):
    """Outline button — quiet secondary action."""
    return ctk.CTkButton(
        parent, text=text, fg_color="transparent", hover_color=SURFACE,
        text_color=accent, border_width=1, border_color=HAIR,
        font=ctk.CTkFont(FONT, 12), corner_radius=8,
        width=width, height=height, command=cmd, **kw)

# Back-compat shim — popups still call pill_btn
def pill_btn(parent, text, fg=GOLD, hover=GOLD_HV, cmd=None, width=130, height=32, **kw):
    if fg in (GOLD, GREEN, ORANGE, RED, BLUE, PURPLE):
        return solid_btn(parent, text, cmd, width, height, fg=fg, hover=hover,
                         text_color="#ffffff" if fg in (GOLD, GREEN, ORANGE) else WHITE, **kw)
    return ghost_btn(parent, text, cmd, width, height, **kw)

def section_label(parent, text):
    return ctk.CTkLabel(parent, text=text.upper(),
                        font=ctk.CTkFont(FONT, 10, "bold"),
                        text_color=MUTED)

def build_tree(parent, cols, height=4, tree_col=False):
    from tkinter import ttk
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.Treeview",
                    background=CARD, foreground=WHITE, fieldbackground=CARD,
                    rowheight=30, borderwidth=0, font=(FONT, 11))
    style.configure("Dark.Treeview.Heading",
                    background=BG, foreground=MUTED,
                    font=(FONT, 9, "bold"), borderwidth=0, relief="flat")
    style.map("Dark.Treeview",
              background=[("selected", "#f3efe6")],   # subtle warm tint, just offset from white
              foreground=[("selected", WHITE)])       # keep the ink colour unchanged
    style.map("Dark.Treeview.Heading", background=[("active", BG)])

    frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12,
                         border_width=1, border_color=HAIR)
    show = "tree headings" if tree_col else "headings"
    tree = tk.ttk.Treeview(frame, columns=cols, show=show,
                            height=height, style="Dark.Treeview")
    if tree_col:
        tree.column("#0", width=18, stretch=False, minwidth=18)
    vsb = tk.ttk.Scrollbar(frame, orient="vertical",   command=tree.yview)
    hsb = tk.ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.pack(side="right",  fill="y",  pady=8)
    hsb.pack(side="bottom", fill="x",  padx=8)
    tree.pack(fill="both",  expand=True, padx=8, pady=8)
    return frame, tree

# ── Main App ────────────────────────────────────────────────────────────────────
class BullhornImportTool(ctk.CTkFrame):
    """Embeddable frame — hosted inside Cornerstone Tools, or standalone via __main__."""

    def __init__(self, master=None):
        super().__init__(master, fg_color=BG)

        # ── Session state ──────────────────────────────────────────────────────
        self.bh_base_url   = ""
        self.bh_rest_token = ""
        self.campaigns_list    = []
        self.bullhorn_cache    = {}
        self.co_search_cache   = {}
        self.csv_data_cache    = {}
        self.company_map       = {}
        self.manual_contact_id = {}
        self.log_visible       = True
        # Maps child treeview item → {type, parent, id, name, raw_data}
        self._child_data       = {}

        self.cols = [
            "Action", "BH Company", "First Name", "Last Name", "Job Title",
            "Email", "Email Status", "Sub-Result", "Phone",
            "City/Town", "County", "Country", "Custom Industry",
            "Custom Type of Work", "Custom County", "Final General Comments",
            "CSV Company", "Company Website", "Company LinkedIn",
            "Company Phone", "Company City/Town", "Company County",
            "Company Country", "Contact LinkedIn URL",
        ]

        # Tree column index → CSV cache key (for keeping csv_data_cache in sync on edits)
        self.col_to_csv = {
            2: "First Name", 3: "Surname", 4: "Position", 5: "Email",
            8: "Work Phone", 9: "City / Town", 10: "County", 11: "Country",
            12: "Custom Industry", 13: "Custom Type of Work", 14: "Custom County",
            15: "Final General Comments", 16: "Company", 17: "Company Website",
            18: "Company LinkedIn URL", 19: "Company Phone Number",
            20: "Company City/Town", 21: "Company County", 22: "Company Country",
            23: "Linked In URL",
        }

        self._build_ui()
        self.after(300, self._bh_connect)

    # ── Bullhorn Auth ──────────────────────────────────────────────────────────
    def _bh_connect(self):
        self.after(0, lambda: self.bh_status.configure(
            text="● Connecting...", text_color=ORANGE))

        def _run():
            try:
                auth_url  = f"{BH_AUTH_URL}/oauth/authorize"
                token_url = f"{BH_AUTH_URL}/oauth/token"
                login_url = f"{BH_LOGIN_URL}/rest-services/login"

                pw_enc = urllib.parse.quote(BH_PASSWORD, safe="")
                full_auth = (
                    f"{auth_url}"
                    f"?client_id={BH_CLIENT_ID}&response_type=code&action=Login"
                    f"&username={BH_USERNAME}&password={pw_enc}"
                    f"&redirect_uri={BH_REDIRECT_URI}"
                )
                session = requests.Session()
                resp = session.get(full_auth, allow_redirects=True, timeout=30)
                final_url = resp.url

                code = None
                if "code=" in final_url:
                    code = parse_qs(urlparse(final_url).query).get("code", [None])[0]
                if not code and "code=" in resp.text:
                    import re as _re
                    m = _re.search(r'[?&]code=([^&"\'\\s]+)', resp.text)
                    if m:
                        code = m.group(1)
                if not code:
                    raise Exception("Could not get authorisation code. Check credentials in config.json.")

                r = requests.post(token_url, params={
                    "grant_type": "authorization_code", "code": code,
                    "client_id": BH_CLIENT_ID, "client_secret": BH_CLIENT_SECRET,
                    "redirect_uri": BH_REDIRECT_URI,
                }, timeout=15)
                d = r.json()
                if "access_token" not in d:
                    raise Exception(d.get("error_description", str(d)))

                r2 = requests.get(login_url,
                    params={"version": "2.0", "access_token": d["access_token"]}, timeout=15)
                d2 = r2.json()
                if "BhRestToken" not in d2:
                    raise Exception(f"REST login failed: {d2}")

                self.bh_rest_token = d2["BhRestToken"]
                self.bh_base_url   = d2["restUrl"]
                self.after(0, lambda: self.bh_status.configure(text="● Bullhorn Connected", text_color=GREEN))
                self.after(0, lambda: self.log("AUTH: Bullhorn connected successfully."))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self.bh_status.configure(text="● Disconnected", text_color=RED))
                self.after(0, lambda m=msg: self.log(f"AUTH ERROR: {m}"))

        threading.Thread(target=_run, daemon=True).start()

    def _token(self):
        return self.bh_rest_token

    # ── Logging ────────────────────────────────────────────────────────────────
    def log(self, m):
        ts = datetime.now().strftime("%H:%M:%S")
        self.terminal.configure(state="normal")
        self.terminal.insert("end", f"[{ts}] {m}\n")
        self.terminal.see("end")
        self.terminal.configure(state="disabled")

    # ── Utility ────────────────────────────────────────────────────────────────
    def fix_phone(self, val):
        p = str(val).strip()
        if not p or p.lower() in ("nan", "none"):
            return ""
        # Remove pandas float artifact e.g. "7911123456.0"
        if p.endswith(".0") and p[:-2].replace("(", "").replace(")", "").isdigit():
            p = p[:-2]
        # Drop the "(0)" insert used in international formats e.g. +44(0)1777 / 0(0)1777
        p = p.replace("(0)", "")
        # Keep a leading + (international), then strip every non-digit
        intl = p.lstrip().startswith("+")
        digits = re.sub(r"\D", "", p)
        if not digits:
            return p
        if intl:
            return "+" + digits
        # Convert 44-prefixed UK numbers to national format
        if digits.startswith("44") and len(digits) >= 12:
            digits = "0" + digits[2:]
        # Collapse accidental double leading zero e.g. "001777358628"
        while digits.startswith("00"):
            digits = digits[1:]
        # Restore missing leading zero on 10/11-digit UK numbers
        if not digits.startswith("0") and len(digits) in (10, 11):
            digits = "0" + digits
        return digits

    def clean_list_str(self, val):
        if val is None:
            return ""
        if isinstance(val, list):
            return ",".join(str(x).strip() for x in val if str(x).strip())
        s = str(val).strip()
        if s.startswith("[") and s.endswith("]"):
            parts = [p.strip().strip("'").strip('"') for p in s[1:-1].split(",") if p.strip()]
            return ",".join(parts)
        return s.replace(";", ",")

    # ── UI Construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header bar (top-tab navigation, matching CV Parse & Format Tool) ────
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0,
                           border_width=1, border_color=HAIR, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="Import Tool", font=ctk.CTkFont(FONT, 14, "bold"),
                     text_color=WHITE).pack(side="left", padx=(20, 0))
        ctk.CTkLabel(hdr, text="V2.0", font=ctk.CTkFont(FONT, 9),
                     text_color=MUTED).pack(side="left", padx=(4, 24))

        self._nav_buttons = {}
        for key, label in (("bullhorn", "Bullhorn"),
                           ("instantly", "Instantly"),
                           ("dripify", "Dripify")):
            b = ctk.CTkButton(
                hdr, text=label, anchor="center",
                fg_color="transparent", hover_color=SURFACE,
                text_color=MUTED, corner_radius=0, height=48,
                font=ctk.CTkFont(FONT, 13),
                command=lambda k=key: self.show_panel(k))
            b.pack(side="left", padx=2)
            self._nav_buttons[key] = b

        self.bh_status = ctk.CTkLabel(
            hdr, text="● Connecting...", text_color=ORANGE,
            font=ctk.CTkFont(FONT, 11))
        self.bh_status.pack(side="right", padx=(0, 16))
        ghost_btn(hdr, "Log", self.toggle_logs, width=58, height=30).pack(
            side="right", padx=6, pady=9)

        # ── Main column ─────────────────────────────────────────────────────────
        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.pack(fill="both", expand=True)

        # Top toolbar
        bar = ctk.CTkFrame(main, fg_color="transparent", height=60)
        bar.pack(fill="x", padx=20, pady=(14, 6))
        solid_btn(bar, "Load CSV", self.load_file, width=110).pack(side="left", padx=(0, 8))
        ghost_btn(bar, "Edit Row",      self.open_edit_row_popup,      width=90).pack(side="left", padx=3)
        ghost_btn(bar, "Select All",    self.select_all,               width=90).pack(side="left", padx=3)
        ghost_btn(bar, "Verify Emails", self.start_email_verification, width=110).pack(side="left", padx=3)
        ghost_btn(bar, "Export",        self.export_to_csv,            width=80).pack(side="left", padx=3)
        ghost_btn(bar, "Clear", self.clear_all_data, width=70, accent=RED).pack(side="left", padx=3)

        # Legend
        leg = ctk.CTkFrame(main, fg_color="transparent")
        leg.pack(fill="x", padx=22, pady=(0, 4))
        for dot_color, txt in ((CON_CHILD_FG, "contact match"),
                               (CO_CHILD_FG, "company match")):
            ctk.CTkLabel(leg, text="●", text_color=dot_color,
                         font=ctk.CTkFont(FONT, 10)).pack(side="left")
            ctk.CTkLabel(leg, text=f" {txt} — click row to link/unlink     ",
                         text_color=MUTED, font=ctk.CTkFont(FONT, 10)).pack(side="left")

        # Terminal drawer (packed before table so table can expand above it)
        self.term_wrap = ctk.CTkFrame(main, fg_color=CARD, corner_radius=12,
                                      border_width=1, border_color=HAIR, height=130)
        self.term_wrap.pack(side="bottom", fill="x", padx=20, pady=(4, 14))
        self.term_wrap.pack_propagate(False)
        self.terminal = ctk.CTkTextbox(
            self.term_wrap, fg_color="transparent", text_color=GREEN,
            font=ctk.CTkFont("SF Mono", 10), state="disabled", wrap="none")
        self.terminal.pack(fill="both", expand=True, padx=10, pady=8)

        # Destination panel container (above terminal)
        self.panel_wrap = ctk.CTkFrame(main, fg_color=CARD, corner_radius=12,
                                       border_width=1, border_color=HAIR)
        self.panel_wrap.pack(side="bottom", fill="x", padx=20, pady=4)

        self.panels = {}
        for key in ("bullhorn", "instantly", "dripify"):
            p = ctk.CTkFrame(self.panel_wrap, fg_color="transparent")
            self.panels[key] = p
        self._build_bh_panel(self.panels["bullhorn"])
        self._build_instantly_panel(self.panels["instantly"])
        self._build_dripify_panel(self.panels["dripify"])

        # Resolution strip (above destination panel)
        res = ctk.CTkFrame(main, fg_color="transparent")
        res.pack(side="bottom", fill="x", padx=20, pady=(6, 0))
        section_label(res, "Resolution").pack(side="left", padx=(2, 12))
        ghost_btn(res, "Force New Contact",    self.mark_contact_as_new,  width=140, accent=BLUE).pack(side="left", padx=3)
        ghost_btn(res, "Mark for New Company", self.mark_for_creation,    width=160, accent=BLUE).pack(side="left", padx=3)
        ghost_btn(res, "Update BH Company",    self.update_company_in_bh, width=150, accent=ORANGE).pack(side="left", padx=3)

        # Main staging table — fills all remaining vertical space
        tbl_frame, self.tree = build_tree(main, self.cols, height=14, tree_col=True)
        tbl_frame.pack(fill="both", expand=True, padx=20, pady=4)
        for col in self.cols:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, width=110, stretch=False)
        self.tree.tag_configure("bh_contact", background=CON_CHILD_BG, foreground=CON_CHILD_FG)
        self.tree.tag_configure("bh_company", background=CO_CHILD_BG,  foreground=CO_CHILD_FG)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_double_click_main)
        self.tree.bind("<<TreeviewSelect>>", self.refresh_dripify_urls, add="+")

        self.show_panel("bullhorn")

    def show_panel(self, key):
        for k, p in self.panels.items():
            p.pack_forget()
        self.panels[key].pack(fill="x")
        for k, b in self._nav_buttons.items():
            if k == key:
                b.configure(text_color=WHITE, fg_color=SURFACE)
            else:
                b.configure(text_color=MUTED, fg_color="transparent")

    # ── Panel: Bullhorn ─────────────────────────────────────────────────────────
    def _build_bh_panel(self, panel):
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", pady=10, padx=14)
        ghost_btn(row, "Audit Contacts",  self.start_audit,         width=130, accent=BLUE).pack(side="left", padx=3)
        ghost_btn(row, "Audit Companies", self.start_company_audit, width=140, accent=PURPLE).pack(side="left", padx=3)
        solid_btn(row, "Sync Selected →", self.start_sync,          width=140).pack(side="right", padx=3)

    # ── Panel: Instantly ────────────────────────────────────────────────────────
    def _build_instantly_panel(self, panel):
        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))
        self.campaign_search_var = ctk.StringVar()
        srch = ctk.CTkEntry(
            top, textvariable=self.campaign_search_var, width=280,
            placeholder_text="Search campaigns...",
            fg_color=SURFACE, border_color=HAIR, border_width=1,
            text_color=WHITE, corner_radius=8,
            font=ctk.CTkFont(FONT, 12))
        srch.pack(side="left", padx=(0, 6))
        srch.bind("<Return>", lambda e: self.search_campaigns())
        ghost_btn(top, "Search", self.search_campaigns, width=80).pack(side="left", padx=3)
        ghost_btn(top, "Refresh All", lambda: self.search_campaigns(fetch_all=True),
                  width=100).pack(side="left", padx=3)
        solid_btn(top, "Add Leads →", self.add_leads_to_campaign,
                  width=130).pack(side="right", padx=3)

        list_wrap = ctk.CTkFrame(panel, fg_color=SURFACE, corner_radius=8, height=78,
                                 border_width=1, border_color=HAIR)
        list_wrap.pack(fill="x", padx=14, pady=4)
        list_wrap.pack_propagate(False)
        sb = tk.Scrollbar(list_wrap, orient="vertical")
        self.campaign_listbox = tk.Listbox(
            list_wrap, yscrollcommand=sb.set,
            bg=SURFACE, fg=WHITE, selectbackground=GOLD, selectforeground="black",
            font=(FONT, 11), relief="flat", borderwidth=0,
            highlightthickness=0, activestyle="none")
        sb.configure(command=self.campaign_listbox.yview)
        sb.pack(side="right", fill="y", pady=4)
        self.campaign_listbox.pack(fill="both", expand=True, padx=8, pady=6)
        self.campaign_listbox.bind("<<ListboxSelect>>", self._on_campaign_select)

        self.selected_campaign_label = ctk.CTkLabel(
            panel, text="No campaign selected", text_color=MUTED,
            font=ctk.CTkFont(FONT, 11))
        self.selected_campaign_label.pack(anchor="w", padx=16, pady=(2, 10))

    # ── Panel: Dripify ──────────────────────────────────────────────────────────
    def _build_dripify_panel(self, panel):
        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(top, text="LinkedIn URLs of selected rows — updates live",
                     text_color=MUTED, font=ctk.CTkFont(FONT, 11)).pack(side="left")
        solid_btn(top, "Copy All", self.copy_dripify_urls, width=100).pack(side="right", padx=3)

        self.dripify_box = ctk.CTkTextbox(
            panel, fg_color=SURFACE, text_color=WHITE,
            font=ctk.CTkFont("SF Mono", 11), height=92, wrap="none",
            border_width=1, border_color=HAIR, corner_radius=8)
        self.dripify_box.pack(fill="x", padx=14, pady=(4, 4))

        self.dripify_count_label = ctk.CTkLabel(
            panel, text="0 URL(s)", text_color=MUTED,
            font=ctk.CTkFont(FONT, 11))
        self.dripify_count_label.pack(anchor="w", padx=16, pady=(0, 10))

    def refresh_dripify_urls(self, event=None):
        if not hasattr(self, "dripify_box"):
            return
        urls = []
        for it in self.tree.selection():
            if it in self._child_data:
                continue
            v = self.tree.item(it)["values"]
            url = str(v[23]).strip()
            if url and url.lower() not in ("nan", "none"):
                urls.append(url)
        self.dripify_box.delete("1.0", "end")
        self.dripify_box.insert("1.0", "\n".join(urls))
        self.dripify_count_label.configure(text=f"{len(urls)} URL(s)")

    def copy_dripify_urls(self):
        content = self.dripify_box.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Nothing to Copy", "Select rows in the main table first.")
            return
        self.clipboard_clear()
        self.clipboard_append(content)
        n = len(content.splitlines())
        self.log(f"DRIPIFY: Copied {n} LinkedIn URL(s) to clipboard.")

    # ── Instantly: campaign search & lead import ───────────────────────────────
    def search_campaigns(self, fetch_all=False):
        q = "" if fetch_all else self.campaign_search_var.get().strip()
        _sfx = f' for "{q}"' if q else ''
        self.log(f"INSTANTLY: Searching campaigns{_sfx}...")
        def _run():
            try:
                params = {"limit": 50}
                if q:
                    params["search"] = q
                r = requests.get(f"{IN_BASE_URL}/campaigns",
                                 headers=instantly_headers(), params=params, timeout=15)
                data = r.json()
                items = data if isinstance(data, list) else data.get("items", data.get("data", []))
                self.campaigns_list = [
                    {"id": c.get("id", c.get("campaign_id", "")),
                     "name": c.get("name", "(unnamed)")} for c in items
                ]
                self.after(0, self._populate_campaign_list)
                self.after(0, lambda: self.log(f"INSTANTLY: Found {len(self.campaigns_list)} campaign(s)."))
            except Exception as e:
                self.after(0, lambda msg=str(e): self.log(f"INSTANTLY ERROR: {msg}"))
        threading.Thread(target=_run, daemon=True).start()

    def _populate_campaign_list(self):
        self.campaign_listbox.delete(0, "end")
        for c in self.campaigns_list:
            self.campaign_listbox.insert("end", f"  {c['name']}")

    def _on_campaign_select(self, event):
        sel = self.campaign_listbox.curselection()
        if not sel:
            return
        c = self.campaigns_list[sel[0]]
        self.selected_campaign_label.configure(text=f"Selected: {c['name']}", text_color=GOLD)

    def add_leads_to_campaign(self):
        sel = self.campaign_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Campaign", "Search for and select a campaign first.")
            return
        rows = [it for it in self.tree.selection() if it not in self._child_data]
        if not rows:
            messagebox.showwarning("No Rows", "Select rows in the main table to import as leads.")
            return
        campaign = self.campaigns_list[sel[0]]
        self._show_instantly_options_popup(campaign, rows)

    def _show_instantly_options_popup(self, campaign, rows):
        pop = ctk.CTkToplevel(self)
        pop.title("Push to Instantly")
        pop.geometry("460x360")
        pop.configure(fg_color=BG)
        pop.transient(self)
        pop.grab_set()

        ctk.CTkLabel(pop, text="Push Leads to Instantly",
                     font=ctk.CTkFont("SF Pro Text", 16, "bold"),
                     text_color=GOLD).pack(pady=(18, 2))
        ctk.CTkLabel(pop, text=f"Campaign:  {campaign['name']}",
                     font=ctk.CTkFont("SF Pro Text", 12),
                     text_color=WHITE).pack(pady=(0, 12))

        card = ctk.CTkFrame(pop, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", padx=24, pady=4)

        ctk.CTkLabel(card, text="Check for duplicates across all:",
                     font=ctk.CTkFont("SF Pro Text", 12, "bold"),
                     text_color=WHITE).pack(anchor="w", padx=16, pady=(12, 4))

        dup_campaigns = ctk.BooleanVar(value=True)
        dup_lists     = ctk.BooleanVar(value=True)
        dup_workspace = ctk.BooleanVar(value=True)
        verify_leads  = ctk.BooleanVar(value=False)

        chk_row = ctk.CTkFrame(card, fg_color="transparent")
        chk_row.pack(fill="x", padx=16, pady=(0, 8))
        for var, label in ((dup_campaigns, "Campaigns"),
                           (dup_lists, "Lists"),
                           (dup_workspace, "The Workspace")):
            ctk.CTkCheckBox(chk_row, text=label, variable=var,
                            fg_color=BLUE, hover_color="#409cff",
                            text_color=WHITE,
                            font=ctk.CTkFont("SF Pro Text", 12)).pack(side="left", padx=(0, 14))

        ctk.CTkCheckBox(card, text="Verify leads  (0.25 credits / row)",
                        variable=verify_leads,
                        fg_color=BLUE, hover_color="#409cff", text_color=WHITE,
                        font=ctk.CTkFont("SF Pro Text", 12)).pack(anchor="w", padx=16, pady=(0, 12))

        ctk.CTkLabel(pop, text=f"✓ Detected {len(rows)} data row(s)",
                     font=ctk.CTkFont("SF Pro Text", 13, "bold"),
                     text_color=GREEN).pack(pady=(14, 6))

        def _go():
            opts = {
                "skip_if_in_campaign":  dup_campaigns.get(),
                "skip_if_in_list":      dup_lists.get(),
                "skip_if_in_workspace": dup_workspace.get(),
                "verify_leads_on_import": verify_leads.get(),
            }
            pop.destroy()
            self.log(f"INSTANTLY: Adding {len(rows)} lead(s) to '{campaign['name']}'...")
            threading.Thread(target=self._run_add_leads,
                             args=(campaign["id"], campaign["name"], rows, opts),
                             daemon=True).start()

        pill_btn(pop, "⬆  UPLOAD ALL", GREEN, "#44df6e", _go,
                 width=200, height=42).pack(pady=(4, 16))

    def _run_add_leads(self, campaign_id, campaign_name, items, opts=None):
        opts = opts or {}
        ok = fail = dup = 0
        for it in items:
            # Skip child rows — only process parent rows
            if it in self._child_data:
                continue
            v     = self.tree.item(it)["values"]
            first = str(v[2]).strip()
            last  = str(v[3]).strip()
            email = str(v[5]).strip()
            if not email:
                self.log(f"INSTANTLY SKIP: No email for {first} {last}.")
                continue
            lead = {
                "email":         email,
                "first_name":    first,
                "last_name":     last,
                "company_name":  str(v[16]).strip(),
                "phone":         self.fix_phone(self.csv_data_cache.get(it, {}).get("Work Phone", str(v[8]))),
                "personalization": str(v[4]).strip(),
                "website":       str(v[17]).strip(),
                "custom_variables": {
                    "linkedin":  str(v[23]).strip(),
                    "county":    str(v[10]).strip(),
                    "industry":  str(v[12]).strip(),
                },
            }
            payload = {
                "campaign_id":          campaign_id,
                "leads":                [lead],
                "skip_if_in_workspace": opts.get("skip_if_in_workspace", False),
                "skip_if_in_campaign":  opts.get("skip_if_in_campaign", False),
                "skip_if_in_list":      opts.get("skip_if_in_list", False),
            }
            if opts.get("verify_leads_on_import"):
                payload["verify_leads_on_import"] = True
            try:
                r = requests.post(f"{IN_BASE_URL}/leads/add",
                                  headers=instantly_headers(), json=payload, timeout=15)
                if r.status_code in (200, 201):
                    res = r.json() if r.text else {}
                    uploaded   = res.get("leads_uploaded", 1)
                    duplicated = res.get("duplicated_leads", 0) + res.get("skipped_count", 0)
                    if duplicated and not uploaded:
                        dup += 1
                        self.log(f"INSTANTLY DUPLICATE: {email} already exists — skipped.")
                        self.after(0, lambda i=it: self.tree.set(i, "Action", "⚠️ DUPLICATE"))
                    else:
                        ok += 1
                        self.after(0, lambda i=it: self.tree.set(i, "Action", "✅ INSTANTLY"))
                else:
                    fail += 1
                    self.log(f"INSTANTLY FAIL [{r.status_code}]: {r.text[:120]}")
            except Exception as e:
                fail += 1
                self.log(f"INSTANTLY ERROR: {e}")
        self.log(f"INSTANTLY DONE: {ok} added, {dup} duplicate(s), {fail} failed  (campaign: {campaign_name})")

    # ── Bullhorn: data operations ──────────────────────────────────────────────
    def clear_all_data(self):
        if not messagebox.askyesno("Clear All", "Delete all rows and clear session cache?"):
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.bullhorn_cache.clear(); self.co_search_cache.clear()
        self.csv_data_cache.clear(); self.company_map.clear()
        self.manual_contact_id.clear(); self._child_data.clear()
        self.log("SYSTEM: All tables and session caches cleared.")

    def mark_for_creation(self):
        for it in self.tree.selection():
            # Work on parent row if a child is selected
            parent = self._child_data.get(it, {}).get("parent", it)
            v = self.tree.item(parent)["values"]
            self.tree.set(parent, "BH Company", "➕ CREATE NEW")
            self.company_map.pop(parent, None)
            self.log(f"SYSTEM: Company '{v[16]}' flagged for new creation.")

    def mark_contact_as_new(self):
        for it in self.tree.selection():
            parent = self._child_data.get(it, {}).get("parent", it)
            self.tree.set(parent, "Action", "IMPORT (FORCE)")
            self.manual_contact_id.pop(parent, None)
            self.log("SYSTEM: Forced Import status for selected contact row.")

    def start_email_verification(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select rows to verify.")
            return
        self.log(f"EMAIL SERVICE: Verifying {len(sel)} contacts...")
        threading.Thread(target=self.run_verify_thread, args=(sel,), daemon=True).start()

    def run_verify_thread(self, items):
        for it in items:
            if it in self._child_data:
                continue
            v  = self.tree.item(it)["values"]
            em = str(v[5]).strip()
            if not em or "@" not in em:
                self.after(0, lambda i=it: self.tree.set(i, "Email Status", "❌ INVALID"))
                continue
            url = (f"https://api.millionverifier.com/api/v3/"
                   f"?api={MILLION_API_KEY}&email={em}&timeout=15")
            try:
                r = requests.get(url, timeout=20).json()
                q   = r.get("quality", "unknown").upper()
                sub = r.get("subresult", "none").replace("_", " ").title()
                ic  = "✅" if q == "GOOD" else "❌"
                self.after(0, lambda i=it, ql=q, icon=ic, s=sub: (
                    self.tree.set(i, "Email Status", f"{icon} {ql}"),
                    self.tree.set(i, "Sub-Result", s),
                ))
                self.log(f"VERIFIED: {em} -> {q} | {sub}")
            except Exception as e:
                self.log(f"VERIFY ERROR: {em}: {e}")
        self.log("EMAIL SERVICE: Batch verification complete.")

    def export_to_csv(self):
        items = self.tree.get_children()
        if not items:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            data = []
            for it in items:
                if it in self._child_data:
                    continue
                v = list(self.tree.item(it)["values"])
                v[8]  = self.fix_phone(v[8])
                v[19] = self.fix_phone(v[19])
                data.append(v[2:])
            pd.DataFrame(data, columns=self.cols[2:]).to_csv(
                path, index=False, encoding="utf-8-sig")
            self.log(f"EXPORT SUCCESS: {len(data)} records saved to {path}")
            messagebox.showinfo("Export", "CSV Saved Successfully.")
        except Exception as e:
            self.log(f"EXPORT ERROR: {e}")

    # ── Click handler — column-aware ──────────────────────────────────────────
    def on_tree_click(self, event):
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not row:
            return

        data = self._child_data.get(row)

        if data is not None:
            # Clicked a child row — toggle its checkbox
            self._handle_child_click(row, data)
            return

        # Parent row: col #1 = Action → toggle contact children
        #             col #2 = BH Company → toggle company children
        if col == "#1":
            self._toggle_children(row, "contact")
        elif col == "#2":
            self._toggle_children(row, "company")

    def _toggle_children(self, parent, kind):
        existing = [c for c in self.tree.get_children(parent)
                    if self._child_data.get(c, {}).get("type") == kind]
        if existing:
            # Already expanded — collapse and remove
            for c in existing:
                del self._child_data[c]
                self.tree.delete(c)
            self.tree.item(parent, open=False)
        else:
            # Expand: insert from cache
            if kind == "contact" and parent in self.bullhorn_cache:
                self._insert_contact_children(parent, self.bullhorn_cache[parent])
            elif kind == "company" and parent in self.co_search_cache:
                self._insert_company_children(parent, self.co_search_cache[parent])

    def _handle_child_click(self, it, data):
        parent   = data["parent"]
        cv       = list(self.tree.item(it)["values"])
        checked  = "☑" in str(cv[0])

        if checked:
            # Uncheck — clear resolution
            cv[0] = cv[0].replace("☑", "☐")
            self.tree.item(it, values=cv)
            if data["type"] == "contact":
                self.manual_contact_id.pop(parent, None)
                cnt = len(self.bullhorn_cache.get(parent, []))
                self.tree.set(parent, "Action", "MATCHED" if cnt == 1 else f"MULTI ({cnt})")
                self.log(f"RESOLUTION: Contact deselected for row.")
            elif data["type"] == "company":
                self.company_map.pop(parent, None)
                cnt = len(self.co_search_cache.get(parent, []))
                self.tree.set(parent, "BH Company", f"⚠️ MULTI ({cnt})")
                self.log(f"RESOLUTION: Company deselected for row.")
        else:
            # Check this, uncheck siblings of same type
            for sibling in self.tree.get_children(parent):
                sd = self._child_data.get(sibling)
                if sd and sd["type"] == data["type"]:
                    sv = list(self.tree.item(sibling)["values"])
                    sv[0] = sv[0].replace("☑", "☐")
                    self.tree.item(sibling, values=sv)
            cv[0] = cv[0].replace("☐", "☑")
            self.tree.item(it, values=cv)
            if data["type"] == "contact":
                self.manual_contact_id[parent] = data["id"]
                self.tree.set(parent, "Action", f"UPDATE ({data['id']})")
                self.log(f"RESOLUTION: Contact '{data['name']}' (ID: {data['id']}) selected.")
            elif data["type"] == "company":
                self.company_map[parent] = {"id": data["id"], "name": data["name"]}
                self.tree.set(parent, "BH Company", f"{data['name']} ({data['id']})")
                self.log(f"RESOLUTION: Company '{data['name']}' (ID: {data['id']}) linked.")

    # ── Sync ──────────────────────────────────────────────────────────────────
    def run_sync_thread(self, token, items):
        count = 0
        # Filter out child rows
        parent_items = [it for it in items if it not in self._child_data]
        self.log(f"SYNC START: Processing {len(parent_items)} item(s)...")
        for it in parent_items:
            act   = self.tree.set(it, "Action")
            v     = self.tree.item(it)["values"]
            bh_co = self.tree.set(it, "BH Company")
            csv_row   = self.csv_data_cache.get(it, {})
            con_phone = self.fix_phone(csv_row.get("Work Phone",           str(v[8])))
            co_phone  = self.fix_phone(csv_row.get("Company Phone Number", str(v[19])))

            tid = self.manual_contact_id.get(it)
            if not tid and "IMPORT (FORCE)" not in act and ("UPDATE" in act or "MATCHED" in act):
                if it in self.bullhorn_cache:
                    tid = self.bullhorn_cache[it][0]["id"]

            cid = self.company_map.get(it, {}).get("id")
            if not cid and "(" in bh_co and ")" in bh_co:
                try: cid = bh_co.split("(")[-1].replace(")", "")
                except: pass
            if not cid and bh_co != "➕ CREATE NEW" and v[16]:
                for pm in self.company_map.values():
                    if pm.get("name") == v[16]:
                        cid = pm["id"]; break

            needs_creation = (not cid and str(v[16]).strip() and
                              (bh_co in ("➕ CREATE NEW", "❌ NO MATCH", "Not Linked")
                               or ("IMPORT" in act)))
            if needs_creation:
                co_pay = {
                    "name": v[16], "companyURL": v[17], "phone": co_phone,
                    "customTextBlock5": self.clean_list_str(v[12]),
                    "address": {"city": v[20], "state": v[21], "countryID": 2359},
                    "linkedinProfileName": str(v[18]),
                    "status": "Active Account",
                }
                self.log(f"SYNC: Creating company '{v[16]}' — enriching…")
                enriched = enrich_company(
                    email=str(v[5]),           # contact email for domain extraction
                    website_url=str(v[17]),    # company website
                    linkedin_raw=str(v[18]),   # LinkedIn slug/URL
                    log=self.log,
                )
                co_pay.update(enriched)
                if "companyDescription" in enriched:
                    self.log(f"  → Description scraped ({len(enriched['companyDescription'])} chars)")
                if "customTextBlock1" in enriched:
                    self.log(f"  → Email domains: {enriched['customTextBlock1']}")
                self.log(f"SYNC: Creating company '{v[16]}' with phone '{co_phone}'")
                try:
                    c_res = requests.put(
                        f"{self.bh_base_url}entity/ClientCorporation?BhRestToken={token}",
                        json=co_pay, timeout=20).json()
                    cid = c_res.get("changedEntityId")
                    if cid:
                        self.company_map[it] = {"id": cid, "name": v[16]}
                        self.log(f"SYNC: Created Company '{v[16]}' (ID: {cid})")
                        self.after(0, lambda i=it, nm=v[16], nid=cid:
                                   self.tree.set(i, "BH Company", f"{nm} ({nid})"))
                    else:
                        self.log(f"SYNC ERROR: Company creation rejected: {str(c_res)[:300]}")
                except Exception as e:
                    self.log(f"SYNC ERROR: Company creation failed: {e}")
            elif not cid and str(v[16]).strip():
                self.log(f"SYNC NOTE: No company linked or created for '{v[16]}' "
                         f"(BH Company='{bh_co}', Action='{act}').")
            pay = {
                "firstName": v[2], "lastName": v[3], "name": f"{v[2]} {v[3]}",
                "email": v[5], "occupation": v[4], "phone": con_phone,
                "customText1": str(v[23]),
                "address": {"city": v[9], "state": v[10], "countryID": 2359},
                "customTextBlock2": self.clean_list_str(v[14]),
                "customTextBlock4": self.clean_list_str(v[12]),
                "customTextBlock5": self.clean_list_str(v[13]),
                "comments": v[15],
            }
            if cid:
                pay["clientCorporation"] = {"id": cid}
            try:
                if tid and "IMPORT (FORCE)" not in act:
                    r = requests.post(
                        f"{self.bh_base_url}entity/ClientContact/{tid}?BhRestToken={token}",
                        json=pay)
                    if r.status_code == 200:
                        self.log(f"SYNC SUCCESS: Updated {v[2]} {v[3]} (ID: {tid})")
                        self.after(0, lambda i=it: self.tree.set(i, "Action", "✅ UPDATED"))
                        count += 1
                else:
                    r = requests.put(
                        f"{self.bh_base_url}entity/ClientContact?BhRestToken={token}",
                        json=pay)
                    if r.status_code in (200, 201):
                        self.log(f"SYNC SUCCESS: Created {v[2]} {v[3]}")
                        self.after(0, lambda i=it: self.tree.set(i, "Action", "✅ CREATED"))
                        count += 1
            except Exception as e:
                self.log(f"SYNC ERROR: {v[2]} {v[3]}: {e}")
        self.log(f"SYNC END: {count} record(s) synchronised.")
        if count > 0:
            self.after(0, lambda: messagebox.showinfo(
                "Sync Complete", f"Successfully processed {count} records."))

    # ── Contact audit — inserts child match rows ───────────────────────────────
    def run_audit_thread(self, token, items):
        fields = ("id,name,occupation,comments,email,customText1,customTextBlock2,"
                  "customTextBlock4,customTextBlock5,address(city,state,countryName),"
                  "mobile,phone,dateAdded,status,massMailOptOut,clientCorporation(id,name),firstName,lastName")
        parent_items = [it for it in items if it not in self._child_data]
        self.log(f"AUDIT CONTACTS: Searching {len(parent_items)} row(s)...")
        for it in parent_items:
            v    = self.tree.item(it)["values"]
            e, n = str(v[5]), f"{v[2]} {v[3]}"
            try:
                _bh_q = '(email:"' + e + '" OR name:"' + n + '") AND isDeleted:0'
                url = (f"{self.bh_base_url}search/ClientContact"
                       f"?query={urllib.parse.quote(_bh_q)}"
                       f"&fields={fields}&BhRestToken={token}")
                matches = requests.get(url).json().get("data", [])
                if matches:
                    self.bullhorn_cache[it] = matches
                    act = "MATCHED" if len(matches) == 1 else f"MULTI ({len(matches)})"
                    self.after(0, lambda i=it, a=act: self.tree.set(i, "Action", a))
                    self.log(f"AUDIT: {len(matches)} match(es) for '{n}'. Click Action cell to expand.")
                else:
                    self.after(0, lambda i=it: self.tree.set(i, "Action", "IMPORT"))
                    self.log(f"AUDIT: No match for '{n}' — flagged for import.")
            except Exception as e:
                self.log(f"AUDIT ERROR: {n}: {e}")
        self.log("AUDIT CONTACTS: Batch finished.")

    def _insert_contact_children(self, parent, matches):
        # Remove old contact children
        for child in list(self.tree.get_children(parent)):
            if self._child_data.get(child, {}).get("type") == "contact":
                del self._child_data[child]
                self.tree.delete(child)
        linked_cid = self.manual_contact_id.get(parent)
        for c in matches:
            a  = c.get("address", {})
            da = (datetime.fromtimestamp(c["dateAdded"] / 1000).strftime("%Y-%m-%d")
                  if c.get("dateAdded") else "")
            box = "☑" if str(c["id"]) == str(linked_cid) else "☐"
            vals = [""] * len(self.cols)
            vals[0]  = f"{box}  ↳ {c.get('name', '?')}  [{c.get('status', '')}]"
            vals[1]  = c.get("clientCorporation", {}).get("name", "")
            vals[2]  = c.get("firstName", "")
            vals[3]  = c.get("lastName", "")
            vals[4]  = c.get("occupation", "")
            vals[5]  = c.get("email", "")
            vals[6]  = c.get("status", "")
            vals[7]  = da
            vals[8]  = c.get("phone", "")
            vals[9]  = a.get("city", "")
            vals[10] = c.get("customTextBlock2", "")
            vals[11] = a.get("countryName", "")
            vals[23] = c.get("customText1", "")
            child = self.tree.insert(parent, "end", values=vals, tags=("bh_contact",))
            self._child_data[child] = {
                "type": "contact", "parent": parent,
                "id": c["id"], "name": c.get("name", ""),
            }
        self.tree.item(parent, open=True)

    # ── Company audit — inserts child match rows ───────────────────────────────
    def run_company_audit(self, token, items):
        parent_items = [it for it in items if it not in self._child_data]
        self.log(f"AUDIT COMPANIES: Searching {len(parent_items)} row(s)...")
        for it in parent_items:
            csv_co = str(self.csv_data_cache.get(it, {}).get("Company", "")).strip()
            if not csv_co:
                self.log("AUDIT SKIP: No company name on row."); continue
            words, m = csv_co.split(), []
            while words and not m:
                s = " ".join(words).replace('"', "").strip()
                try:
                    _co_q = 'name:("' + s + '") AND NOT status:Archive'
                    d = requests.get(
                        f"{self.bh_base_url}search/ClientCorporation"
                        f"?query={urllib.parse.quote(_co_q)}"
                        f"&fields=id,name,status,address(city,state,countryName),phone,"
                        f"companyURL,customTextBlock5,linkedinProfileName"
                        f"&BhRestToken={token}").json()
                    m = d.get("data", [])
                except Exception as e:
                    self.log(f"AUDIT ERROR: {e}"); break
                if not m:
                    words.pop()
            if m:
                fi, fn, c = m[0]["id"], m[0]["name"], len(m)
                self.co_search_cache[it] = m
                if c == 1:
                    # Single match — auto-link immediately; details still expandable
                    self.after(0, lambda i=it, nid=fi, nm=fn:
                               self.tree.set(i, "BH Company", f"{nm} ({nid})"))
                    self.after(0, lambda i=it, nid=fi, nm=fn:
                               self.company_map.update({i: {"id": nid, "name": nm}}))
                    self.log(f"AUDIT: Auto-linked '{fn}' (ID: {fi}) to '{csv_co}'. Click BH Company cell to view details.")
                else:
                    # Multiple matches — let user click BH Company to expand and pick
                    self.after(0, lambda i=it, cnt=c:
                               self.tree.set(i, "BH Company", f"⚠️ MULTI ({cnt})"))
                    self.log(f"AUDIT: {c} matches for '{csv_co}'. Click BH Company cell to expand.")
            else:
                self.after(0, lambda i=it: self.tree.set(i, "BH Company", "❌ NO MATCH"))
                self.log(f"AUDIT: No match for '{csv_co}'.")
        self.log("AUDIT COMPANIES: Batch finished.")

    def _insert_company_children(self, parent, matches):
        # Remove old company children
        for child in list(self.tree.get_children(parent)):
            if self._child_data.get(child, {}).get("type") == "company":
                del self._child_data[child]
                self.tree.delete(child)
        linked_id = self.company_map.get(parent, {}).get("id")
        for c in matches:
            a = c.get("address", {})
            box = "☑" if str(c["id"]) == str(linked_id) else "☐"
            vals = [""] * len(self.cols)
            vals[0]  = f"{box}  ↳ 🏢 {c.get('name', '?')}"
            vals[1]  = f"ID: {c['id']}  •  {c.get('status', '')}"
            vals[9]  = a.get("city", "")
            vals[10] = a.get("state", "")
            vals[11] = a.get("countryName", "")
            vals[17] = c.get("companyURL", "")
            vals[18] = c.get("linkedinProfileName", "")
            vals[19] = self.fix_phone(c.get("phone", ""))
            child = self.tree.insert(parent, "end", values=vals, tags=("bh_company",))
            self._child_data[child] = {
                "type": "company", "parent": parent,
                "id": c["id"], "name": c.get("name", ""),
                "raw": c,
            }
        self.tree.item(parent, open=True)

    # ── Update company — uses CSV data so phone is always correct ─────────────
    def update_company_in_bh(self):
        t = self._token()
        if not t:
            messagebox.showwarning("Not Connected", "Bullhorn is not connected yet.")
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select the main row (or a company child) to update.")
            return

        it     = sel[0]
        c_data = self._child_data.get(it)

        if c_data and c_data["type"] == "company":
            # User clicked a company child row — update that specific company
            parent  = c_data["parent"]
            co_id   = c_data["id"]
            co_name = c_data["name"]
            pv      = self.tree.item(parent)["values"]
            csv_row = self.csv_data_cache.get(parent, {})
        elif c_data is None:
            # User clicked a parent row — find its linked company
            bh_co = self.tree.set(it, "BH Company")
            if "(" in bh_co and ")" in bh_co:
                co_id = bh_co.split("(")[-1].replace(")", "").strip()
                co_name = bh_co.split("(")[0].strip()
            elif it in self.company_map:
                co_id   = self.company_map[it]["id"]
                co_name = self.company_map[it]["name"]
            else:
                messagebox.showwarning("No Company", "No company linked to this row. Run company audit first.")
                return
            pv      = self.tree.item(it)["values"]
            csv_row = self.csv_data_cache.get(it, {})
        else:
            messagebox.showwarning("Wrong Row", "Select the main row or a company child row.")
            return

        co_phone = self.fix_phone(csv_row.get("Company Phone Number", str(pv[19])))
        payload = {
            "name":               str(pv[16]),
            "phone":              co_phone,
            "companyURL":         str(pv[17]),
            "linkedinProfileName":str(pv[18]),
            "customTextBlock5":   self.clean_list_str(pv[12]),
            "address": {
                "city":      str(pv[20]),
                "state":     str(pv[21]),
                "countryID": 2359,
            },
        }
        self.log(f"UPDATE: Sending '{co_name}' (ID: {co_id}) phone='{co_phone}'...")
        def _push():
            try:
                r = requests.post(
                    f"{self.bh_base_url}entity/ClientCorporation/{co_id}?BhRestToken={t}",
                    json=payload, timeout=20)
                if r.status_code in (200, 201, 204):
                    self.log(f"UPDATE SUCCESS: '{co_name}' updated.")
                    self.after(0, lambda: messagebox.showinfo(
                        "Update Complete", f"Company '{co_name}' updated successfully."))
                else:
                    self.log(f"UPDATE FAILED: {r.status_code} — {r.text}")
                    self.after(0, lambda: messagebox.showerror(
                        "Update Failed", f"API Error {r.status_code}: {r.text}"))
            except Exception as e:
                self.log(f"UPDATE ERROR: {e}")
        threading.Thread(target=_push, daemon=True).start()

    def toggle_logs(self):
        if self.log_visible:
            self.term_wrap.pack_forget()
        else:
            self.term_wrap.pack(side="bottom", fill="x", padx=20, pady=(4, 14))
        self.log_visible = not self.log_visible

    def load_file(self):
        p = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not p: return
        self.log(f"LOAD: Reading {p}...")
        try:
            f = lambda x: self.fix_phone(x)
            df = pd.read_csv(p, converters={
                "Work Phone": f, "Company Phone Number": f,
                "Mobile Phone": f, "Company": str,
            }).fillna("")
            for _, r in df.iterrows():
                co_li = r.get("Company LinkedIn URL", r.get("Company Linkedin URL", ""))
                v = [
                    "?", "Not Linked",
                    r.get("First Name", ""),   r.get("Surname", ""),
                    r.get("Position", ""),     r.get("Email", ""),
                    "", "",                    r.get("Work Phone", ""),
                    r.get("City / Town", ""),  self.clean_list_str(r.get("County", "")),
                    r.get("Country", ""),      self.clean_list_str(r.get("Custom Industry", "")),
                    self.clean_list_str(r.get("Custom Type of Work", "")),
                    self.clean_list_str(r.get("Custom County", "")),
                    r.get("Final General Comments", ""),
                    r.get("Company", ""),      r.get("Company Website", ""),
                    co_li,                     r.get("Company Phone Number", ""),
                    r.get("Company City/Town", ""), r.get("Company County", ""),
                    r.get("Company Country", ""),   r.get("Linked In URL", ""),
                ]
                it = self.tree.insert("", "end", values=v)
                self.csv_data_cache[it] = r.to_dict()
            self.log(f"LOAD SUCCESS: {len(df)} rows imported.")
        except Exception as e:
            self.log(f"LOAD ERROR: {e}")

    def select_all(self):
        # Select only parent rows
        parents = [it for it in self.tree.get_children() if it not in self._child_data]
        self.tree.selection_set(parents)

    def start_audit(self):
        t, s = self._token(), [it for it in self.tree.selection() if it not in self._child_data]
        if t and s: threading.Thread(target=self.run_audit_thread, args=(t, s), daemon=True).start()

    def start_company_audit(self):
        t, s = self._token(), [it for it in self.tree.selection() if it not in self._child_data]
        if t and s: threading.Thread(target=self.run_company_audit, args=(t, s), daemon=True).start()

    def start_sync(self):
        t, s = self._token(), [it for it in self.tree.selection() if it not in self._child_data]
        if t and s: threading.Thread(target=self.run_sync_thread, args=(t, s), daemon=True).start()

    def _apply_cell_edit(self, item, idx, new_val):
        """Write an edited value into the tree AND csv_data_cache (sync reads from cache)."""
        vls = list(self.tree.item(item, "values"))
        # Run phone fields through the cleaner
        if idx in (8, 19):
            new_val = self.fix_phone(new_val)
        vls[idx] = new_val
        self.tree.item(item, values=vls)
        csv_key = self.col_to_csv.get(idx)
        if csv_key and item in self.csv_data_cache:
            self.csv_data_cache[item][csv_key] = new_val
        self.log(f"EDIT: '{self.cols[idx]}' updated to '{new_val}'.")

    def on_double_click_main(self, e):
        i, col = self.tree.identify_row(e.y), self.tree.identify_column(e.x)
        if not i or not col or col == "#0": return
        # Don't allow editing child rows
        if i in self._child_data: return
        idx = int(col[1:]) - 1
        vls = list(self.tree.item(i, "values"))
        x, y, w, h = self.tree.bbox(i, col)
        ent = tk.Entry(self.tree, bg=SURFACE, fg=WHITE, relief="flat")
        ent.insert(0, vls[idx]); ent.place(x=x, y=y, width=w, height=h); ent.focus_set()
        def save(ev=None):
            self._apply_cell_edit(i, idx, ent.get())
            ent.destroy()
        ent.bind("<Return>", save)
        ent.bind("<FocusOut>", lambda ev: ent.destroy())

    def open_edit_row_popup(self):
        sel = [it for it in self.tree.selection() if it not in self._child_data]
        if not sel:
            messagebox.showwarning("No Row", "Select a row in the main table to edit.")
            return
        item = sel[0]
        vls  = list(self.tree.item(item, "values"))

        pop = ctk.CTkToplevel(self)
        pop.title("Edit Row")
        pop.geometry("560x680")
        pop.configure(fg_color=BG)
        pop.transient(self)
        pop.grab_set()

        ctk.CTkLabel(pop, text=f"Edit:  {vls[2]} {vls[3]}",
                     font=ctk.CTkFont("SF Pro Text", 15, "bold"),
                     text_color=GOLD).pack(pady=(16, 8))

        body = ctk.CTkScrollableFrame(pop, fg_color=CARD, corner_radius=12)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        entries = {}
        for idx in sorted(self.col_to_csv.keys()):
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(row, text=self.cols[idx], width=170, anchor="w",
                         text_color=MUTED,
                         font=ctk.CTkFont("SF Pro Text", 11)).pack(side="left")
            ent = ctk.CTkEntry(row, fg_color=SURFACE, border_color=SURFACE,
                               text_color=WHITE,
                               font=ctk.CTkFont("SF Pro Text", 12))
            ent.insert(0, str(vls[idx]))
            ent.pack(side="left", fill="x", expand=True, padx=(8, 0))
            entries[idx] = ent

        def _save():
            for idx, ent in entries.items():
                new_val = ent.get()
                if str(vls[idx]) != new_val:
                    self._apply_cell_edit(item, idx, new_val)
            pop.destroy()
            self.log("EDIT: Row saved.")

        btns = ctk.CTkFrame(pop, fg_color="transparent")
        btns.pack(pady=(2, 14))
        pill_btn(btns, "💾  Save",  GREEN,   "#44df6e", _save,       width=130, height=38).pack(side="left", padx=8)
        pill_btn(btns, "Cancel",    SURFACE, "#48484a", pop.destroy, width=110, height=38).pack(side="left", padx=8)


    def reconnect(self):
        """Called by the shell's global reload button."""
        self._bh_connect()


def _standalone():
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.title("Import Contacts Tool for BH  •  v2.0")
    root.geometry("1380x860")
    root.minsize(1100, 700)
    tool = BullhornImportTool(root)
    tool.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    _standalone()
