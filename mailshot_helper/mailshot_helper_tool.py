"""
Cornerstone — Mailshot Filter Tool
Dark green theme, CustomTkinter rounded UI, Bullhorn CRM + Instantly integration
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.filedialog import asksaveasfilename
import customtkinter as ctk
import threading
import requests
import json
import os
import csv
import time
import re
import base64
import io
import urllib.parse
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import platform as _platform

# ── Platform flags ────────────────────────────────────────────────────────────
IS_WINDOWS = _platform.system() == "Windows"
IS_MAC     = _platform.system() == "Darwin"

def _screen_center(W, H):
    """Calculate top-left corner to center a WxH window on screen."""
    import tkinter as _tk
    r = _tk.Tk()
    r.withdraw()
    sw = r.winfo_screenwidth()
    sh = r.winfo_screenheight()
    r.destroy()
    return (sw - W) // 2, (sh - H) // 2

def _popup_show(window, W, H, cx, cy, offset=26):
    """
    Show a popup window centered with no flash-in-wrong-position.
    Uses withdraw() before positioning so the window is NEVER seen
    at the wrong location.
    macOS: fade-in + slide-up after positioning.
    Windows: instant appear at correct position.
    """
    # Hide immediately — before ANY geometry call
    window.withdraw()
    window.update_idletasks()

    if IS_WINDOWS:
        window.geometry(f"{W}x{H}+{cx}+{cy}")
        window.deiconify()
        window.lift()
        window.focus_force()
        return

    # macOS: start invisible and below final position
    window.attributes("-alpha", 0.0)
    window.geometry(f"{W}x{H}+{cx}+{cy + offset}")
    window.deiconify()

    def _animate(step=0):
        steps = 16
        ease  = 1 - (1 - step / steps) ** 3
        window.attributes("-alpha", min(ease, 1.0))
        y_off = int(offset * (1 - ease))
        window.geometry(f"{W}x{H}+{cx}+{cy + y_off}")
        if step < steps:
            window.after(12, lambda: _animate(step + 1))
    window.after(10, _animate)

def _popup_hide(window, on_done=None, overlay=None):
    """
    Hide a popup.
    macOS: fade-out animation then destroy.
    Windows: instant destroy.
    """
    if IS_WINDOWS:
        if overlay:
            try: overlay.destroy()
            except Exception: pass
        try: window.destroy()
        except Exception: pass
        if on_done: on_done()
        return
    def _step(alpha=1.0):
        alpha = max(alpha - 0.09, 0.0)
        try:
            window.attributes("-alpha", alpha)
            if overlay:
                overlay.attributes("-alpha", alpha * 0.45)
        except Exception:
            pass
        if alpha > 0:
            window.after(14, lambda: _step(alpha))
        else:
            if overlay:
                try: overlay.destroy()
                except Exception: pass
            try: window.destroy()
            except Exception: pass
            if on_done: on_done()
    _step()

def _show_overlay(parent):
    """
    Dim overlay behind a popup.
    macOS: semi-transparent black layer fades in.
    Windows: skip entirely (causes flickering).
    """
    if IS_WINDOWS:
        return None   # no overlay on Windows
    overlay = tk.Toplevel(parent)
    overlay.overrideredirect(True)
    overlay.attributes("-alpha", 0.0)
    overlay.configure(bg="#000000")
    parent.update_idletasks()
    overlay.geometry(f"{parent.winfo_width()}x{parent.winfo_height()}"
                     f"+{parent.winfo_rootx()}+{parent.winfo_rooty()}")
    overlay.lift()
    def _fade(a=0.0):
        a = min(a + 0.05, 0.45)
        overlay.attributes("-alpha", a)
        if a < 0.45: overlay.after(16, lambda: _fade(a))
    _fade()
    return overlay

# ── CustomTkinter global appearance ──────────────────────────────────────────
# Appearance mode is set by the host shell (CornerstoneTools); do not override here.
# ctk.set_appearance_mode("dark")  # <-- removed; shell controls this

# ─── CONFIG — loaded from config.json next to this script ────────────────────
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE  = os.path.join(_SCRIPT_DIR, "config.json")

def _load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[config] Failed to load config.json: {e}")
        return {}

_cfg = _load_config()

# Bullhorn
CLIENT_ID     = _cfg.get("bullhorn_client_id",     "YOUR_BULLHORN_CLIENT_ID")
CLIENT_SECRET = _cfg.get("bullhorn_client_secret",  "YOUR_BULLHORN_CLIENT_SECRET")
USERNAME      = _cfg.get("bullhorn_username",        "YOUR_BULLHORN_USERNAME")
PASSWORD      = _cfg.get("bullhorn_password",        "YOUR_BULLHORN_PASSWORD")
REDIRECT_URI  = _cfg.get("bullhorn_redirect_uri",   "https://welcome.bullhornstaffing.com")

# Instantly
INSTANTLY_API_KEY = _cfg.get("instantly_api_key",
    "YOUR_INSTANTLY_API_KEY")

# ─── LOGO ─────────────────────────────────────────────────────────────────────
# Looks for logo.png next to the script first; falls back to embedded base64.
# To use your own logo: drop a PNG named "logo.png" in the same folder as the script.
_LOGO_PATH = os.path.join(_SCRIPT_DIR, "logo.png")

# Embedded Cornerstone Project Source logo (gold arches, transparent bg)
_EMBEDDED_LOGO_B64 = (
    "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"
    "Hn1pagFAxBfv8XCSw9g0tC93mD5tKN13qJ3t3DO8anzbygNmSpOOtHLLHe+CD8AX/hqCUcNEzOIJ"
    "xAybpLbVcNYjx4GD7RedR57YiWwloLBTRpqZbZPA+yC2YbSmsEYPhfce/dV+28kEsKiNtoQPHG4+"
    "47x6a4+brlI9y+2B0eaAZB0kHL6lnBUSAGZY5wXKHgwLmjQ0wKuWz/udOTMn/Uo7zzMmTkECKEO9"
    "r/dXKgPbnntt3ev7hrd7L9RsNf1452M5965UUly2efl/GRxIPqfi2ykltcPDjb995Ok9P8pEpONc"
    "llp8znnRer0xoV1j7Hwq1NdXIQbMRWsXfvOJHXtuvuLCZaONLG8yUU0UzUpiaw88+sKkZqtTRzEP"
    "a7c6muX5cedEAGbMmFK7cP3CBpG0LahK4GalktTue/TFmSP19kHqWofF3JsYzVZLsuz7EuuESUOD"
    "hgg6Z9akjWtWnL1l5Ei9Xuur1kiZ73j42dT50FumTx1ctH7lvJ3MzPc9+uL8N/YefLW8TuOvW61W"
    "5cTaYPaP/QKqwFnTJ517zpypv/Lwk7s+t2bpgs8umj31T29/7NnJI/XWaKPZkIlez2UmpGlKG1ae"
    "8wsL5037g9sffG6g3ck71158nlcVMANeBGDA2KTdbufVR7e90t9ottv1RvOEtlalklK1UqHLLlp+"
    "2LIOQR3gUK9VKgPbdr6+8Y39w1sVwBVrljx17/ZdqycPDs5YsWTB5+948LFP587pRE7hAKBarXAl"
    "TdFXtX2XXbCknuXSBlHXXxRmXYr7Hnsxcc7LWbNmnjt3zoxb7n3w8Z/3Xo47H2ZGra/Cc86atnrN"
    "eXO3Ze28bhgDAMSw4dFGds+Tz736kSsuOHe0k7X3JamdNaENikQikUgkEolEIpFIJBKJRCKRSCQS"
    "iUQikUgkEolEIpFIJBKJRCKRSCQSiUQikUgkEolEIpFIJBKJRCKRSCQSiUQikUgkEolEIt+b/x+d"
    "myz9ZnKRaQAAAABJRU5ErkJggg=="
)

def _get_logo_image(size=(32,32)):
    """Return a CTkImage of the Cornerstone arch logo for use in the UI."""
    try:
        from PIL import Image as _PImage
        if os.path.exists(_LOGO_PATH):
            img = _PImage.open(_LOGO_PATH).convert("RGBA")
        else:
            raw = base64.b64decode(_EMBEDDED_LOGO_B64)
            img = _PImage.open(io.BytesIO(raw)).convert("RGBA")
        img = img.resize(size, _PImage.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None

def _set_window_icon(window):
    """
    Set window/taskbar/dock icon to the Cornerstone arch logo.
    Called via after(50,...) so it runs AFTER CTk finishes its own icon setup.
    On Windows: clears CTk's blue default bitmap, then sets our icon.
    On macOS: sets title-bar icon + dock icon via NSApp if pyobjc available.
    """
    try:
        from PIL import Image as _PImage, ImageTk as _ITk

        if os.path.exists(_LOGO_PATH):
            icon_img = _PImage.open(_LOGO_PATH).convert("RGBA")
        else:
            raw = base64.b64decode(_EMBEDDED_LOGO_B64)
            icon_img = _PImage.open(io.BytesIO(raw)).convert("RGBA")

        SIZE = 256
        bg = _PImage.new("RGBA", (SIZE, SIZE), (42, 42, 42, 255))
        bg.paste(icon_img.resize((SIZE, SIZE), _PImage.LANCZOS), (0, 0), icon_img.resize((SIZE, SIZE), _PImage.LANCZOS))

        # Windows: CTk sets a blue .ico via wm_iconbitmap — clear it first
        if IS_WINDOWS:
            try:
                window.wm_iconbitmap("")
            except Exception:
                pass

        tk_icon = _ITk.PhotoImage(bg.convert("RGB"))
        window.wm_iconphoto(True, tk_icon)
        window._icon_ref = tk_icon   # prevent GC

        # macOS dock icon via NSApp (requires: pip install pyobjc-framework-Cocoa)
        if IS_MAC:
            try:
                import tempfile as _tf
                tmp = _tf.NamedTemporaryFile(suffix=".png", delete=False)
                bg.save(tmp.name); tmp.close()
                from AppKit import NSApplication as _NSApp, NSImage as _NSImg
                ns_img = _NSImg.alloc().initWithContentsOfFile_(tmp.name)
                _NSApp.sharedApplication().setApplicationIconImage_(ns_img)
            except Exception:
                pass

    except Exception:
        pass
INSTANTLY_BASE     = "https://api.instantly.ai/api/v2"

# ─── PALETTE (Cornerstone brand: dark charcoal + gold accent) ────────────────
BG       = "#1a1a1a"   # dark charcoal — matches website sidebar
PANEL    = "#222222"   # slightly lighter panels
CARD     = "#2a2a2a"   # card surfaces
ENTRY_BG = "#141414"   # input fields
BORDER   = "#3a3530"   # warm dark border
ACCENT   = "#c9a96e"   # Cornerstone gold
ACCENT_H = "#d4b483"   # lighter gold on hover
ACCENT_D = "#a8874e"   # darker gold pressed/disabled
GREEN    = "#6ab187"   # success green (softer)
GREEN_H  = "#55966e"
YELLOW   = "#e8c84a"   # warning amber
RED      = "#e05c5c"   # error red
TEXT     = "#f0ece4"   # warm white
SUBTEXT  = "#8a8278"   # warm grey
WHITE    = "#ffffff"
DISABLED = "#2e2b27"
DIS_TEXT = "#5a5650"
CHIP_BG  = "#3a3020"
CHIP_FG  = "#c9a96e"
SEL_BG   = "#2e2818"

# ─── OPTION LISTS ─────────────────────────────────────────────────────────────
STATUS_OPTIONS = ["New Lead", "Active", "Passive", "DNC", "Left Company", "Archive"]

INDUSTRY_OPTIONS = sorted([
    "Architectural Metalwork", "Structural Steel", "Sheet Metal", "Asbestos Removal",
    "Bricklayering", "Civils", "Cladding", "Consultancy", "Curtain Wall", "Demolition",
    "Ductwork", "Electrical", "Energy", "Facilities Management", "Fire & Security",
    "Fire Protection", "Fit Out", "Glazing", "Groundworks", "Logistics", "Main Contractor",
    "Mechanical", "Mechanical & Electrical", "Modular Housing", "New Build", "Nuclear",
    "Oil & Gas", "Plumbing", "Renewables", "Roofing", "Scaffolding", "Self Storage",
    "Stone", "Tiling", "Traffic Management", "Tradesmen", "Water", "Powder Coating",
])

EMAIL_STATUS_OPTIONS = ["Good", "Bad", "Risky"]

def _dedup_ordered(lst):
    seen, out = set(), []
    for x in lst:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

COUNTY_OPTIONS = _dedup_ordered([
    "- United States -", "- UAE -", "- Denmark -", "- Netherlands -",
    "- Brazil -", "- Spain -", "- India -",
    "West London", "South London", "North London", "East London",
    "Bristol", "London", "Avon", "Bedfordshire", "Berkshire", "Borders",
    "Buckinghamshire", "Cambridgeshire", "Cheshire", "Cleveland", "Clwyd",
    "Cornwall", "County Antrim", "County Armagh", "County Cork", "County Down",
    "County Durham", "County Fermanagh", "County Londonderry", "County Carlow",
    "County Tyrone", "Cumbria", "Derbyshire", "Devon", "Dorset", "Dublin",
    "Dumfries and Galloway", "Dyfed", "East Scotland", "East Yorkshire",
    "East Sussex", "Edinburgh", "Essex", "Fife", "Galway", "Glasgow",
    "Gloucestershire", "Grampian", "Greater Manchester", "Gwent", "Gwynedd",
    "Hampshire", "Herefordshire", "Hertfordshire", "Highlands and Islands",
    "Humberside", "Isle of Wight", "Kent", "East Kent", "West Kent",
    "Lancashire", "Laois", "Leicestershire", "Leitrim", "Lincolnshire",
    "Limerick", "Lothian", "Mayo", "Meath", "Merseyside", "Mid Glamorgan",
    "Monaghan", "Norfolk", "North Scotland", "North Wales", "North Yorkshire",
    "Ireland", "Northern Ireland", "Northamptonshire", "Northumberland",
    "Nottinghamshire", "Offaly", "Oxfordshire", "Powys", "Roscommon",
    "Rutland", "Shropshire", "Sligo", "Somerset", "South Glamorgan",
    "South Scotland", "South Wales", "South Yorkshire", "Staffordshire",
    "Strathclyde", "Suffolk", "Surrey", "Tayside", "Tipperary",
    "Tyne and Wear", "Warwickshire", "Waterford", "West Glamorgan",
    "West Midlands", "West Scotland", "West Sussex", "West Yorkshire",
    "Westmeath", "Wexford", "Wicklow", "Wiltshire", "Worcestershire",
    "South Lanarkshire", "Glamorgan", "North Somerset", "North Lincolnshire",
    "Scotland", "Monmouthshire",
])

TYPE_OF_WORK_OPTIONS = ["Projects", "Design", "Commercial", "Workshop"]

# ─── ALWAYS KEEP — HR / Recruitment titles (never filter out) ─────────────────
HR_KEYWORDS = [
    "recruitment", "recruiter", "talent", "hr ", "human resource",
    "people manager", "people director", "head of people",
    "training manager", "training director", "learning and development",
    "l&d", "workforce", "resourcing",
]

# ─── UNCERTAIN — ambiguous titles, flag for manual review ─────────────────────
# Only titles that genuinely span multiple tracks with no clear answer
UNCERTAIN_TITLES = [
    "bid manager", "bid director",       # commercial-ish but not always
    "director",                          # bare "director" — too generic
    "manager",                           # bare "manager" — too generic
]

# ─── JOB TITLE HIERARCHY ──────────────────────────────────────────────────────
# Aligned exactly with Cornerstone introduction document.
# Level 0 = most senior. Candidate at level N removes contacts at level > N
# (strictly junior). Same level and above are always kept.
#
# PROJECTS track  — site/operations based
#   MD > Contracts/Projects Director > Contracts Manager > Project Manager
#   > Site/Construction/Installation Manager > Supervisor > Foreman > Skilled Workers
#
# DESIGN track    — design/technical office
#   Design/Technical Director > Design/Technical Manager
#   > Design/Technical Supervisor > Senior Designer/Draughtsman/Detailer
#   > Designer/Draughtsman/Detailer
#
# COMMERCIAL track — office based commercial/estimating/sales
#   Commercial Director > Commercial Manager > QS > Estimators
#   (includes Pre-Construction, BDM, Sales at appropriate levels)
#
# WORKSHOP track  — factory/manufacturing
#   Workshop/Production Director > Workshop/Production Manager
#   > Workshop/Production Supervisor > QC / Operatives

HIERARCHY = {
    "projects": [
        # 0 — Managing Director / board level
        ["managing director", "chief executive", "ceo", "owner",
         "group director", "executive director"],
        # 1 — Contracts / Projects Director (per PDF)
        ["contracts director", "projects director", "operations director",
         "installations director", "construction director",
         "delivery director", "divisional director", "regional director"],
        # 2 — Contracts Manager / Senior Project Manager
        ["contracts manager", "projects manager", "operations manager",
         "installations manager", "delivery manager", "divisional manager",
         "regional manager", "senior project manager"],
        # 3 — Project Manager
        ["project manager", "junior project manager", "assistant project manager"],
        # 4 — Site Manager / Construction Manager / Installation Manager
        #     NOTE: "senior site manager" is STILL level 4 — not above PM
        ["site manager", "senior site manager", "assistant site manager",
         "construction manager", "installation manager", "site agent"],
        # 5 — Supervisor / Foreman
        ["supervisor", "foreman", "chargehand", "gang leader", "team leader",
         "site supervisor"],
        # 6 — Skilled Workers / Operatives
        ["skilled worker", "labourer", "labour", "operative",
         "fitter", "welder", "fabricator", "installer", "erector",
         "rigger", "steelworker", "ironworker"],
    ],
    "design": [
        # 0 — Design / Technical Director
        ["design director", "technical director", "drawing office director",
         "head of design", "head of engineering", "engineering director",
         "chief engineer"],
        # 1 — Design / Technical Manager
        ["design manager", "technical manager", "drawing office manager",
         "engineering manager", "bim manager"],
        # 2 — Design / Technical Supervisor (senior level)
        ["design supervisor", "technical supervisor", "lead designer",
         "lead engineer", "principal designer", "senior engineer",
         "senior structural engineer", "senior mechanical engineer",
         "senior civil engineer", "senior cad technician"],
        # 3 — Senior Designer / Draughtsman / Detailer
        ["senior designer", "senior draughtsman", "senior detailer"],
        # 4 — Designer / Draughtsman / Detailer
        ["designer", "draughtsman", "detailer", "structural engineer",
         "mechanical engineer", "civil engineer", "engineer",
         "cad technician", "bim technician", "revit technician"],
        # 5 — Junior / Graduate
        ["junior designer", "junior draughtsman", "junior detailer",
         "junior engineer", "graduate engineer", "graduate designer",
         "apprentice designer", "trainee designer"],
    ],
    "commercial": [
        # 0 — Commercial Director and equivalents (per PDF: all Director levels)
        ["commercial director", "pre-construction director",
         "business development director", "sales director",
         "estimating director", "procurement director"],
        # 1 — Commercial Manager and equivalents
        ["commercial manager", "pre-construction manager",
         "business development manager", "sales manager",
         "estimating manager", "procurement manager",
         "senior quantity surveyor", "senior estimator", "senior buyer",
         "chief estimator"],
        # 2 — Quantity Surveyor / Estimator / Buyer (per PDF core QS level)
        ["quantity surveyor", "estimator", "buyer", "commercial surveyor",
         "cost manager", "cost engineer", "planner", "project planner",
         "procurement officer", "contract surveyor"],
        # 3 — Sales and junior commercial roles (per PDF: "Sales (anything related)")
        ["sales executive", "sales representative", "sales coordinator",
         "business development executive",
         "junior quantity surveyor", "junior estimator", "junior buyer",
         "assistant quantity surveyor", "assistant estimator", "assistant buyer",
         "trainee quantity surveyor", "trainee estimator",
         "graduate quantity surveyor", "graduate estimator", "graduate surveyor"],
    ],
    "workshop": [
        # 0 — Workshop / Production Director (per PDF)
        ["workshop director", "production director", "manufacturing director",
         "factory director"],
        # 1 — Workshop / Production Manager / Operations Manager (per PDF)
        ["workshop manager", "production manager", "manufacturing manager",
         "factory manager", "operations manager"],
        # 2 — Workshop / Production Supervisor (per PDF)
        ["workshop supervisor", "production supervisor", "shift supervisor",
         "manufacturing supervisor", "floor manager", "shop floor manager"],
        # 3 — QC Inspectors and workshop operatives (per PDF: "workshop not site")
        ["quality control inspector", "qc inspector", "quality manager",
         "quality engineer", "quality assurance manager", "quality assurance",
         "ndt technician", "press operator", "machine operator", "cnc operator",
         "workshop operative", "production operative", "fabricator"],
    ],
}

def normalise(t):
    t = t.lower().strip()
    # Strip parenthetical noise: "Project Manager (Civil)" → "project manager"
    t = re.sub(r'\(.*?\)', '', t)
    # Take first part of slash/pipe/ampersand compounds:
    # "Project Manager / Site Manager" — classify by the FIRST title only
    # (usually the primary role)
    for sep in ('/', '|', ' & ', ' and '):
        if sep in t:
            t = t.split(sep)[0].strip()
            break
    # Strip punctuation except hyphens between words
    t = re.sub(r'[^\w\s-]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    # Common abbreviations → canonical form
    t = re.sub(r'\bcontracts?\b', 'contracts', t)   # "contract manager" → "contracts manager"
    t = re.sub(r'\bprojs?\b', 'project', t)
    t = re.sub(r'\bmgr\b', 'manager', t)
    t = re.sub(r'\bdir\b', 'director', t)
    t = re.sub(r'\b(snr|sr)\b', 'senior', t)
    t = re.sub(r'\bjnr\b', 'junior', t)
    t = re.sub(r'\bqs\b', 'quantity surveyor', t)
    t = re.sub(r'\bpm\b', 'project manager', t)
    t = re.sub(r'\bcm\b', 'contracts manager', t)
    t = re.sub(r'\bmd\b', 'managing director', t)
    t = re.sub(r'\bbdm\b', 'business development manager', t)
    return t.strip()

def _word_match(variant, title):
    """
    True if `variant` appears in `title` as a complete phrase (whole-word boundary).
    e.g. "project manager" matches "senior electrical project manager".
    """
    if title == variant:
        return True
    idx = title.find(variant)
    while idx != -1:
        before_ok = (idx == 0 or not title[idx-1].isalpha())
        after_idx = idx + len(variant)
        after_ok  = (after_idx >= len(title) or not title[after_idx].isalpha())
        if before_ok and after_ok:
            return True
        idx = title.find(variant, idx + 1)
    return False

def is_hr_title(title):
    t = normalise(title)
    return any(kw in t for kw in HR_KEYWORDS)

def is_uncertain(title):
    t = normalise(title)
    for u in UNCERTAIN_TITLES:
        if t == u:
            return True
    return False

def get_level(title):
    """
    Return (track_name, level_int) for the best match — longest variant wins.
    Keyword root matching: "senior electrical project manager" → matches
    "project manager" (level 3 projects) because _word_match finds the phrase.
    """
    t = normalise(title)
    best      = None
    best_vlen = -1

    for track_name, track in HIERARCHY.items():
        for lvl, variants in enumerate(track):
            for v in variants:
                if not _word_match(v, t):
                    continue
                vlen = len(v)
                if (best is None
                        or vlen > best_vlen
                        or (vlen == best_vlen and lvl < best[1])):
                    best      = (track_name, lvl)
                    best_vlen = vlen
    return best

# ALWAYS-REMOVE phrases — on-site/operative roles regardless of candidate
# Checked as substrings so "senior site manager" still hits "site manager"
_ALWAYS_REMOVE_PHRASES = [
    "site manager", "construction manager", "installation manager",
    "site agent", "site supervisor", "supervisor", "foreman", "chargehand",
    "gang leader", "skilled worker", "labourer", "labour", "operative",
    "fitter", "welder", "fabricator", "installer", "erector",
    "rigger", "steelworker", "ironworker",
]

def classify_auto(contact_title, candidate_title):
    """
    Returns: "keep", "remove", or "uncertain"

    Rules (in priority order):
    1.  Blank title                      → uncertain
    2.  HR/Recruitment keyword           → always keep
    3.  "director" anywhere              → always keep
    4.  On-site/operative phrase         → always remove
        (site manager, supervisor, foreman, etc — incl. "senior site manager")
    5.  Unrecognised title (not in hierarchy) → keep (don't remove unknowns)
    6.  Different tracks                 → keep
    7.  Same track, STRICTLY below candidate (level > candidate level) → remove
    8.  Same track, same level OR above  → keep
    9.  Uncertain bare title             → uncertain (yellow flag)

    Key design decisions:
    - "same level" = keep  (peers of candidate are relevant)
    - only STRICTLY junior (higher level number) = remove
    - "senior X" is classified by its base keyword via get_level,
      so "senior project manager" → projects level 2 (same as PM level 2 entry)
    - modifier words (electrical, mechanical, civil, site, senior...) are
      ignored for track/level — only the ROOT keyword matters
    """
    if not contact_title or not contact_title.strip():
        return "uncertain"

    if is_hr_title(contact_title):
        return "keep"

    t    = normalise(contact_title)
    cand = normalise(candidate_title)

    # Rule 3: directors always kept
    if "director" in t:
        return "keep"

    # Rule 4: always-remove on-site/operative roles
    if any(phrase in t for phrase in _ALWAYS_REMOVE_PHRASES):
        return "remove"

    # Rule 5-8: classify both titles
    tp = get_level(t)
    cp = get_level(cand)

    if tp is None:
        # Unrecognised contact title — flag uncertain so user can review
        return "uncertain"

    if cp is None:
        # Can't classify candidate → can't reason → keep
        return "keep"

    if cp[0] != tp[0]:
        # Different tracks → keep (different discipline)
        return "keep"

    # Same track:
    # contact STRICTLY BELOW candidate (higher level number) → remove
    # contact at same level OR above (same or lower number)  → keep
    #
    # Special case: "junior/assistant/trainee" prefix = one level lower than
    # the base title, so junior project manager (level 3) vs project manager
    # (level 3) should be removed. We detect this via prefix words.
    JUNIOR_PREFIXES = ("junior ", "assistant ", "trainee ", "graduate ")
    SENIOR_PREFIXES = ("senior ", "lead ", "principal ", "chief ")

    contact_is_junior = any(t.startswith(p) for p in JUNIOR_PREFIXES)
    contact_is_senior = any(t.startswith(p) for p in SENIOR_PREFIXES)
    cand_is_senior    = any(cand.startswith(p) for p in SENIOR_PREFIXES)

    if tp[1] > cp[1]:
        # Contact is strictly below candidate → remove
        return "remove"

    if tp[1] == cp[1]:
        # Same hierarchy level as candidate → remove
        # (same-level peers don't need mailshotting — they are the candidate)
        return "remove"

    # tp[1] < cp[1] — contact is strictly ABOVE candidate → keep
    return "keep"

def should_remove(contact_title, candidate_title, always_exclude=None):
    """Legacy boolean wrapper for backward compatibility."""
    if contact_title and "*" in contact_title:
        return False
    t = normalise(contact_title or "")
    if always_exclude:
        for excl in always_exclude:
            if excl.strip() and normalise(excl) == t:
                return True
    return classify_auto(contact_title or "", candidate_title) == "remove"

def clean_list_field(val):
    if not val:
        return ""
    s = str(val).strip()
    if s.startswith("[") and s.endswith("]"):
        import ast
        try:
            items = ast.literal_eval(s)
            if isinstance(items, list):
                return ", ".join(str(i) for i in items)
        except Exception:
            pass
        s = s[1:-1].replace("'", "").replace('"', "")
        return ", ".join(p.strip() for p in s.split(",") if p.strip())
    return s


# ═══════════════════════════════════════════════════════════════════════════
#  CUSTOM SCROLLBAR
# ═══════════════════════════════════════════════════════════════════════════
class DarkScrollbar(tk.Canvas):
    TRACK  = "#161d17"
    THUMB  = "#2a3d2d"
    THUMB_H = "#30d158"
    WIDTH  = 8

    def __init__(self, parent, command=None, **kwargs):
        super().__init__(parent, bg=self.TRACK, highlightthickness=0,
                         width=self.WIDTH, **kwargs)
        self._command   = command
        self._thumb_top = 0.0
        self._thumb_bot = 1.0
        self._dragging  = False
        self._drag_y    = 0
        self._hovered   = False
        self.bind("<Configure>",       self._redraw)
        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<B1-Motion>",       self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>",           self._on_enter)
        self.bind("<Leave>",           self._on_leave)

    def set(self, lo, hi):
        self._thumb_top = float(lo)
        self._thumb_bot = float(hi)
        self._redraw()

    def _redraw(self, _=None):
        self.delete("all")
        h = self.winfo_height()
        if h <= 0:
            return
        y0 = int(self._thumb_top * h)
        y1 = int(self._thumb_bot * h)
        if y1 - y0 < 20:
            y1 = min(h, y0 + 20)
        color = self.THUMB_H if self._hovered else self.THUMB
        r = self.WIDTH // 2
        self.create_oval(1, y0, self.WIDTH - 1, y0 + self.WIDTH, fill=color, outline="")
        self.create_rectangle(1, y0 + r, self.WIDTH - 1, y1 - r, fill=color, outline="")
        self.create_oval(1, y1 - self.WIDTH, self.WIDTH - 1, y1, fill=color, outline="")

    def _on_enter(self, _=None):
        self._hovered = True; self._redraw()
    def _on_leave(self, _=None):
        if not self._dragging: self._hovered = False; self._redraw()
    def _on_press(self, e):
        h = self.winfo_height()
        y0 = int(self._thumb_top * h)
        y1 = int(self._thumb_bot * h)
        if y0 <= e.y <= y1:
            self._dragging = True
            self._drag_y = e.y - y0
        elif self._command:
            self._command("moveto", e.y / max(h, 1))
    def _on_drag(self, e):
        if not self._dragging: return
        h = self.winfo_height()
        thumb_h = int((self._thumb_bot - self._thumb_top) * h)
        new_top = (e.y - self._drag_y) / max(h, 1)
        new_top = max(0.0, min(new_top, 1.0 - thumb_h / max(h, 1)))
        if self._command: self._command("moveto", new_top)
    def _on_release(self, _=None):
        self._dragging = False; self._hovered = False; self._redraw()


# ═══════════════════════════════════════════════════════════════════════════
#  CLICK LABEL — simple label-button (used for inline flat buttons)
#  For prominent buttons, CTkButton is used directly in the UI code.
# ═══════════════════════════════════════════════════════════════════════════
class ClickLabel(tk.Label):
    def __init__(self, parent, command=None,
                 bg=None, hover_bg=None, active_bg=None,
                 fg=TEXT, hover_fg=None,
                 disabled_bg=None, disabled_fg=None,
                 text="", font=None, padx=10, pady=5,
                 **kwargs):
        _bg      = bg      or CARD
        _dis_bg  = disabled_bg or DISABLED
        _dis_fg  = disabled_fg or DIS_TEXT
        super().__init__(parent, text=text, bg=_bg, fg=fg,
                         font=font or ("SF Pro Text", 10),
                         cursor="hand2", padx=padx, pady=pady, **kwargs)
        self._cmd       = command
        self._bg        = _bg
        self._hover_bg  = hover_bg  or self._dk(_bg)
        self._active_bg = active_bg or self._dk(_bg, 30)
        self._fg        = fg
        self._hover_fg  = hover_fg or fg
        self._dis_bg    = _dis_bg
        self._dis_fg    = _dis_fg
        self._enabled   = True
        self.bind("<Enter>",           self._on_enter)
        self.bind("<Leave>",           self._on_leave)
        self.bind("<ButtonPress-1>",   self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    @staticmethod
    def _dk(h, a=20):
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"#{max(0,r-a):02x}{max(0,g-a):02x}{max(0,b-a):02x}"

    def _on_enter(self, _=None):
        if self._enabled: tk.Label.config(self, bg=self._hover_bg, fg=self._hover_fg)
    def _on_leave(self, _=None):
        if self._enabled: tk.Label.config(self, bg=self._bg, fg=self._fg)
    def _on_press(self, _=None):
        if self._enabled: tk.Label.config(self, bg=self._active_bg)
    def _on_release(self, _=None):
        if self._enabled:
            tk.Label.config(self, bg=self._hover_bg)
            if self._cmd: self._cmd()

    def set_enabled(self, enabled):
        self._enabled = enabled
        if enabled:
            tk.Label.config(self, bg=self._bg, fg=self._fg, cursor="hand2")
        else:
            tk.Label.config(self, bg=self._dis_bg, fg=self._dis_fg, cursor="")

    def configure(self, **kw):
        if "hover_bg"  in kw: self._hover_bg  = kw.pop("hover_bg")
        if "active_bg" in kw: self._active_bg = kw.pop("active_bg")
        if "hover_fg"  in kw: self._hover_fg  = kw.pop("hover_fg")
        if "bg" in kw and kw["bg"] != self._dis_bg: self._bg = kw["bg"]
        if "fg" in kw and kw["fg"] != self._dis_fg: self._fg = kw["fg"]
        if kw: tk.Label.configure(self, **kw)

    def config(self, **kw): self.configure(**kw)


# ═══════════════════════════════════════════════════════════════════════════
#  CHIP FRAME
# ═══════════════════════════════════════════════════════════════════════════
class ChipFrame(tk.Frame):
    """
    Displays a list of removable chips.
    Uses a stable widget pool — chips are reused not destroyed/recreated,
    so there's no flicker on add/remove.
    """
    def __init__(self, parent, on_change=None, **kwargs):
        super().__init__(parent, bg=CARD, **kwargs)
        self._on_change = on_change
        self._chips     = []        # ordered list of chip names
        self._widgets   = {}        # name → (frame, label, x_label)

    def add(self, name):
        name = str(name).strip()
        if not name or name in self._chips:
            return
        self._chips.append(name)
        self._sync()
        if self._on_change: self._on_change()

    def remove(self, name):
        if name in self._chips:
            self._chips.remove(name)
            self._sync()
            if self._on_change: self._on_change()

    def clear(self):
        if not self._chips:
            return
        self._chips.clear()
        self._sync()
        if self._on_change: self._on_change()

    def get(self):
        return list(self._chips)

    def _sync(self):
        """
        Add/remove chip widgets without touching unchanged ones.
        No destroy/recreate = no flicker.
        """
        # Remove widgets for chips that no longer exist
        gone = [n for n in list(self._widgets) if n not in self._chips]
        for n in gone:
            f, _, _ = self._widgets.pop(n)
            f.pack_forget()
            f.destroy()

        # Add widgets for new chips
        for name in self._chips:
            if name not in self._widgets:
                chip = tk.Frame(self, bg=CHIP_BG)
                lbl  = tk.Label(chip, text=name, bg=CHIP_BG, fg=CHIP_FG,
                                font=("SF Pro Text", 8), padx=5, pady=2)
                lbl.pack(side="left")
                x = tk.Label(chip, text="×", bg=CHIP_BG, fg=CHIP_FG,
                             font=("SF Pro Text", 9, "bold"), padx=3, cursor="hand2")
                x.pack(side="left")
                x.bind("<ButtonRelease-1>", lambda e, n=name: self.remove(n))
                self._widgets[name] = (chip, lbl, x)

        # Re-pack in correct order (pack_forget + re-pack only, no destroy)
        for f, _, _ in self._widgets.values():
            f.pack_forget()
        for name in self._chips:
            self._widgets[name][0].pack(side="left", padx=(0, 4), pady=2)


# ═══════════════════════════════════════════════════════════════════════════
#  MULTI-SELECT POPUP
# ═══════════════════════════════════════════════════════════════════════════
class MultiSelectPopup(tk.Toplevel):
    def __init__(self, parent, title, options, selected=None):
        super().__init__(parent)
        self.withdraw()          # hide immediately — no flash at wrong position
        self.title(title)
        self.configure(bg=PANEL)
        self.resizable(True, True)
        self.grab_set()
        self.result = list(selected) if selected else []
        self._all_options = list(options)
        self._selected = set(self.result)

        w, h = 460, 520
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        cx, cy = (sw - w) // 2, (sh - h) // 2
        self.minsize(360, 380)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        _popup_show(self, w, h, cx, cy, offset=20)

        # Header
        hdr = tk.Frame(self, bg=ACCENT, height=46)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=title, bg=ACCENT, fg=WHITE,
                 font=("SF Pro Text", 11, "bold")).pack(side="left", padx=14, pady=10)
        self._count_var = tk.StringVar(value="0 selected")
        tk.Label(hdr, textvariable=self._count_var, bg=ACCENT, fg="#86efac",
                 font=("SF Pro Text", 9)).pack(side="right", padx=14)

        # Search box (CTkFrame for rounded edges)
        sf_wrap = ctk.CTkFrame(self, fg_color=ENTRY_BG, corner_radius=10,
                                border_width=1, border_color=BORDER)
        sf_wrap.grid(row=1, column=0, sticky="ew", padx=12, pady=(10, 4))
        sf_wrap.columnconfigure(1, weight=1)
        tk.Label(sf_wrap, text="🔍", bg=ENTRY_BG, fg=SUBTEXT,
                 font=("SF Pro Text", 10)).grid(row=0, column=0, padx=(10, 2), pady=7)
        self._fv = tk.StringVar()
        self._fv.trace_add("write", lambda *_: self._filter())
        tk.Entry(sf_wrap, textvariable=self._fv, bg=ENTRY_BG, fg=TEXT,
                 insertbackground=TEXT, font=("SF Pro Text", 10),
                 relief="flat").grid(row=0, column=1, sticky="ew", padx=(2, 10), pady=7)

        # Listbox
        lf = ctk.CTkFrame(self, fg_color=ENTRY_BG, corner_radius=10,
                           border_width=1, border_color=BORDER)
        lf.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 6))
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self.lb = tk.Listbox(lf, selectmode="multiple", bg=ENTRY_BG, fg=TEXT,
                             selectbackground=ACCENT, selectforeground=WHITE,
                             font=("SF Pro Text", 10), borderwidth=0, relief="flat",
                             activestyle="none", height=16, highlightthickness=0)
        self.lb.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        sb = DarkScrollbar(lf, command=self.lb.yview)
        sb.grid(row=0, column=1, sticky="ns", pady=6, padx=(0, 4))
        self.lb.config(yscrollcommand=sb.set)
        self.lb.bind("<<ListboxSelect>>", self._on_select)
        self._populate(self._all_options)

        # Buttons — CTkButton for rounded look
        bf = tk.Frame(self, bg=PANEL)
        bf.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 14))
        ctk.CTkButton(bf, text="Confirm", command=self._save,
                      width=110, height=34, corner_radius=17,
                      fg_color=ACCENT, hover_color=ACCENT_H, text_color=WHITE,
                      font=ctk.CTkFont("SF Pro Text", 11, weight="bold")
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bf, text="Clear", command=self._clear,
                      width=80, height=34, corner_radius=17,
                      fg_color=CARD, hover_color=BORDER, text_color=SUBTEXT,
                      border_width=1, border_color=BORDER,
                      font=ctk.CTkFont("SF Pro Text", 10)
                      ).pack(side="left")
        ctk.CTkButton(bf, text="Cancel", command=self.destroy,
                      width=80, height=34, corner_radius=17,
                      fg_color=CARD, hover_color=BORDER, text_color=SUBTEXT,
                      border_width=1, border_color=BORDER,
                      font=ctk.CTkFont("SF Pro Text", 10)
                      ).pack(side="right")

    def _populate(self, options):
        self.lb.delete(0, "end")
        for opt in options:
            self.lb.insert("end", opt)
        for i, opt in enumerate(options):
            if opt in self._selected:
                self.lb.selection_set(i)
        self._update_count()

    def _filter(self):
        term = self._fv.get().lower()
        opts = [o for o in self._all_options if term in o.lower()] if term else self._all_options
        self._populate(opts)

    def _on_select(self, _=None):
        visible = list(self.lb.get(0, "end"))
        for i, opt in enumerate(visible):
            if self.lb.selection_includes(i):
                self._selected.add(opt)
            else:
                self._selected.discard(opt)
        self._update_count()

    def _update_count(self):
        n = len(self._selected)
        self._count_var.set(f"{n} selected" if n else "0 selected")

    def _clear(self):
        self._selected.clear()
        self.lb.selection_clear(0, "end")
        self._update_count()

    def _save(self):
        self.result = sorted(self._selected)
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════
#  BULLHORN API
# ═══════════════════════════════════════════════════════════════════════════
class BullhornAPI:
    def __init__(self):
        self.access_token  = None
        self.rest_url      = None
        self.refresh_token = None
        self._token_url    = None
        self._login_url    = None
        self._auth_url     = None
        cfg = self._load_config()
        self.refresh_token = cfg.get("refresh_token", "")
        self.rest_url      = cfg.get("rest_url", "")

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {}

    def _save_config(self, data):
        cfg = self._load_config()
        cfg.update(data)
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)

    def _detect_dc(self):
        cfg = self._load_config()
        dc  = cfg.get("dc", "emea")
        self._auth_url  = f"https://auth-{dc}.bullhornstaffing.com/oauth/authorize"
        self._token_url = f"https://auth-{dc}.bullhornstaffing.com/oauth/token"
        self._login_url = f"https://rest-{dc}.bullhornstaffing.com/rest-services/login"

    def _exchange_and_login(self, token_params):
        if not self._token_url:
            self._detect_dc()
        r = requests.post(self._token_url, params=token_params, timeout=15)
        d = r.json()
        if "access_token" not in d:
            raise Exception(d.get("error_description", str(d)))
        self.refresh_token = d.get("refresh_token", self.refresh_token)
        self._save_config({"refresh_token": self.refresh_token})
        r2 = requests.get(self._login_url,
                          params={"version": "2.0", "access_token": d["access_token"]},
                          timeout=15)
        d2 = r2.json()
        if "BhRestToken" not in d2:
            raise Exception(f"REST login failed: {d2}")
        self.access_token = d2["BhRestToken"]
        self.rest_url     = d2["restUrl"]
        self._save_config({"rest_url": self.rest_url})

    def login_with_refresh_token(self):
        if not self.refresh_token:
            return False
        try:
            self._detect_dc()
            self._exchange_and_login({
                "grant_type":    "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            })
            return True
        except Exception:
            return False

    def start_oauth_flow(self, on_success, on_error):
        """
        Authenticates with Bullhorn using the password grant flow —
        no browser, no Selenium, no ChromeDriver required.
        Works identically when packaged as a .app or .exe.
        """
        def _run():
            try:
                self._detect_dc()

                # Step 1: Get auth code via direct POST (no browser needed)
                pw_enc = urllib.parse.quote(PASSWORD, safe="")
                auth_url = (
                    f"{self._auth_url}"
                    f"?client_id={CLIENT_ID}&response_type=code&action=Login"
                    f"&username={USERNAME}&password={pw_enc}"
                    f"&redirect_uri={REDIRECT_URI}"
                )
                # Follow redirects and capture the code from the final URL
                session = requests.Session()
                resp = session.get(auth_url, allow_redirects=True, timeout=30)

                # The code is in the final redirect URL
                final_url = resp.url
                code = None
                if "code=" in final_url:
                    params = parse_qs(urlparse(final_url).query)
                    code = params.get("code", [None])[0]

                # If not in URL, check response body for redirect
                if not code and "code=" in resp.text:
                    import re as _re
                    m = _re.search(r'[?&]code=([^&"\'\\s]+)', resp.text)
                    if m:
                        code = m.group(1)

                if not code:
                    raise Exception(
                        "Could not get authorisation code from Bullhorn.\n"
                        "Check your username, password and client credentials in config.json."
                    )

                # Step 2: Exchange code for tokens
                self._exchange_and_login({
                    "grant_type":   "authorization_code",
                    "code":         code,
                    "client_id":    CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                })
                on_success()

            except Exception as e:
                on_error(str(e))

        threading.Thread(target=_run, daemon=True).start()

    def _req(self, method, path, **kwargs):
        if not self.rest_url:
            raise Exception("Not connected to Bullhorn")
        params = kwargs.pop("params", {})
        params["BhRestToken"] = self.access_token
        r = requests.request(method, self.rest_url + path, params=params, timeout=30, **kwargs)
        if r.status_code == 401:
            self.login_with_refresh_token()
            params["BhRestToken"] = self.access_token
            r = requests.request(method, self.rest_url + path, params=params, timeout=30, **kwargs)
        return r

    def search_contacts(self, query, count=500, log_cb=None):
        fields = (
            "id,firstName,lastName,occupation,email,phone,mobile,status,"
            "customText1,customTextBlock2,customTextBlock4,customTextBlock5,"
            "clientCorporation(id,name,customTextBlock1)"
        )
        BATCH_SIZE = 500
        r1 = self._req("get", "search/ClientContact",
                       params={"query": query, "fields": "id", "count": 1, "start": 0})
        resp1 = r1.json()
        total_matched = int(resp1.get("total", 0))
        if total_matched == 0:
            return {"data": [], "total": 0}
        target = min(count, total_matched)
        collected = []
        offset = 0
        if log_cb:
            log_cb(f"  {total_matched} contacts found — fetching up to {target}…")
        while len(collected) < target:
            batch_count = min(BATCH_SIZE, target - len(collected))
            r = self._req("get", "search/ClientContact",
                          params={"query": query, "fields": fields,
                                  "count": batch_count, "start": offset,
                                  "sort": "clientCorporation.name"})
            batch = r.json().get("data", [])
            if not batch: break
            collected.extend(batch)
            offset += len(batch)
            if log_cb:
                log_cb(f"  Loaded {len(collected)} / {target}…")
        return {"data": collected, "total": total_matched}


# ═══════════════════════════════════════════════════════════════════════════
#  FILTER DEFINITION
# ═══════════════════════════════════════════════════════════════════════════
FILTER_DEFS = [
    # (display_name, bh_field, value_type, options_list_or_None)
    ("Company",              "clientCorporation.name",             "company_search",      None),
    ("Work Email",           "email",                              "text",                None),
    ("Company Email Domain", "clientCorporation.customTextBlock1", "corp_domain_search",  None),
    ("Status",               "status",                             "inline_filter",       STATUS_OPTIONS),
    ("Email Status",         "customTextBlock1",                   "inline_filter",       EMAIL_STATUS_OPTIONS),
    ("Custom Industry",      "customTextBlock4",                   "inline_filter",       INDUSTRY_OPTIONS),
    ("Custom County",        "customTextBlock2",                   "inline_filter",       COUNTY_OPTIONS),
    ("Custom Type of Work",  "customTextBlock5",                   "inline_filter",       TYPE_OF_WORK_OPTIONS),
    ("Job Title",            "occupation",                         "text",                None),
]
FIELD_NAMES = [d[0] for d in FILTER_DEFS]
FIELD_MAP   = {d[0]: (d[1], d[2], d[3]) for d in FILTER_DEFS}
OPERATORS   = ["Include Any", "Include All", "Exclude"]


# ═══════════════════════════════════════════════════════════════════════════
#  FILTER ROW WIDGET
# ═══════════════════════════════════════════════════════════════════════════
class FilterRow(tk.Frame):
    """
    Value-type behaviours:
      text             – CTkEntry, Enter adds chip
      company_search   – debounced BH search → floating dropdown
      corp_domain_search – BH domain search
      inline_filter    – click → filtered list
    """
    _api_ref = None

    def __init__(self, parent, on_delete, default_field=None, default_op=None, **kwargs):
        super().__init__(parent, bg=CARD, pady=6, padx=6, **kwargs)
        self.on_delete     = on_delete
        self._search_after = None
        self._dropdown_win = None
        self._dropdown_lb  = None
        self._dropdown_outside_bind = None
        self._ready        = False

        # ── Delete button ───────────────────────────────────────────────
        x = tk.Label(self, text="✕", bg=CARD, fg=ACCENT,
                     font=("SF Pro Text", 12, "bold"), cursor="hand2", padx=6)
        x.pack(side="left")
        x.bind("<ButtonRelease-1>", lambda e: self._delete())

        # ── Field selector (CTkComboBox) ────────────────────────────────
        self.field_var = tk.StringVar(value=default_field or FIELD_NAMES[0])
        self.field_var.trace_add("write", self._on_field_change)
        ctk.CTkComboBox(self, variable=self.field_var, values=FIELD_NAMES,
                        width=190, height=32, corner_radius=8,
                        fg_color=ENTRY_BG, border_color=BORDER,
                        button_color=BORDER, button_hover_color=ACCENT,
                        text_color=TEXT, dropdown_fg_color=CARD,
                        dropdown_text_color=TEXT,
                        dropdown_hover_color=SEL_BG,
                        font=ctk.CTkFont("SF Pro Text", 11),
                        state="readonly"
                        ).pack(side="left", padx=(0, 6))

        # ── Operator selector (CTkComboBox) ─────────────────────────────
        self.op_var = tk.StringVar(value=default_op or "Include Any")
        ctk.CTkComboBox(self, variable=self.op_var, values=OPERATORS,
                        width=130, height=32, corner_radius=8,
                        fg_color=ENTRY_BG, border_color=BORDER,
                        button_color=BORDER, button_hover_color=ACCENT,
                        text_color=TEXT, dropdown_fg_color=CARD,
                        dropdown_text_color=TEXT,
                        dropdown_hover_color=SEL_BG,
                        font=ctk.CTkFont("SF Pro Text", 11),
                        state="readonly"
                        ).pack(side="left", padx=(0, 6))

        # ── Value container ─────────────────────────────────────────────
        self.val_frame = tk.Frame(self, bg=CARD)
        self.val_frame.pack(side="left", fill="x", expand=True)

        # ── 1. Free-text (CTkEntry) ─────────────────────────────────────
        self.val_var     = tk.StringVar()
        self._text_entry = ctk.CTkEntry(self.val_frame, textvariable=self.val_var,
                                         fg_color=ENTRY_BG, text_color=TEXT,
                                         border_color=BORDER, border_width=1,
                                         corner_radius=8, placeholder_text="↵ enter to add",
                                         placeholder_text_color=SUBTEXT,
                                         font=ctk.CTkFont("SF Pro Text", 11), width=240, height=32)
        self._text_entry.bind("<Return>", self._add_text_chip)
        self._text_chip_frame = ChipFrame(self.val_frame)

        # ── 2. Live BH search (CTkEntry) ────────────────────────────────
        self._live_search_var = tk.StringVar()
        self._live_entry = ctk.CTkEntry(self.val_frame, textvariable=self._live_search_var,
                                         fg_color=ENTRY_BG, text_color=TEXT,
                                         border_color=BORDER, border_width=1,
                                         corner_radius=8,
                                         font=ctk.CTkFont("SF Pro Text", 11), width=220, height=32)
        self._live_hint = tk.Label(self.val_frame, text="", bg=CARD, fg=SUBTEXT,
                                    font=("SF Pro Text", 8))
        self._live_search_var.trace_add("write", self._on_live_type)
        self._live_entry.bind("<FocusOut>", lambda e: None)
        self._live_entry.bind("<Down>",     self._dd_focus)
        self._live_entry.bind("<Escape>",   lambda e: self._close_dropdown())
        self._live_chip_frame = ChipFrame(self.val_frame)

        # ── 3. Inline-filter (CTkEntry) ─────────────────────────────────
        self._if_search_var = tk.StringVar()
        self._if_entry = ctk.CTkEntry(self.val_frame, textvariable=self._if_search_var,
                                       fg_color=ENTRY_BG, text_color=TEXT,
                                       border_color=BORDER, border_width=1,
                                       corner_radius=8, placeholder_text="browse ▾",
                                       placeholder_text_color=SUBTEXT,
                                       font=ctk.CTkFont("SF Pro Text", 11), width=180, height=32)
        self._if_hint = tk.Label(self.val_frame, text="", bg=CARD, fg=SUBTEXT,
                                  font=("SF Pro Text", 8))
        self._if_search_var.trace_add("write", self._on_if_type)
        self._if_entry.bind("<FocusIn>",  lambda e: self._if_ew_focus_in())
        self._if_entry.bind("<FocusOut>", lambda e: None)
        self._if_entry.bind("<Down>",     self._dd_focus)
        self._if_entry.bind("<Escape>",   lambda e: self._close_dropdown())
        self._if_chip_frame = ChipFrame(self.val_frame)

        self._on_field_change()
        self.after(100, lambda: setattr(self, "_ready", True))

    def _if_ew_focus_in(self):
        """Show dropdown when clicking into inline-filter entry."""
        self.after(10, self._show_if_dropdown)

    # ── Field type switch ─────────────────────────────────────────────────
    def _vtype(self):
        _, vt, _ = FIELD_MAP.get(self.field_var.get(), (None, "text", None))
        return vt

    def _on_field_change(self, *_):
        self._close_dropdown()
        new_vt = self._vtype()

        # Skip if same type — no repack needed, avoids flicker
        if hasattr(self, "_cur_vt") and self._cur_vt == new_vt:
            return
        self._cur_vt = new_vt

        # Hide all value widgets without destroying them
        for w in self.val_frame.winfo_children():
            w.pack_forget()

        if new_vt in ("company_search", "corp_domain_search"):
            hint = ("Type to search companies…"
                    if new_vt == "company_search"
                    else "Type domain (e.g. severfield.com)…")
            self._live_hint.config(text=hint)
            self._live_search_var.set("")
            self._live_entry.pack(side="left")
            self._live_hint.pack(side="left", padx=(4, 0))
            self._live_chip_frame.pack(side="left", padx=(6, 0))
        elif new_vt == "inline_filter":
            self._if_search_var.set("")
            self._if_entry.pack(side="left")
            self._if_hint.pack(side="left", padx=(4, 0))
            self._if_chip_frame.pack(side="left", padx=(6, 0))
        else:
            self._text_entry.pack(side="left")
            self._text_chip_frame.pack(side="left", padx=(6, 0))
            self._text_chip_frame.clear()

    def _on_live_type(self, *_):
        if not self._ready:
            return
        if self._search_after:
            self.after_cancel(self._search_after)
        term = self._live_search_var.get().strip()
        if len(term) < 2:
            self._close_dropdown()
            self._live_hint.config(text="")
            return
        self._live_hint.config(text="…")
        # 220ms debounce — fast enough to feel responsive, slow enough to avoid hammering BH
        self._search_seq = getattr(self, "_search_seq", 0) + 1
        seq = self._search_seq
        self._search_after = self.after(220, lambda t=term, s=seq: self._do_live_search(t, s))

    def _do_live_search(self, term, seq):
        api = FilterRow._api_ref
        vt  = self._vtype()
        if not api:
            self._live_hint.config(text="Not connected.")
            return

        def _fetch():
            # Abort if a newer keystroke has superseded this one
            if getattr(self, "_search_seq", 0) != seq:
                return
            try:
                safe = term.replace('"', '\\"').replace("'", "\\'")
                if vt == "company_search":
                    # Bullhorn tokenises names by word — "Met Structures" is two tokens.
                    # name:(*met structures*) FAILS — wildcard doesn't span token boundaries.
                    # Fix: split words and AND them: name:(*met*) AND name:(*structures*)
                    words = [w for w in safe.strip().split() if w]
                    if len(words) > 1:
                        # Multi-word: each word must appear somewhere in the name
                        word_clauses = " AND ".join(f'name:(*{w}*)' for w in words)
                        q = f'({word_clauses}) AND NOT status:Archive'
                    else:
                        # Single word: wildcard both sides
                        q = f'name:(*{safe}*) AND NOT status:Archive'
                    r = api._req("get", "search/ClientCorporation",
                                 params={"query": q, "fields": "id,name",
                                         "count": 50, "sort": "name"})
                    data = r.json().get("data", [])
                    # Fallback: prefix-only (some BH instances block leading wildcard)
                    if not data:
                        if len(words) > 1:
                            word_clauses2 = " AND ".join(f'name:({w}*)' for w in words)
                            q2 = f'({word_clauses2}) AND NOT status:Archive'
                        else:
                            q2 = f'name:({safe}*) AND NOT status:Archive'
                        r2 = api._req("get", "search/ClientCorporation",
                                      params={"query": q2, "fields": "id,name",
                                              "count": 50, "sort": "name"})
                        data = r2.json().get("data", [])
                    names = sorted({c["name"] for c in data if c.get("name")})
                else:
                    # Domain search — search clientCorporation.customTextBlock1
                    # Bullhorn stores as "@domain.com" so search with @ prefix
                    safe_at = f"@{safe}" if not safe.startswith("@") else safe
                    q = f'customTextBlock1:({safe_at}*) AND NOT status:Archive'
                    r = api._req("get", "search/ClientCorporation",
                                 params={"query": q,
                                         "fields": "id,name,customTextBlock1",
                                         "count": 50, "sort": "name"})
                    data = r.json().get("data", [])
                    if not data:
                        # Fallback: wildcard search without @ prefix
                        q2 = f'customTextBlock1:(*{safe}*) AND NOT status:Archive'
                        r2 = api._req("get", "search/ClientCorporation",
                                      params={"query": q2,
                                              "fields": "id,name,customTextBlock1",
                                              "count": 50, "sort": "name"})
                        data = r2.json().get("data", [])
                    # Show clean domain (strip leading @) so chips look clean
                    names = sorted({
                        c.get("customTextBlock1", "").strip().lstrip("@")
                        for c in data if c.get("customTextBlock1", "").strip()
                    })

                # Only show results if this is still the latest search
                if getattr(self, "_search_seq", 0) == seq:
                    self.after(0, lambda n=names: self._show_live_dropdown(n, term))
            except Exception:
                if getattr(self, "_search_seq", 0) == seq:
                    self.after(0, lambda: self._live_hint.config(text="Search error"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _show_live_dropdown(self, items, term):
        self._close_dropdown()
        if not items:
            self._live_hint.config(text=f"Nothing found")
            return
        self._live_hint.config(text=f"{len(items)} found")
        chip_f = self._live_chip_frame
        entry  = self._live_entry
        hint   = self._live_hint
        sv     = self._live_search_var

        def _on_pick(val):
            chip_f.add(val)
            sv.set("")
            hint.config(text="")
            self._close_dropdown()
            # Return focus to entry so user can keep typing without clicking
            entry.after(10, lambda: entry.focus_set())

        self._open_floating_list(entry, items, _on_pick, width_ref=self._live_entry)

    # ── Inline filter (static list, shows on focus, filters on type) ──────
    def _on_if_type(self, *_):
        if not self._ready:
            return
        vt = self._vtype()
        if vt != "inline_filter":
            return
        self._close_dropdown()
        term = self._if_search_var.get().strip().lower()
        _, _, opts = FIELD_MAP.get(self.field_var.get(), (None, None, None))
        if not opts:
            return
        already = set(self._if_chip_frame.get())
        filtered = [o for o in opts
                    if o not in already and (not term or term in o.lower())]
        if not filtered:
            self._if_hint.config(text="no match")
            return
        self._if_hint.config(text=f"{len(filtered)}")
        self._open_floating_list(self._if_entry, filtered,
                                  self._make_if_pick_handler(),
                                  width_ref=self._if_entry)

    def _show_if_dropdown(self, _=None):
        if not self._ready:
            return
        self._close_dropdown()
        _, _, opts = FIELD_MAP.get(self.field_var.get(), (None, None, None))
        if not opts:
            return
        term    = self._if_search_var.get().strip().lower()
        already = set(self._if_chip_frame.get())
        filtered = [o for o in opts
                    if o not in already and (not term or term in o.lower())]
        if not filtered:
            self._if_hint.config(text="all selected")
            return
        self._if_hint.config(text=f"{len(filtered)}")
        self._open_floating_list(self._if_entry, filtered,
                                  self._make_if_pick_handler(),
                                  width_ref=self._if_entry)

    def _make_if_pick_handler(self):
        """Pick handler: adds chip, clears search, keeps focus + dropdown open."""
        def _on_pick(val):
            self._if_chip_frame.add(val)
            self._if_search_var.set("")
            # Keep dropdown open and focus in entry so user can keep selecting
            self.after(10, self._show_if_dropdown)
            self.after(20, lambda: self._if_entry.focus_set())
        return _on_pick

    # ── Shared floating list builder ──────────────────────────────────────
    def _open_floating_list(self, anchor_widget, items, on_pick, width_ref=None):
        """
        Draw a dropdown list anchored below anchor_widget.
        Frame is built invisible (place off-screen), content added,
        then moved to correct position — prevents any flash at 0,0.
        """
        self._close_dropdown()
        if not items:
            return

        root = self.winfo_toplevel()
        anchor_widget.update_idletasks()

        # Coordinates relative to root window
        ax = anchor_widget.winfo_rootx() - root.winfo_rootx()
        ay = anchor_widget.winfo_rooty() - root.winfo_rooty() + anchor_widget.winfo_height() + 2
        w  = max((width_ref or anchor_widget).winfo_width(), 260)
        h  = min(len(items) * 28 + 4, 300)

        # Clamp so it doesn't go off-screen
        root_h = root.winfo_height()
        if ay + h > root_h - 10:
            ay = (anchor_widget.winfo_rooty() - root.winfo_rooty()) - h - 2

        # Build frame off-screen first so it never flashes at (0,0)
        outer = tk.Frame(root, bg=CARD,
                         highlightbackground=ACCENT, highlightthickness=1)
        outer.place(x=-9999, y=-9999, width=w, height=h)   # off-screen
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        lb = tk.Listbox(outer, bg=CARD, fg=TEXT,
                        selectbackground=SEL_BG, selectforeground=CHIP_FG,
                        font=("SF Pro Text", 10), borderwidth=0, relief="flat",
                        activestyle="none", highlightthickness=0)
        lb.grid(row=0, column=0, sticky="nsew")
        sb = DarkScrollbar(outer, command=lb.yview)
        sb.grid(row=0, column=1, sticky="ns")
        lb.configure(yscrollcommand=sb.set)

        for item in items:
            lb.insert("end", f"  {item}")

        # NOW move to correct position and lift
        if IS_MAC:
            # Slide down from 8px above
            outer.place(x=ax, y=ay - 8, width=w, height=h)
            outer.lift()
            def _slide(step=0):
                steps = 8
                ease  = 1 - (1 - step / steps) ** 2
                y_cur = int(ay - 8 * (1 - ease))
                try:
                    outer.place(x=ax, y=y_cur, width=w, height=h)
                except Exception:
                    pass
                if step < steps:
                    outer.after(10, lambda: _slide(step + 1))
            outer.after(0, _slide)
        else:
            # Windows/Linux: just place at correct position instantly
            outer.place(x=ax, y=ay, width=w, height=h)
            outer.lift()

        # Store so _close_dropdown can destroy it
        self._dropdown_win = outer
        self._dropdown_lb  = lb

        def _pick(e=None):
            sel = lb.curselection()
            if sel:
                on_pick(lb.get(sel[0]).strip())
            # Don't close here — on_pick callback does it

        lb.bind("<ButtonRelease-1>", _pick)
        lb.bind("<Return>",          _pick)
        lb.bind("<Escape>",          lambda e: self._close_dropdown())

        # Close if user clicks anywhere outside this frame
        def _check_outside(e):
            try:
                wx, wy = e.widget.winfo_rootx(), e.widget.winfo_rooty()
                ox, oy = outer.winfo_rootx(), outer.winfo_rooty()
                ow, oh = outer.winfo_width(), outer.winfo_height()
                if not (ox <= wx <= ox + ow and oy <= wy <= oy + oh):
                    self._close_dropdown()
            except Exception:
                pass
        root.bind("<Button-1>", _check_outside, add=True)
        self._dropdown_outside_bind = _check_outside

    def _close_dropdown(self):
        if self._dropdown_win:
            try:
                # Unbind outside-click handler
                if hasattr(self, "_dropdown_outside_bind") and self._dropdown_outside_bind:
                    try:
                        self.winfo_toplevel().unbind("<Button-1>", None)
                    except Exception:
                        pass
                    self._dropdown_outside_bind = None
                self._dropdown_win.place_forget()
                self._dropdown_win.destroy()
            except Exception:
                pass
            self._dropdown_win = None
            self._dropdown_lb  = None

    def _dd_focus(self, _=None):
        if self._dropdown_lb:
            self._dropdown_lb.focus_set()
            if self._dropdown_lb.size() > 0:
                self._dropdown_lb.selection_set(0)
                self._dropdown_lb.activate(0)

    # ── Free-text chip ────────────────────────────────────────────────────
    def _add_text_chip(self, _=None):
        v = self.val_var.get().strip()
        if v:
            self._text_chip_frame.add(v)
            self.val_var.set("")

    def _delete(self):
        self._close_dropdown()
        self.on_delete(self)
        self.destroy()

    # ── Data accessors ────────────────────────────────────────────────────
    def get_values(self):
        vt = self._vtype()
        if vt in ("company_search", "corp_domain_search"):
            return self._live_chip_frame.get()
        if vt == "inline_filter":
            return self._if_chip_frame.get()
        return self._text_chip_frame.get()

    def to_lucene(self):
        field, vt, _ = FIELD_MAP.get(self.field_var.get(),
                                     (self.field_var.get(), "text", None))
        values = self.get_values()
        op     = self.op_var.get()
        if not values:
            return None

        # Company Email Domain — field is clientCorporation.customTextBlock1
        # Bullhorn stores domains as "@domain.com" — match with wildcard
        # Example from real query: NOT clientCorporation.customTextBlock1:(@severfield.com)
        if vt == "corp_domain_search":
            # Normalise: strip leading @ so user can type either "severfield.com" or "@severfield.com"
            clauses = []
            for v in values:
                v = v.strip().lstrip("@")
                # Match the exact domain stored as @domain.com
                clauses.append(f'clientCorporation.customTextBlock1:(@{v})')
            if op == "Include Any": return "(" + " OR ".join(clauses) + ")"
            if op == "Exclude":     return "NOT (" + " OR ".join(clauses) + ")"
            return "(" + " OR ".join(clauses) + ")"

        clauses = [f'{field}:"{v}"' for v in values]
        if op == "Include Any": return "(" + " OR ".join(clauses) + ")"
        if op == "Include All": return "(" + " AND ".join(clauses) + ")"
        if op == "Exclude":     return "NOT (" + " OR ".join(clauses) + ")"
        return None




# ═══════════════════════════════════════════════════════════════════════════
#  INSTANTLY API
# ═══════════════════════════════════════════════════════════════════════════
class InstantlyAPI:
    """
    Instantly v2 API wrapper.
    The API key stored is base64(uuid:secret) — we pass it as-is as Bearer token.
    """
    def __init__(self):
        self.api_key = INSTANTLY_API_KEY

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    def _get(self, path, params=None):
        r = requests.get(f"{INSTANTLY_BASE}{path}", headers=self._headers(),
                         params=params, timeout=20)
        if not r.ok:
            raise Exception(f"GET {path} → {r.status_code}: {r.text[:300]}")
        return r.json()

    def _post(self, path, body):
        r = requests.post(f"{INSTANTLY_BASE}{path}", headers=self._headers(),
                          json=body, timeout=20)
        if not r.ok:
            raise Exception(f"POST {path} → {r.status_code}: {r.text[:400]}")
        return r.json()

    # ── Accounts (individual sending accounts) ───────────────────────────
    def list_accounts(self):
        """Returns all individual sending accounts."""
        results, params = [], {"limit": 100}
        while True:
            data  = self._get("/accounts", params=params)
            items = data.get("items", data.get("data", []))
            results.extend(items)
            nc = (data.get("next_cursor") or data.get("next_starting_after")
                  or data.get("nextCursor"))
            if not nc or not items:
                break
            params["starting_after"] = nc
        return results

    # ── Custom tags (Mailshot (Josh), Mailshot (Liam), For Mailshots etc.) ──
    def list_account_groups(self):
        """
        Fetches custom tags from /custom-tags.
        Returns list of {id, name} dicts with human-readable names.
        """
        try:
            results, params = [], {"limit": 100}
            while True:
                data  = self._get("/custom-tags", params=params)
                items = data.get("items", data.get("data", []))
                results.extend(items)
                nc = data.get("next_cursor") or data.get("nextCursor")
                if not nc or not items:
                    break
                params["starting_after"] = nc
            return results
        except Exception:
            return []

    @staticmethod
    def _tag_name(tag_dict):
        """
        Extract the human-readable name from a custom tag dict.
        Tries every field name Instantly might use.
        """
        for field in ("tag_name", "label", "title", "display_name",
                      "name", "tagName", "tag"):
            val = tag_dict.get(field, "")
            # Only use it if it doesn't look like a raw UUID
            if val and not (len(val) == 36 and val.count("-") == 4):
                return val
        # All fields look like UUIDs or are empty — return id as last resort
        return tag_dict.get("id", "??")

    def list_all_senders(self):
        """
        Combined list:
        - Custom tags first (◈ prefix) — UUIDs go into email_tag_list
        - Individual email accounts  — emails go into email_list
        Each entry: {id, label, kind}
        """
        senders = []

        # Custom tags — Mailshot (Josh), Mailshot (Liam), For Mailshots etc.
        for g in self.list_account_groups():
            gid  = g.get("id", "")
            name = self._tag_name(g)
            if gid:
                senders.append({"id": gid, "label": f"◈ {name}", "kind": "group",
                                 "_raw": g})   # keep raw so we can debug if needed

        # Individual sending accounts
        for a in self.list_accounts():
            aid   = a.get("id") or a.get("email", "")
            email = a.get("email", "")
            label = email or aid
            if label:
                senders.append({"id": aid, "label": label, "kind": "account"})

        return senders

    # ── Campaigns ────────────────────────────────────────────────────────
    def create_campaign(self, name, selected_senders, schedule_payload,
                        daily_limit=50, text_only=True, first_text_only=True,
                        sequence=None):
        """
        Creates a campaign matching the exact Instantly v2 OpenAPI spec.
        - email_list: list of email address strings (individual accounts)
        - email_tag_list: list of tag/group UUID strings
        - stop_on_reply, link_tracking etc. are TOP-LEVEL fields (not nested)
        - text_only / first_email_text_only for delivery optimisation
        - additionalProperties: false — send ONLY documented fields
        """
        # Individual accounts: email_list takes email addresses, not IDs
        account_emails = []
        for s in selected_senders:
            if s.get("kind") == "account":
                email = s.get("label", "")
                if "@" in email:
                    account_emails.append(email)

        # Groups: email_tag_list takes UUID strings
        tag_uuids = [s["id"] for s in selected_senders if s.get("kind") == "group"]

        body = {
            "name":                    name,
            "campaign_schedule":       schedule_payload,
            "daily_limit":             daily_limit,
            "stop_on_reply":           False,   # disabled — do not stop on reply
            "stop_on_auto_reply":      False,   # disabled
            "open_tracking":           False,   # disabled — delivery optimisation
            "link_tracking":           False,   # disabled
            "text_only":               text_only,
            "first_email_text_only":   first_text_only,
        }
        if account_emails:
            body["email_list"]     = account_emails
        if tag_uuids:
            body["email_tag_list"] = tag_uuids
        if sequence:
            body["sequences"] = sequence   # Step 1 email sequence

        result = self._post("/campaigns", body)

        cid = result.get("id")
        if not cid:
            raise Exception(f"No campaign id in response: {result}")

        # Instantly's workspace defaults can override values set during creation.
        # PATCH the campaign immediately after to force-disable these settings.
        try:
            self._patch(f"/campaigns/{cid}", {
                "stop_on_reply":      False,
                "stop_on_auto_reply": False,
                "open_tracking":      False,
                "link_tracking":      False,
            })
        except Exception:
            pass  # non-fatal — campaign is still created

        return {"id": cid, "raw": result}

    def _patch(self, path, body):
        r = requests.patch(f"{INSTANTLY_BASE}{path}", headers=self._headers(),
                           json=body, timeout=20)
        if not r.ok:
            raise Exception(f"PATCH {path} → {r.status_code}: {r.text[:300]}")
        return r.json()

    # ── Leads ────────────────────────────────────────────────────────────
    def add_leads(self, campaign_id, leads_batch):
        """
        Uses the correct endpoint: POST /api/v2/leads/add
        All three skip_if_* flags set to false to force-add regardless of duplicates.
        assigned_to is omitted (requires a workspace user UUID we don't have).
        """
        added = skipped = errors = 0
        error_details = []
        for i in range(0, len(leads_batch), 1000):
            chunk = leads_batch[i:i+1000]
            try:
                result = self._post("/leads/add", {
                    "campaign_id":          campaign_id,
                    "leads":                chunk,
                    "skip_if_in_workspace": False,
                    "skip_if_in_campaign":  False,
                    "skip_if_in_list":      False,
                })
                added   += result.get("leads_uploaded",   0)
                skipped += result.get("duplicated_leads", 0) + result.get("skipped_count", 0)
                inv      = result.get("invalid_email_count", 0)
                if inv:
                    error_details.append(f"Chunk {i//1000+1}: {inv} invalid emails")
                blk = result.get("in_blocklist", 0)
                if blk:
                    error_details.append(f"Chunk {i//1000+1}: {blk} in blocklist")
            except Exception as e:
                errors += len(chunk)
                error_details.append(f"Chunk {i//1000+1} error: {e}")
        return added, skipped, errors, error_details


# ═══════════════════════════════════════════════════════════════════════════
#  INSTANTLY CAMPAIGN POPUP
# ═══════════════════════════════════════════════════════════════════════════
class InstantlyCampaignPopup(tk.Toplevel):
    DAYS     = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    DAY_NUMS = [1, 2, 3, 4, 5, 6, 0]
    HOURS    = [f"{h:02d}:00" for h in range(0, 24)]
    # ONLY values from the official Instantly v2 timezone enum
    # Europe/London is NOT in the enum — use Europe/Isle_of_Man (same UTC offset, in enum)
    TIMEZONES = [
        "Europe/Isle_of_Man",    # Edinburgh, London (UTC) ← default
        "Atlantic/Canary",       # Canary Islands
        "Africa/Casablanca",     # Casablanca (UTC)
        "Europe/Belgrade",       # Central European (UTC+1)
        "Europe/Helsinki",       # Eastern European (UTC+2)
        "Asia/Dubai",            # Dubai (UTC+4)
        "America/Bogota",        # Colombia (UTC-5)
        "America/Chicago",       # Central US (UTC-6)
        "America/Detroit",       # Eastern US (UTC-5)
        "America/Los_Angeles",   # Pacific US (UTC-8)
        "Australia/Melbourne",   # Melbourne/Sydney (UTC+10)
        "Pacific/Auckland",      # New Zealand (UTC+12)
    ]
    TZ_LABELS = {
        "Europe/Isle_of_Man":  "Edinburgh, London (UTC)",
        "Atlantic/Canary":     "Canary Islands (UTC)",
        "Africa/Casablanca":   "Casablanca (UTC)",
        "Europe/Belgrade":     "Central Europe (UTC+1)",
        "Europe/Helsinki":     "Eastern Europe (UTC+2)",
        "Asia/Dubai":          "Dubai (UTC+4)",
        "America/Bogota":      "Colombia (UTC-5)",
        "America/Chicago":     "Central US (UTC-6)",
        "America/Detroit":     "Eastern US (UTC-5)",
        "America/Los_Angeles": "Pacific US (UTC-8)",
        "Australia/Melbourne": "Sydney / Melbourne (UTC+10)",
        "Pacific/Auckland":    "New Zealand (UTC+12)",
    }

    def __init__(self, parent, api, leads):
        super().__init__(parent)
        self.withdraw()          # hide immediately — no flash at wrong position
        self.title("Push to Instantly")
        self.configure(bg=PANEL)
        self.grab_set()
        self.resizable(False, False)
        self._api      = api
        self._leads    = leads
        self._accounts = []
        self._sel_senders = []
        self._build()
        self._load_accounts()

        W, H = 540, 700
        sw   = self.winfo_screenwidth()
        sh   = self.winfo_screenheight()
        cx   = (sw - W) // 2
        cy   = (sh - H) // 2
        _popup_show(self, W, H, cx, cy, offset=30)

    def _build(self):
        # Green accent strip
        ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=3).pack(fill="x")

        # Header
        hf = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        hf.pack(fill="x", padx=20, pady=(12, 4))
        ctk.CTkLabel(hf, text="Push to Instantly",
                     font=ctk.CTkFont("SF Pro Text", 14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(hf, text=f"  {len(self._leads)} leads",
                     font=ctk.CTkFont("SF Pro Text", 11), text_color=SUBTEXT).pack(side="left")

        # Scrollable body
        scroll = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)
        body = ctk.CTkFrame(scroll, fg_color=PANEL, corner_radius=0)
        body.pack(fill="x", padx=20, pady=4)

        def section(t):
            ctk.CTkLabel(body, text=t,
                         font=ctk.CTkFont("SF Pro Text", 11, weight="bold"),
                         text_color=TEXT, anchor="w").pack(anchor="w", pady=(12, 4))

        # ── Campaign name ─────────────────────────────────────────────────
        section("Campaign name")
        self._name_var = tk.StringVar()
        ctk.CTkEntry(body, textvariable=self._name_var,
                     fg_color=ENTRY_BG, text_color=TEXT,
                     border_color=BORDER, border_width=1, corner_radius=10,
                     placeholder_text="e.g. 01/06/2026 - Structural Steel - Josh",
                     placeholder_text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 12), height=38
                     ).pack(fill="x", pady=(0, 6))

        # ── Sending accounts ──────────────────────────────────────────────
        section("Sending accounts")
        ar = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        ar.pack(fill="x", pady=(0, 8))
        self._acc_lbl = ctk.CTkLabel(ar, text="Loading…",
                                      text_color=SUBTEXT,
                                      font=ctk.CTkFont("SF Pro Text", 10))
        self._acc_lbl.pack(side="left")
        self._acc_btn = ctk.CTkButton(ar, text="Choose ▾",
                                       command=self._pick_accounts,
                                       width=110, height=30, corner_radius=15,
                                       fg_color=CARD, hover_color=BORDER,
                                       text_color=TEXT, border_width=1, border_color=BORDER,
                                       font=ctk.CTkFont("SF Pro Text", 10),
                                       state="disabled")
        self._acc_btn.pack(side="right")

        # ── Schedule ──────────────────────────────────────────────────────
        section("Schedule")

        # Days row - grid so all 7 fit
        dr = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        dr.pack(anchor="w", fill="x", pady=(0, 8))
        ctk.CTkLabel(dr, text="Days:", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10), width=80, anchor="w").grid(
                     row=0, column=0, sticky="w")
        self._day_vars = []
        for i, d in enumerate(self.DAYS):
            v = tk.BooleanVar(value=(i < 5))
            self._day_vars.append(v)
            ctk.CTkCheckBox(dr, text=d, variable=v,
                             checkbox_width=16, checkbox_height=16,
                             corner_radius=4,
                             fg_color=ACCENT, hover_color=ACCENT_H,
                             border_color=BORDER, checkmark_color=WHITE,
                             text_color=TEXT,
                             font=ctk.CTkFont("SF Pro Text", 10),
                             width=68
                             ).grid(row=0, column=i+1, padx=(0, 4), sticky="w")

        # Time row
        tr = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        tr.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(tr, text="Time:", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10), width=80, anchor="w").pack(side="left")
        self._from_var = tk.StringVar(value="09:00")
        self._to_var   = tk.StringVar(value="17:00")
        ctk.CTkComboBox(tr, variable=self._from_var, values=self.HOURS,
                         width=90, height=30, corner_radius=8,
                         fg_color=ENTRY_BG, border_color=BORDER,
                         button_color=BORDER, button_hover_color=ACCENT,
                         text_color=TEXT, dropdown_fg_color=CARD,
                         dropdown_text_color=TEXT,
                         font=ctk.CTkFont("SF Pro Text", 10),
                         state="readonly").pack(side="left")
        ctk.CTkLabel(tr, text=" → ", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10)).pack(side="left")
        ctk.CTkComboBox(tr, variable=self._to_var, values=self.HOURS,
                         width=90, height=30, corner_radius=8,
                         fg_color=ENTRY_BG, border_color=BORDER,
                         button_color=BORDER, button_hover_color=ACCENT,
                         text_color=TEXT, dropdown_fg_color=CARD,
                         dropdown_text_color=TEXT,
                         font=ctk.CTkFont("SF Pro Text", 10),
                         state="readonly").pack(side="left")

        # Timezone row
        tzr = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        tzr.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(tzr, text="Timezone:", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10), width=80, anchor="w").pack(side="left")
        tz_labels = [self.TZ_LABELS.get(z, z) for z in self.TIMEZONES]
        self._tz_label_var = tk.StringVar(value=self.TZ_LABELS["Europe/Isle_of_Man"])
        ctk.CTkComboBox(tzr, variable=self._tz_label_var, values=tz_labels,
                         width=240, height=30, corner_radius=8,
                         fg_color=ENTRY_BG, border_color=BORDER,
                         button_color=BORDER, button_hover_color=ACCENT,
                         text_color=TEXT, dropdown_fg_color=CARD,
                         dropdown_text_color=TEXT,
                         font=ctk.CTkFont("SF Pro Text", 10),
                         state="readonly").pack(side="left")

        # Schedule name row
        snr = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        snr.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(snr, text="Sched. name:", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10), width=80, anchor="w").pack(side="left")
        self._sched_name_var = tk.StringVar(value="New schedule")
        ctk.CTkEntry(snr, textvariable=self._sched_name_var,
                     fg_color=ENTRY_BG, text_color=TEXT,
                     border_color=BORDER, border_width=1, corner_radius=8,
                     font=ctk.CTkFont("SF Pro Text", 10),
                     width=200, height=30).pack(side="left")

        # Daily limit row
        lr = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        lr.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(lr, text="Daily limit:", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10), width=80, anchor="w").pack(side="left")
        self._limit_var = tk.StringVar(value="50")
        ctk.CTkEntry(lr, textvariable=self._limit_var,
                     fg_color=ENTRY_BG, text_color=TEXT,
                     border_color=BORDER, border_width=1, corner_radius=8,
                     font=ctk.CTkFont("SF Pro Text", 10),
                     width=80, height=30).pack(side="left")
        ctk.CTkLabel(lr, text="  emails / day", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 9)).pack(side="left", padx=6)

        # ── Delivery optimisation ─────────────────────────────────────────
        section("Delivery optimisation")
        self._text_only_var       = tk.BooleanVar(value=True)
        self._first_text_only_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(body,
                         text="Send emails as text-only (no HTML)  — recommended",
                         variable=self._text_only_var,
                         checkbox_width=18, checkbox_height=18, corner_radius=4,
                         fg_color=ACCENT, hover_color=ACCENT_H,
                         border_color=BORDER, checkmark_color=WHITE,
                         text_color=TEXT, font=ctk.CTkFont("SF Pro Text", 10)
                         ).pack(anchor="w", pady=(0, 6))
        ctk.CTkCheckBox(body,
                         text="Send first email as text-only",
                         variable=self._first_text_only_var,
                         checkbox_width=18, checkbox_height=18, corner_radius=4,
                         fg_color=ACCENT, hover_color=ACCENT_H,
                         border_color=BORDER, checkmark_color=WHITE,
                         text_color=TEXT, font=ctk.CTkFont("SF Pro Text", 10)
                         ).pack(anchor="w", pady=(0, 10))

        # ── Sequence drafter ─────────────────────────────────────────────
        section("Email sequence  (optional)")
        ctk.CTkLabel(body,
                     text="Draft your first email below. It will be added as Step 1 of the sequence.",
                     text_color=SUBTEXT, font=ctk.CTkFont("SF Pro Text", 9),
                     anchor="w", wraplength=480).pack(anchor="w", pady=(0, 6))

        # Subject
        subj_row = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        subj_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(subj_row, text="Subject:", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10), width=60, anchor="w").pack(side="left")
        self._seq_subject_var = tk.StringVar()
        ctk.CTkEntry(subj_row, textvariable=self._seq_subject_var,
                     fg_color=ENTRY_BG, text_color=TEXT,
                     border_color=BORDER, border_width=1, corner_radius=8,
                     placeholder_text="e.g. Quick question, {{firstName}}",
                     placeholder_text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10), height=32
                     ).pack(side="left", fill="x", expand=True)

        # Body — with HTML/Preview toggle
        body_hdr = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        body_hdr.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(body_hdr, text="Body:", text_color=SUBTEXT,
                     font=ctk.CTkFont("SF Pro Text", 10)).pack(side="left")
        self._html_mode = tk.BooleanVar(value=False)
        ctk.CTkSwitch(body_hdr, text="HTML mode",
                      variable=self._html_mode,
                      command=self._toggle_seq_mode,
                      onvalue=True, offvalue=False,
                      fg_color=BORDER, progress_color=ACCENT,
                      button_color=WHITE, button_hover_color=ACCENT_H,
                      text_color=SUBTEXT, font=ctk.CTkFont("SF Pro Text", 9)
                      ).pack(side="right")

        # Text box for body
        body_wrap = ctk.CTkFrame(body, fg_color=ENTRY_BG,
                                  corner_radius=8, border_width=1, border_color=BORDER)
        body_wrap.pack(fill="x", pady=(0, 4))
        self._seq_body = tk.Text(body_wrap, height=7,
                                  bg=ENTRY_BG, fg=TEXT,
                                  insertbackground=TEXT,
                                  font=("SF Pro Text", 10),
                                  relief="flat", padx=10, pady=8,
                                  wrap="word", highlightthickness=0)
        self._seq_body.pack(fill="x")

        # HTML preview label (hidden by default)
        self._seq_preview_lbl = ctk.CTkLabel(body, text="",
                                              text_color=SUBTEXT,
                                              font=ctk.CTkFont("SF Pro Text", 8),
                                              anchor="w", wraplength=480)

        ctk.CTkLabel(body, text="Leave subject + body empty to skip sequence and add it manually in Instantly.",
                     text_color=SUBTEXT, font=ctk.CTkFont("SF Pro Text", 8),
                     anchor="w", wraplength=480).pack(anchor="w", pady=(0, 8))

        # ── Status label ──────────────────────────────────────────────────
        self._status_lbl = ctk.CTkLabel(body, text="",
                                         text_color=ACCENT, wraplength=460,
                                         font=ctk.CTkFont("SF Pro Text", 10),
                                         justify="left", anchor="w")
        self._status_lbl.pack(anchor="w", pady=(0, 8))

        # ── Buttons ───────────────────────────────────────────────────────
        bf = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        bf.pack(fill="x", pady=(4, 16))
        self._create_btn = ctk.CTkButton(bf, text="Create Campaign & Import Leads",
                                          command=self._confirm,
                                          width=260, height=40, corner_radius=20,
                                          fg_color=ACCENT, hover_color=ACCENT_H,
                                          text_color=WHITE,
                                          font=ctk.CTkFont("SF Pro Text", 12, weight="bold"))
        self._create_btn.pack(side="left")
        ctk.CTkButton(bf, text="Cancel", command=self.destroy,
                      width=100, height=40, corner_radius=20,
                      fg_color=CARD, hover_color=BORDER, text_color=SUBTEXT,
                      border_width=1, border_color=BORDER,
                      font=ctk.CTkFont("SF Pro Text", 11)
                      ).pack(side="left", padx=12)

    def _load_accounts(self):
        def _fetch():
            try:
                senders = self._api.list_all_senders()
                self.after(0, lambda: self._on_accounts_loaded(senders))
            except Exception as e:
                self.after(0, lambda: self._acc_lbl.configure(
                    text=f"Error: {e}", text_color=RED))
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_accounts_loaded(self, senders):
        self._accounts = senders   # list of {id, label, kind}
        if senders:
            groups = [s for s in senders if s.get("kind") == "group"]
            accts  = [s for s in senders if s.get("kind") == "account"]
            self._acc_lbl.configure(
                text=f"{len(groups)} groups  ·  {len(accts)} accounts",
                text_color=SUBTEXT)
            self._acc_btn.configure(state="normal")
            # Show raw fields of first tag in log so we can find the name field
            if groups and groups[0].get("_raw"):
                raw = groups[0]["_raw"]
                import json as _json
                print("DEBUG first custom-tag fields:", _json.dumps(raw, indent=2))
        else:
            self._acc_lbl.configure(text="No sending accounts found", text_color=RED)

    def _pick_accounts(self):
        opts    = [a["label"] for a in self._accounts]
        already = [a["label"] for a in self._sel_senders]
        popup = MultiSelectPopup(self, "Select sending accounts / groups", opts, already)
        popup.transient(self); popup.lift(); popup.focus_force()
        self.wait_window(popup)
        label_to_sender = {a["label"]: a for a in self._accounts}
        self._sel_senders = [label_to_sender[lbl] for lbl in popup.result
                              if lbl in label_to_sender]
        if popup.result:
            preview = ", ".join(popup.result[:2])
            if len(popup.result) > 2: preview += f" +{len(popup.result)-2} more"
            self._acc_lbl.configure(text=preview, text_color=CHIP_FG)
        else:
            self._acc_lbl.configure(text="None selected", text_color=SUBTEXT)

    def _toggle_seq_mode(self):
        """Switch between plain text and HTML mode for sequence body."""
        if self._html_mode.get():
            self._seq_preview_lbl.configure(
                text="HTML mode — paste your HTML. It will be sent as-is to Instantly.")
            self._seq_preview_lbl.pack(anchor="w", pady=(0, 6))
        else:
            self._seq_preview_lbl.pack_forget()

    def _build_sequence_payload(self):
        """
        Returns a sequences list for the campaign payload, or None to skip.
        Empty subject + body = skip (user adds sequence manually in Instantly).
        """
        subject = self._seq_subject_var.get().strip()
        body    = self._seq_body.get("1.0", "end").strip()
        if not subject and not body:
            return None
        return [{
            "steps": [{
                "type":     "email",
                "delay":    0,
                "variants": [{
                    "subject": subject or "(no subject)",
                    "body":    body    or "",
                }]
            }]
        }]

    def _build_schedule(self):
        # Days: Instantly v2 uses {"0": bool, "1": bool, ...} where 0=Sunday, 6=Saturday
        # UI order: Mon Tue Wed Thu Fri Sat Sun → DAY_NUMS: [1,2,3,4,5,6,0]
        days_dict = {}
        for i in range(7):
            days_dict[str(i)] = False
        for i, v in enumerate(self._day_vars):
            day_num = self.DAY_NUMS[i]   # 0=Sun,1=Mon,...,6=Sat
            days_dict[str(day_num)] = bool(v.get())

        if not any(days_dict.values()):
            raise ValueError("Select at least one sending day.")

        # Resolve display label back to IANA timezone string
        label       = self._tz_label_var.get()
        label_to_iana = {v: k for k, v in self.TZ_LABELS.items()}
        tz_iana     = label_to_iana.get(label, "Europe/Isle_of_Man")
        sched_name  = self._sched_name_var.get().strip() or "New schedule"

        return {
            "schedules": [{
                "name":     sched_name,
                "timing":   {
                    "from": self._from_var.get(),   # "09:00"
                    "to":   self._to_var.get(),     # "17:00"
                },
                "days":     days_dict,              # {"0": false, "1": true, ...}
                "timezone": tz_iana,
            }]
        }

    def _build_leads(self):
        """
        Builds lead objects matching the exact /api/v2/leads/add spec.
        Lead object allowed fields (additionalProperties: false):
          email, first_name, last_name, company_name, job_title,
          phone, website, personalization, lt_interest_status,
          pl_value_lead, assigned_to, custom_variables
        linkedin_url is NOT in spec — goes into custom_variables.
        """
        out = []
        for c in self._leads:
            email = (c.get("email") or "").strip()
            if not email:
                continue

            corp     = c.get("clientCorporation") or {}
            company  = (corp.get("name", "") if isinstance(corp, dict) else "").strip()
            county   = clean_list_field(c.get("customTextBlock2") or "")
            phone    = (c.get("phone") or c.get("mobile") or "").strip()
            linkedin = (c.get("customText1") or "").strip()
            job_title = (c.get("occupation") or "").strip()

            # Only include fields that are in the spec (additionalProperties: false)
            lead = {"email": email}
            if c.get("firstName"): lead["first_name"]   = c["firstName"].strip()
            if c.get("lastName"):  lead["last_name"]    = c["lastName"].strip()
            if company:            lead["company_name"] = company
            if job_title:          lead["job_title"]    = job_title
            if phone:              lead["phone"]        = phone

            # custom_variables for fields not in the top-level schema
            custom = {}
            if linkedin: custom["linkedin"] = linkedin   # {{linkedin}} in email templates
            if county:   custom["location"] = county
            if custom:   lead["custom_variables"] = custom

            out.append(lead)
        return out

    def _confirm(self):
        name = self._name_var.get().strip()
        if not name:
            self._status_lbl.configure(text="Please enter a campaign name.", text_color=RED)
            return
        if not self._sel_senders:
            self._status_lbl.configure(text="Please select at least one sending account.", text_color=RED)
            return
        try:
            schedule = self._build_schedule()
        except ValueError as e:
            self._status_lbl.configure(text=str(e), text_color=RED)
            return
        leads = self._build_leads()
        if not leads:
            self._status_lbl.configure(text="No leads with valid email addresses.", text_color=RED)
            return
        try:
            limit = int(self._limit_var.get() or 50)
        except ValueError:
            limit = 50
        text_only       = self._text_only_var.get()
        first_text_only = self._first_text_only_var.get()

        # Pulse button → disable → start
        def _after_pulse():
            self._create_btn.configure(state="disabled")
            self._start_progress_dots("Step 1/2 — Creating campaign")
            seq = self._build_sequence_payload()   # None if empty
            threading.Thread(target=self._run,
                             args=(name, schedule, leads, limit,
                                   list(self._sel_senders),
                                   text_only, first_text_only, seq),
                             daemon=True).start()
        self._pulse_btn(self._create_btn, done_cb=_after_pulse)

    def _pulse_btn(self, btn, steps=10, done_cb=None):
        """Flash button to lighter green then back, call done_cb when finished."""
        colors = [ACCENT_H, ACCENT, ACCENT_H, ACCENT, ACCENT_H,
                  ACCENT, ACCENT_H, ACCENT, ACCENT_H, ACCENT]
        def _step(i=0):
            try:
                btn.configure(fg_color=colors[i])
            except Exception:
                pass
            if i < steps - 1:
                self.after(35, lambda: _step(i + 1))
            elif done_cb:
                self.after(35, done_cb)
        _step()

    def _start_progress_dots(self, base_text):
        """Animate trailing dots on status label."""
        self._progress_running = True
        self._progress_base    = base_text
        def _tick(i=0):
            if not getattr(self, "_progress_running", False):
                return
            dots = ["", " .", " ..", " ..."][i % 4]
            try:
                self._status_lbl.configure(
                    text=self._progress_base + dots, text_color=ACCENT)
            except Exception:
                return
            self.after(380, lambda: _tick(i + 1))
        _tick()

    def _stop_progress_dots(self):
        self._progress_running = False

    def _run(self, name, schedule, leads, limit, senders, text_only, first_text_only, sequence=None):
        steps = []
        self.after(0, lambda: self._start_progress_dots("Step 1/2 — Creating campaign"))
        try:
            result = self._api.create_campaign(
                name, senders, schedule, limit,
                text_only=text_only, first_text_only=first_text_only,
                sequence=sequence)
            cid = result["id"]
            steps.append(f"✓ Campaign '{name}' created (id: {cid})")
        except Exception as e:
            err = str(e)
            self.after(0, lambda msg=err: self._finish(f"✗ Campaign creation failed:\n{msg}", RED))
            return

        self.after(0, lambda n=len(leads): (
            setattr(self, "_progress_base", f"Step 2/2 — Importing {n} leads")
        ))
        try:
            added, skipped, errors, err_details = self._api.add_leads(cid, leads)
            detail = f"✓ {added} added"
            if skipped: detail += f",  {skipped} duplicates"
            if errors:  detail += f",  {errors} errors"
            steps.append(detail)
            if err_details:
                for d in err_details[:3]:
                    steps.append(f"  ⚠ {d}")
        except Exception as e:
            steps.append(f"✗ Lead import failed: {e}")

        steps.append("Campaign is in DRAFT — add your sequence in Instantly, then launch.")
        self.after(0, lambda: self._finish("\n".join(steps), GREEN))

    def _finish(self, msg, color):
        self._stop_progress_dots()
        if color == GREEN:
            # Show success briefly then fade out and close
            self._status_lbl.configure(text=msg, text_color=GREEN)
            self._create_btn.configure(
                text="✓ Done!", state="disabled", fg_color=ACCENT_D)
            self.after(800 if IS_WINDOWS else 1800, self._fade_close)
        else:
            self._status_lbl.configure(text=msg, text_color=color)
            self._create_btn.configure(state="normal", fg_color=ACCENT)

    def _fade_close(self):
        """Close popup — animated on macOS, instant on Windows."""
        _popup_hide(self)


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════
class MailshotHelperTool(ctk.CTkFrame):
    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("fg_color", BG)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)

        self.api           = BullhornAPI()
        FilterRow._api_ref = self.api
        self.instantly     = InstantlyAPI()
        self._connected    = False
        self.all_contacts  = []
        self.contact_vars  = {}
        self.filter_rows   = []

        self._apply_styles()
        self._build_ui()
        self.after(200, self._auto_login)

    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
                    background=ENTRY_BG, foreground=TEXT,
                    fieldbackground=ENTRY_BG, font=("SF Pro Text", 10),
                    rowheight=32, borderwidth=0)
        s.configure("Treeview.Heading",
                    background=CARD, foreground=SUBTEXT,
                    font=("SF Pro Text", 9, "bold"), relief="flat")
        s.map("Treeview",
              background=[("selected", SEL_BG)],
              foreground=[("selected", CHIP_FG)])
        s.configure("TCombobox",
                    fieldbackground=ENTRY_BG, background=ENTRY_BG,
                    foreground=TEXT, selectbackground=ACCENT,
                    arrowcolor=SUBTEXT, bordercolor=BORDER,
                    lightcolor=ENTRY_BG, darkcolor=ENTRY_BG,
                    padding=6)
        s.map("TCombobox",
              fieldbackground=[("readonly", ENTRY_BG)],
              background=[("readonly", ENTRY_BG)],
              foreground=[("readonly", TEXT)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab",
                    font=("SF Pro Text", 10), padding=[18, 8],
                    background=PANEL, foreground=SUBTEXT)
        s.map("TNotebook.Tab",
              background=[("selected", CARD)],
              foreground=[("selected", ACCENT)])

    # ── Auth ──────────────────────────────────────────────────────────────
    def _auto_login(self):
        self._log("Connecting to Bullhorn…", "info")
        def _do():
            ok = self.api.login_with_refresh_token()
            self.after(0, lambda: self._set_connected(ok))
        threading.Thread(target=_do, daemon=True).start()

    def _set_connected(self, ok):
        self._connected = ok
        if ok:
            self.conn_lbl.configure(text="● Connected", text_color=GREEN)
            self._log("Connected to Bullhorn ✓", "good")
        else:
            self.conn_lbl.configure(text="● Disconnected", text_color=RED)
            self._log("Not connected — click Reconnect.", "error")

    def _open_login(self):
        self.conn_lbl.configure(text="● Connecting…", text_color=YELLOW)
        self._log("Opening Bullhorn login (Chrome)…", "info")
        def _ok():
            self.after(0, lambda: self._set_connected(True))
        def _err(msg):
            self.after(0, lambda: self._log(f"Login failed: {msg}", "error"))
            self.after(0, lambda: self.conn_lbl.configure(text="● Disconnected", text_color=RED))
        self.api.start_oauth_flow(_ok, _err)

    # ── UI build ──────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header bar (CTkFrame for rounded feel) ─────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo in header
        _logo_img = _get_logo_image(size=(38, 28))
        if _logo_img:
            ctk.CTkLabel(hdr, image=_logo_img, text="").pack(side="left", padx=(12, 4), pady=8)
        ctk.CTkLabel(hdr, text="CORNERSTONE", text_color=WHITE,
                     font=ctk.CTkFont("SF Pro Text", 13, weight="bold")
                     ).pack(side="left", pady=12, padx=(0, 2))
        ctk.CTkLabel(hdr, text="/ Mailshot Filter", text_color=ACCENT,
                     font=ctk.CTkFont("SF Pro Text", 11)
                     ).pack(side="left", padx=(4, 0))

        self.conn_lbl = ctk.CTkLabel(hdr, text="● Not connected",
                                      text_color="#86efac",
                                      font=ctk.CTkFont("SF Pro Text", 9))
        self.conn_lbl.pack(side="right", padx=16)

        ctk.CTkButton(hdr, text="Reconnect", command=self._open_login,
                      width=100, height=30, corner_radius=15,
                      fg_color=ACCENT_D, hover_color=ACCENT_H,
                      text_color=WHITE,
                      font=ctk.CTkFont("SF Pro Text", 10)
                      ).pack(side="right", padx=8, pady=10)


        # ── Body ──────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        # ── Filter panel (CTkFrame for rounded corners) ────────────────────
        filter_panel = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12,
                                     border_width=1, border_color=BORDER)
        filter_panel.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # Green top strip
        tk.Frame(filter_panel, bg=ACCENT, height=3).pack(fill="x")

        # ── Collapsed header (always visible) ─────────────────────────────
        self._filters_expanded = True
        fh_bar = tk.Frame(filter_panel, bg=PANEL, padx=14, pady=8)
        fh_bar.pack(fill="x")

        self._collapse_arrow = tk.Label(fh_bar, text="▾  SEARCH FILTERS",
                                         bg=PANEL, fg=SUBTEXT,
                                         font=("SF Pro Text", 9, "bold"), cursor="hand2")
        self._collapse_arrow.pack(side="left")
        self._collapse_arrow.bind("<ButtonRelease-1>", lambda e: self._toggle_filters())

        # Summary shown when collapsed
        self._filter_summary_lbl = tk.Label(fh_bar, text="", bg=PANEL, fg=CHIP_FG,
                                             font=("SF Pro Text", 8))
        self._filter_summary_lbl.pack(side="left", padx=(10, 0))

        ctk.CTkButton(fh_bar, text="Reset", command=self._reset_filters,
                      width=70, height=26, corner_radius=13,
                      fg_color=CARD, hover_color=BORDER, text_color=SUBTEXT,
                      font=ctk.CTkFont("SF Pro Text", 9)
                      ).pack(side="right", padx=(4, 0))
        ctk.CTkButton(fh_bar, text="Clear", command=self._clear_filters,
                      width=60, height=26, corner_radius=13,
                      fg_color=CARD, hover_color=BORDER, text_color=SUBTEXT,
                      font=ctk.CTkFont("SF Pro Text", 9)
                      ).pack(side="right", padx=(4, 0))
        ctk.CTkButton(fh_bar, text="+ Add Filter", command=self._add_filter_row,
                      width=100, height=26, corner_radius=13,
                      fg_color=ACCENT, hover_color=ACCENT_H, text_color=WHITE,
                      font=ctk.CTkFont("SF Pro Text", 9, weight="bold")
                      ).pack(side="right")

        # ── Expandable body ────────────────────────────────────────────────
        self._filter_body = tk.Frame(filter_panel, bg=PANEL)
        self._filter_body.pack(fill="x")

        filter_inner = tk.Frame(self._filter_body, bg=PANEL, padx=14)
        filter_inner.pack(fill="x", pady=(0, 8))

        # Base query info
        info = ctk.CTkFrame(filter_inner, fg_color="#0a1a0e", corner_radius=6,
                             border_width=1, border_color="#1a3a24")
        info.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(info,
                     text="  Always applied:  isDeleted:0  ·  NOT status:Archive  ·  NOT clientCorporation.status:Archive",
                     text_color="#4a9e5e", font=ctk.CTkFont("SF Pro Text", 8),
                     anchor="w").pack(anchor="w", padx=4, pady=4)

        # Filter rows container
        self.filter_rows_frame = tk.Frame(filter_inner, bg=PANEL)
        self.filter_rows_frame.pack(fill="x")

        # Search bar
        sb = tk.Frame(filter_inner, bg=PANEL, pady=6)
        sb.pack(fill="x")
        self.results_lbl = tk.Label(sb, text="", bg=PANEL, fg=SUBTEXT,
                                    font=("SF Pro Text", 10))
        self.results_lbl.pack(side="left")

        ctk.CTkButton(sb, text="Search Contacts →", command=self._run_search,
                      width=170, height=34, corner_radius=17,
                      fg_color=ACCENT, hover_color=ACCENT_H, text_color=WHITE,
                      font=ctk.CTkFont("SF Pro Text", 11, weight="bold")
                      ).pack(side="right", padx=(8, 0))

        self._reset_filters()

        # ── Notebook ──────────────────────────────────────────────────────
        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self._build_results_tab()
        self._build_log_tab()

    def _add_filter_row(self, default_field=None, default_op=None):
        row = FilterRow(self.filter_rows_frame, on_delete=self._on_filter_delete,
                        default_field=default_field, default_op=default_op)
        row.pack(fill="x", pady=2)
        self.filter_rows.append(row)
        return row

    def _on_filter_delete(self, row):
        if row in self.filter_rows:
            self.filter_rows.remove(row)

    def _clear_filters(self):
        for row in list(self.filter_rows):
            row.destroy()
        self.filter_rows.clear()

    DEFAULT_FILTERS = [
        ("Company",              "Exclude"),
        ("Work Email",           "Exclude"),
        ("Company Email Domain", "Exclude"),
        ("Status",               "Exclude"),
        ("Email Status",         "Include Any"),
        ("Custom Industry",      "Include Any"),
        ("Custom County",        "Include Any"),
        ("Custom Type of Work",  "Include Any"),
    ]

    def _reset_filters(self):
        self._clear_filters()
        for f, op in self.DEFAULT_FILTERS:
            self._add_filter_row(default_field=f, default_op=op)
        # If collapsed, show summary
        if not self._filters_expanded:
            self._update_filter_summary()

    def _toggle_filters(self):
        self._filters_expanded = not self._filters_expanded
        if self._filters_expanded:
            self._filter_body.pack(fill="x")
            self._collapse_arrow.config(text="▾  SEARCH FILTERS")
            self._filter_summary_lbl.config(text="")
        else:
            self._filter_body.pack_forget()
            self._collapse_arrow.config(text="▸  SEARCH FILTERS")
            self._update_filter_summary()

    def _update_filter_summary(self):
        """Build a compact one-line summary of active filters for the collapsed state."""
        parts = []
        for row in self.filter_rows:
            vals = row.get_values()
            if vals:
                field = row.field_var.get()
                op    = row.op_var.get()
                op_s  = {"Include Any": "+", "Include All": "++", "Exclude": "−"}.get(op, "")
                short = ", ".join(vals[:2]) + (f" +{len(vals)-2}" if len(vals) > 2 else "")
                parts.append(f"{op_s} {field}: {short}")
        if parts:
            summary = "  ·  ".join(parts)
            # Truncate if very long
            if len(summary) > 120:
                summary = summary[:117] + "…"
            self._filter_summary_lbl.config(text=summary)
        else:
            self._filter_summary_lbl.config(text="no active filters")

    def _build_query(self):
        base = "isDeleted:0 AND NOT status:Archive AND NOT clientCorporation.status:Archive"
        clauses = [r.to_lucene() for r in self.filter_rows if r.to_lucene()]
        return base + (" AND " + " AND ".join(clauses) if clauses else "")

    # ── Results tab ────────────────────────────────────────────────────────
    def _build_results_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Results  ")
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        # Auto filter controls
        ctrl = tk.Frame(tab, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Frame(ctrl, bg=ACCENT, height=2).pack(fill="x")
        ci = tk.Frame(ctrl, bg=PANEL, padx=14, pady=8)
        ci.pack(fill="x")
        tk.Label(ci, text="Auto-filter by candidate title:", bg=PANEL, fg=SUBTEXT,
                 font=("SF Pro Text", 9)).pack(side="left", padx=(0, 8))

        self.candidate_var = tk.StringVar()
        cand_entry = ctk.CTkEntry(ci, textvariable=self.candidate_var,
                                   fg_color=ENTRY_BG, text_color=TEXT,
                                   border_color=BORDER, border_width=1,
                                   corner_radius=8,
                                   font=ctk.CTkFont("SF Pro Text", 10), width=220)
        cand_entry.pack(side="left", padx=(0, 8))
        cand_entry.bind("<Return>", lambda e: self._run_auto_filter())

        ctk.CTkButton(ci, text="Apply", command=self._run_auto_filter,
                      width=80, height=30, corner_radius=15,
                      fg_color=ACCENT, hover_color=ACCENT_H, text_color=WHITE,
                      font=ctk.CTkFont("SF Pro Text", 10, weight="bold")
                      ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(ci, text="Reset (check all)", command=self._check_all,
                      width=130, height=30, corner_radius=15,
                      fg_color=CARD, hover_color=BORDER, text_color=SUBTEXT,
                      border_width=1, border_color=BORDER,
                      font=ctk.CTkFont("SF Pro Text", 9)
                      ).pack(side="left")

        self.auto_status_lbl = tk.Label(ci, text="",
                                        bg=PANEL, fg=SUBTEXT, font=("SF Pro Text", 9))
        self.auto_status_lbl.pack(side="left", padx=12)

        # Tree
        tree_frame = tk.Frame(tab, bg=BG)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        cols = ("check", "name", "company", "title", "county", "industry", "type_of_work", "email", "status")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="none")
        hdrs = [
            ("✓",       40),
            ("Name",    150),
            ("Company", 160),
            ("Job Title",160),
            ("County",  110),
            ("Industry",130),
            ("Type",    110),
            ("Email",   190),
            ("Status",   90),
        ]
        for (h, w), c in zip(hdrs, cols):
            self.tree.heading(c, text=h, anchor="center" if h == "✓" else "w")
            self.tree.column(c, width=w, stretch=(w > 60), anchor="center" if h == "✓" else "w")

        self.tree.tag_configure("remove",    background="#1a0a0a", foreground="#ff453a")
        self.tree.tag_configure("keep",      background=ENTRY_BG,  foreground=TEXT)
        self.tree.tag_configure("uncertain", background="#1a1800", foreground="#ffd60a")
        self.tree.bind("<Button-1>", self._toggle_check)

        vsb = DarkScrollbar(tree_frame, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Bottom action bar
        bot = ctk.CTkFrame(tab, fg_color=PANEL, corner_radius=0, height=50)
        bot.grid(row=2, column=0, sticky="ew")
        self.sel_count_lbl = ctk.CTkLabel(bot, text="Run a search first.",
                                           text_color=SUBTEXT,
                                           font=ctk.CTkFont("SF Pro Text", 9))
        self.sel_count_lbl.pack(side="left", padx=12, pady=10)

        ctk.CTkButton(bot, text="⚡ Push to Instantly",
                      command=self._show_instantly_popup,
                      width=150, height=32, corner_radius=16,
                      fg_color="#0d3d1a", hover_color="#1a5c2a",
                      text_color="#30d158",
                      font=ctk.CTkFont("SF Pro Text", 10, weight="bold")
                      ).pack(side="right", padx=(4, 8), pady=9)
        ctk.CTkButton(bot, text="Export CSV",
                      command=self._export_csv,
                      width=110, height=32, corner_radius=16,
                      fg_color=CARD, hover_color=BORDER,
                      text_color=GREEN, border_width=1, border_color=BORDER,
                      font=ctk.CTkFont("SF Pro Text", 10, weight="bold")
                      ).pack(side="right", padx=4, pady=9)
        ctk.CTkButton(bot, text="Save to Tearsheet / Hotlist",
                      command=self._show_tearsheet_popup,
                      width=200, height=32, corner_radius=16,
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      text_color=WHITE,
                      font=ctk.CTkFont("SF Pro Text", 10, weight="bold")
                      ).pack(side="right", padx=4, pady=9)

    # ── Log tab ────────────────────────────────────────────────────────────
    def _build_log_tab(self):
        tab = tk.Frame(self.notebook, bg=BG)
        self.notebook.add(tab, text="  Log  ")
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)

        log_frame = tk.Frame(tab, bg=ENTRY_BG)
        log_frame.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, bg=ENTRY_BG, fg=TEXT,
                           font=("Consolas", 9), state="disabled",
                           relief="flat", wrap="word",
                           insertbackground=TEXT, padx=10, pady=8)
        self.log.grid(row=0, column=0, sticky="nsew")
        log_sb = DarkScrollbar(log_frame, command=self.log.yview)
        log_sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=log_sb.set)
        self.log.tag_config("good",  foreground=GREEN)
        self.log.tag_config("error", foreground=RED)
        self.log.tag_config("info",  foreground=ACCENT)
        self.log.tag_config("head",  foreground="#e08090",
                             font=("Consolas", 9, "bold"))

    def _log(self, msg, tag=None):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.config(state="normal")
        if tag:
            self.log.insert("end", f"[{ts}] {msg}\n", tag)
        else:
            self.log.insert("end", f"[{ts}] {msg}\n")
        self.log.see("end")
        self.log.config(state="disabled")

    # ── Search ─────────────────────────────────────────────────────────────
    def _run_search(self):
        if not self._connected:
            messagebox.showwarning("Not connected", "Connect to Bullhorn first.")
            return
        query = self._build_query()
        self._log(f"Query: {query}", "info")
        self.results_lbl.config(text="Searching…")

        def _do():
            try:
                def _cb(m): self.after(0, lambda msg=m: self._log(msg, "info"))
                data = self.api.search_contacts(query, count=99999, log_cb=_cb)
                self.all_contacts = data.get("data", [])
                total = data.get("total", len(self.all_contacts))
                self.after(0, self._populate_tree)
                self.after(0, lambda: self.results_lbl.config(
                    text=f"{len(self.all_contacts)} of {total} contacts loaded"))
                self._log(f"Loaded {len(self.all_contacts)} of {total} contacts.", "good")
            except Exception as e:
                self.after(0, lambda: self._log(f"Search error: {e}", "error"))
                self.after(0, lambda: self.results_lbl.config(text=f"Error: {e}"))
        threading.Thread(target=_do, daemon=True).start()

    def _populate_tree(self):
        # Detach tree from display during bulk insert — no per-row flicker
        self.tree.configure(displaycolumns=self.tree["columns"])
        self.tree.delete(*self.tree.get_children())
        self.contact_vars.clear()

        # Batch all inserts without triggering a redraw each time
        self.tree.update_idletasks()
        for c in self.all_contacts:
            cid     = c["id"]
            name    = f"{c.get('firstName','')} {c.get('lastName','')}".strip()
            corp    = c.get("clientCorporation") or {}
            company = corp.get("name", "") if isinstance(corp, dict) else ""
            title   = c.get("occupation") or ""
            county  = clean_list_field(c.get("customTextBlock2") or "")
            ind     = clean_list_field(c.get("customTextBlock4") or "")
            tow     = clean_list_field(c.get("customTextBlock5") or "")
            email   = c.get("email") or ""
            status  = c.get("status") or ""
            self.contact_vars[cid] = {"remove": False, "data": c}
            vals = ("☑", name, company, title, county, ind, tow, email, status)
            self.tree.insert("", "end", iid=str(cid), values=vals, tags=("keep",))

        self._update_count()
        self.auto_status_lbl.config(
            text=f"{len(self.all_contacts)} loaded — enter candidate title and click Apply")
        self.notebook.select(0)

    def _update_count(self):
        keep = sum(1 for v in self.contact_vars.values() if not v["remove"])
        excl = len(self.contact_vars) - keep
        # Count uncertain (yellow ?) rows — those that are "removed" but tagged uncertain
        uncertain = sum(
            1 for iid in self.tree.get_children()
            if "uncertain" in self.tree.item(iid, "tags")
            and self.contact_vars.get(int(iid), {}).get("remove", False)
        )
        parts = [f"☑ {keep} selected"]
        if uncertain:
            parts.append(f"? {uncertain} review")
        plain_excl = excl - uncertain
        if plain_excl:
            parts.append(f"☐ {plain_excl} excluded")
        self.sel_count_lbl.configure(
            text="  ·  ".join(parts),
            text_color=TEXT if keep > 0 else SUBTEXT)

    # ── Toggle / auto filter ───────────────────────────────────────────────
    def _toggle_check(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or self.tree.identify("region", event.x, event.y) != "cell":
            return
        try:
            cid = int(iid)
        except ValueError:
            return
        new_remove = not self.contact_vars[cid]["remove"]
        self.contact_vars[cid]["remove"] = new_remove
        vals    = list(self.tree.item(iid, "values"))
        vals[0] = "☐" if new_remove else "☑"
        self.tree.item(iid, values=vals, tags=("remove" if new_remove else "keep",))
        self._update_count()

    def _check_all(self):
        for cid, v in self.contact_vars.items():
            v["remove"] = False
            vals = list(self.tree.item(str(cid), "values"))
            vals[0] = "☑"
            self.tree.item(str(cid), values=vals, tags=("keep",))
        self._update_count()
        self.auto_status_lbl.config(text="All contacts re-selected.")

    def _run_auto_filter(self):
        candidate = self.candidate_var.get().strip()
        if not candidate:
            messagebox.showwarning("Missing", "Enter the candidate's job title first.")
            return
        remove_n = keep_n = uncertain_n = 0
        for c in self.all_contacts:
            cid   = c["id"]
            title = (c.get("occupation") or "").strip()
            vals  = list(self.tree.item(str(cid), "values"))
            result = classify_auto(title, candidate)

            # Debug: log every keep result so we can see what slipped through
            if result == "keep":
                nc = normalise(title)
                nk = normalise(candidate)
                lc = get_level(nc)
                lk = get_level(nk)
                self._log(
                    f"KEEP: {title!r}  normalised={nc!r}  "
                    f"contact_level={lc}  cand_level={lk}", "info")

            if result == "remove":
                vals[0] = "☐"
                self.tree.item(str(cid), values=vals, tags=("remove",))
                self.contact_vars[cid]["remove"] = True
                remove_n += 1
            elif result == "uncertain":
                vals[0] = "?"
                self.tree.item(str(cid), values=vals, tags=("uncertain",))
                self.contact_vars[cid]["remove"] = True
                uncertain_n += 1
            else:
                vals[0] = "☑"
                self.tree.item(str(cid), values=vals, tags=("keep",))
                self.contact_vars[cid]["remove"] = False
                keep_n += 1
        self.auto_status_lbl.config(
            text=f"☑ {keep_n} keep  ·  ☐ {remove_n} excluded  ·  ? {uncertain_n} review  (click any row to override)")
        self._update_count()
        self._log(
            f"Auto-filter '{candidate}': {keep_n} kept, {remove_n} excluded, "
            f"{uncertain_n} flagged for review. Check log for KEEP details.", "info")

    # ── Kept contacts ──────────────────────────────────────────────────────
    def _get_kept(self):
        return [v["data"] for v in self.contact_vars.values() if not v["remove"]]

    # ── Export CSV ─────────────────────────────────────────────────────────
    def _export_csv(self):
        if not self.contact_vars:
            messagebox.showwarning("No data", "Run a search first.")
            return
        kept = self._get_kept()
        if not kept:
            messagebox.showwarning("Nothing to export", "All contacts are excluded.")
            return
        path = asksaveasfilename(defaultextension=".csv",
                                 filetypes=[("CSV files", "*.csv")],
                                 initialfile="mailshot_contacts.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "id", "firstName", "lastName", "occupation", "email",
                "phone", "mobile", "company", "emailDomain",
                "county", "industry", "typeOfWork", "status"])
            writer.writeheader()
            for c in kept:
                corp = c.get("clientCorporation") or {}
                writer.writerow({
                    "id":          c.get("id", ""),
                    "firstName":   c.get("firstName", ""),
                    "lastName":    c.get("lastName", ""),
                    "occupation":  c.get("occupation", ""),
                    "email":       c.get("email", ""),
                    "phone":       c.get("phone", ""),
                    "mobile":      c.get("mobile", ""),
                    "company":     corp.get("name", "") if isinstance(corp, dict) else "",
                    "emailDomain": corp.get("customTextBlock1", "") if isinstance(corp, dict) else "",
                    "county":      clean_list_field(c.get("customTextBlock2", "")),
                    "industry":    clean_list_field(c.get("customTextBlock4", "")),
                    "typeOfWork":  clean_list_field(c.get("customTextBlock5", "")),
                    "status":      c.get("status", ""),
                })
        messagebox.showinfo("Exported", f"Saved {len(kept)} contacts to:\n{path}")
        self._log(f"Exported {len(kept)} contacts → {path}", "good")

    # ── Tearsheet / Hotlist popup ──────────────────────────────────────────
    def _show_tearsheet_popup(self):
        if not self.contact_vars:
            messagebox.showwarning("No data", "Run a search first.")
            return
        kept_ids = [v["data"]["id"] for v in self.contact_vars.values() if not v["remove"]]
        if not kept_ids:
            messagebox.showwarning("Nothing selected", "No contacts are selected.")
            return

        # ── Dim overlay ────────────────────────────────────────────────
        overlay = _show_overlay(self)

        # ── Dialog ─────────────────────────────────────────────────────
        dlg = tk.Toplevel(self)
        dlg.withdraw()           # hide immediately — no flash at wrong position
        dlg.title("Save to Tearsheet / Hotlist")
        dlg.configure(bg=PANEL)
        dlg.resizable(False, False)
        dlg.grab_set()

        W, H = 500, 360
        sw   = dlg.winfo_screenwidth()
        sh   = dlg.winfo_screenheight()
        cx, cy = (sw - W) // 2, (sh - H) // 2
        _popup_show(dlg, W, H, cx, cy, offset=24)

        def _close_all():
            _popup_hide(dlg, overlay=overlay)

        if overlay:
            dlg.bind("<Destroy>",
                     lambda e, ov=overlay: (ov.destroy() if e.widget is dlg else None))

        # ── Header ─────────────────────────────────────────────────────
        ctk.CTkFrame(dlg, fg_color=ACCENT, corner_radius=0, height=4).pack(fill="x")
        hf = ctk.CTkFrame(dlg, fg_color=PANEL, corner_radius=0)
        hf.pack(fill="x", padx=20, pady=(12, 4))
        ctk.CTkLabel(hf, text="Save to Tearsheet / Hotlist",
                     font=ctk.CTkFont("SF Pro Text", 13, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(hf, text=f"  {len(kept_ids)} contacts",
                     font=ctk.CTkFont("SF Pro Text", 10),
                     text_color=SUBTEXT).pack(side="left")

        # ── Body ───────────────────────────────────────────────────────
        body = ctk.CTkFrame(dlg, fg_color=PANEL, corner_radius=0)
        body.pack(fill="both", expand=True, padx=20)

        ctk.CTkLabel(body, text="Tearsheet name:",
                     font=ctk.CTkFont("SF Pro Text", 10),
                     text_color=SUBTEXT, anchor="w").pack(anchor="w", pady=(8, 3))

        name_var = tk.StringVar()

        # Status label shown below name entry (for duplicate warning / progress)
        status_lbl = ctk.CTkLabel(body, text="",
                                   font=ctk.CTkFont("SF Pro Text", 9),
                                   text_color=SUBTEXT, anchor="w", wraplength=440)

        name_entry = ctk.CTkEntry(body, textvariable=name_var,
                                   fg_color=ENTRY_BG, text_color=TEXT,
                                   border_color=BORDER, border_width=1,
                                   corner_radius=8,
                                   placeholder_text="e.g. Structural Steel – June 2026",
                                   placeholder_text_color=SUBTEXT,
                                   font=ctk.CTkFont("SF Pro Text", 12), height=36)
        name_entry.pack(fill="x", pady=(0, 4))
        status_lbl.pack(anchor="w", pady=(0, 6))

        # Check for duplicate name as user types (debounced)
        _check_after = [None]
        def _on_name_type(*_):
            if _check_after[0]:
                dlg.after_cancel(_check_after[0])
            n = name_var.get().strip()
            if not n:
                status_lbl.configure(text="", text_color=SUBTEXT)
                return
            _check_after[0] = dlg.after(500, lambda: _check_name(n))

        def _check_name(n):
            def _fetch():
                try:
                    safe = n.replace('"', '\\"')
                    r = self.api._req("get", "search/Tearsheet",
                                      params={"query": f'name:("{safe}")',
                                              "fields": "id,name", "count": 5})
                    matches = [d for d in r.json().get("data", [])
                               if d.get("name","").lower() == n.lower()]
                    if matches:
                        dlg.after(0, lambda: status_lbl.configure(
                            text=f"⚠ A tearsheet named '{n}' already exists — saving will create a duplicate.",
                            text_color=YELLOW))
                    else:
                        dlg.after(0, lambda: status_lbl.configure(
                            text="✓ Name available", text_color=GREEN))
                except Exception:
                    pass
            threading.Thread(target=_fetch, daemon=True).start()

        name_var.trace_add("write", _on_name_type)

        # Note checkbox
        note_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(body, text="Also log a note on each contact",
                         variable=note_var,
                         checkbox_width=16, checkbox_height=16, corner_radius=4,
                         fg_color=ACCENT, hover_color=ACCENT_H,
                         border_color=BORDER, checkmark_color=WHITE,
                         text_color=TEXT, font=ctk.CTkFont("SF Pro Text", 10),
                         command=lambda: _toggle_note()
                         ).pack(anchor="w", pady=(2, 4))

        comment_frame = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        ctk.CTkLabel(comment_frame, text="Comment:",
                     font=ctk.CTkFont("SF Pro Text", 9),
                     text_color=SUBTEXT, anchor="w").pack(anchor="w", pady=(4, 2))
        comment_text = tk.Text(comment_frame, height=3,
                                bg=ENTRY_BG, fg=TEXT,
                                insertbackground=TEXT, font=("SF Pro Text", 10),
                                relief="flat", padx=8, pady=6,
                                highlightthickness=1, highlightbackground=BORDER)
        comment_text.pack(fill="x")
        comment_text.insert("1.0", "Sent via external email tool.")

        def _toggle_note():
            if note_var.get():
                comment_frame.pack(fill="x", pady=(4, 0))
                dlg.geometry(f"{W}x430+{dlg.winfo_x()}+{dlg.winfo_y()}")
            else:
                comment_frame.pack_forget()
                dlg.geometry(f"{W}x{H}+{dlg.winfo_x()}+{dlg.winfo_y()}")

        # Buttons
        bf = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=0)
        bf.pack(fill="x", pady=(10, 14))

        save_btn = ctk.CTkButton(bf, text="Save to Bullhorn",
                                  command=lambda: _do_save(),
                                  width=160, height=36, corner_radius=18,
                                  fg_color=ACCENT, hover_color=ACCENT_H,
                                  text_color=WHITE,
                                  font=ctk.CTkFont("SF Pro Text", 11, weight="bold"))
        save_btn.pack(side="left")
        ctk.CTkButton(bf, text="Cancel", command=_close_all,
                      width=90, height=36, corner_radius=18,
                      fg_color=CARD, hover_color=BORDER, text_color=SUBTEXT,
                      border_width=1, border_color=BORDER,
                      font=ctk.CTkFont("SF Pro Text", 10)
                      ).pack(side="left", padx=10)

        def _do_save():
            name = name_var.get().strip()
            if not name:
                status_lbl.configure(text="Please enter a name.", text_color=RED)
                return
            comment = comment_text.get("1.0", "end").strip() if note_var.get() else None
            save_btn.configure(state="disabled", text="Saving…")
            status_lbl.configure(text="Saving to Bullhorn…", text_color=ACCENT)
            threading.Thread(target=self._save_to_bullhorn,
                             args=(name, comment, kept_ids, status_lbl, save_btn, _close_all),
                             daemon=True).start()

    def _save_to_bullhorn(self, name, comment, contact_ids, status_lbl, save_btn, close_cb):
        results = []
        try:
            r = self.api._req("put", "entity/Tearsheet", params={},
                              json={"name": name, "isPrivate": False,
                                    "description": f"Mailshot export — {len(contact_ids)} contacts"})
            data = r.json()
            if "changedEntityId" not in data:
                raise Exception(data.get("errorMessage", str(data)))
            ts_id = data["changedEntityId"]
            self.api._req("post", f"massUpdate/Tearsheet/{ts_id}", params={},
                          json={"clientContacts": {"add": contact_ids}})
            results.append(f"✓ Tearsheet '{name}' created ({len(contact_ids)} contacts)")
            self._log(f"Tearsheet '{name}' saved with {len(contact_ids)} contacts.", "good")
        except Exception as e:
            results.append(f"✗ Tearsheet failed: {e}")
            self._log(f"Tearsheet error: {e}", "error")

        if comment is not None:
            try:
                elements = [{"_dtoType": "ClientContact", "id": cid} for cid in contact_ids]
                r2 = self.api._req("put", "entity/Note", params={},
                                   json={"action": "Email Sent",
                                         "comments": f"{name}\n\n{comment}",
                                         "elementsToLink": elements})
                data2 = r2.json()
                if "changedEntityId" not in data2:
                    raise Exception(data2.get("errorMessage", str(data2)))
                results.append(f"✓ Note logged on {len(contact_ids)} profiles")
            except Exception as e:
                results.append(f"✗ Note failed: {e}")

        success = all("✓" in r for r in results)
        msg     = "  ·  ".join(results)

        if success:
            # Show success briefly then close with fade
            self.after(0, lambda: status_lbl.configure(text=msg, text_color=GREEN))
            self.after(0, lambda: save_btn.configure(text="✓ Saved!", fg_color=ACCENT_D))
            self.after(800 if IS_WINDOWS else 1600, close_cb)
        else:
            self.after(0, lambda: status_lbl.configure(text=msg, text_color=RED))
            self.after(0, lambda: save_btn.configure(state="normal", text="Save to Bullhorn",
                                                      fg_color=ACCENT))

    def _show_instantly_popup(self):
        if not self.contact_vars:
            messagebox.showwarning("No data", "Run a search first.")
            return
        kept = self._get_kept()
        if not kept:
            messagebox.showwarning("Nothing to send", "All contacts are excluded.")
            return
        with_email = [c for c in kept if (c.get("email") or "").strip()]
        if not with_email:
            messagebox.showwarning("No emails",
                                   "None of the selected contacts have an email address.")
            return

        overlay = _show_overlay(self)
        popup   = InstantlyCampaignPopup(self, self.instantly, with_email)
        if overlay:
            popup.bind("<Destroy>",
                       lambda e, ov=overlay: (ov.destroy() if e.widget is popup else None))


# ═══════════════════════════════════════════════════════════════════════════
def _standalone():
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title("Cornerstone — Mailshot Helper")
    root.geometry("1300x860")
    root.minsize(1100, 700)
    _set_window_icon(root)
    tool = MailshotHelperTool(root)
    tool.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    _standalone()
