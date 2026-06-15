"""Cornerstone Tools — multi-tool shell.
Each tool lives in its own module and exposes an embeddable CTkFrame:
  cv_parse_format_tool.CVParseFormatTool   — CV Parse & Format  V0.1
  import_contact_tool.BullhornImportTool   — Import Contacts    V2.0
Add future tools to the TOOLS list below.
"""

import os
import sys

import customtkinter as ctk
from PIL import Image, ImageDraw

ctk.set_appearance_mode("light")


def _flat_icon(kind, color="#5a6472", size=24):
    """Draw a flat outline icon (supersampled for smooth anti-aliasing)."""
    S = 8                      # supersample factor
    W = size * S
    lw = int(1.8 * S)
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def E(*xy):                # scale 0-24 coords up
        return [v * S for v in xy]

    if kind == "candidate":    # person: head + shoulders
        d.ellipse(E(7.5, 3, 16.5, 12), outline=color, width=lw)
        d.arc(E(3.5, 13.5, 20.5, 30), 180, 360, fill=color, width=lw)
    elif kind == "upload":     # tray + up arrow
        d.line(E(4, 15, 4, 19), fill=color, width=lw)
        d.line(E(4, 19, 20, 19), fill=color, width=lw)
        d.line(E(20, 15, 20, 19), fill=color, width=lw)
        d.line(E(12, 4, 12, 14), fill=color, width=lw)
        d.line(E(7.5, 8.5, 12, 4), fill=color, width=lw)
        d.line(E(12, 4, 16.5, 8.5), fill=color, width=lw)
    elif kind == "email":      # envelope outline + flap
        d.rectangle(E(3, 7, 21, 17), outline=color, width=lw)
        d.line(E(3, 7, 12, 13), fill=color, width=lw)
        d.line(E(12, 13, 21, 7), fill=color, width=lw)
    im = im.resize((size, size), Image.LANCZOS)
    return im


def tool_icon(kind, active=False, size=24):
    return ctk.CTkImage(light_image=_flat_icon(kind, "#b8965a" if active else "#5a6472", size),
                        size=(size, size))

# shell palette (matches the CV tool's paper theme)
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
        self.frames = {}        # tool id → instantiated frame (lazy)
        self.buttons = {}
        self.active = None
        self.expanded = False
        self._build()
        self.show_tool(TOOLS[0]["id"])

    def _build(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0,
                                    border_width=1, border_color=HAIR, width=58)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkButton(self.sidebar, text="☰", width=42, height=36, fg_color="transparent",
                      hover_color=SURFACE, text_color=MUTED, font=FONT_BOLD,
                      command=self.toggle).pack(pady=(10, 14))
        self.icons = {t["id"]: {"idle": tool_icon(t["icon"]),
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

        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

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
            # Add the tool's subfolder to sys.path so its module can be imported
            tool_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), tool["folder"])
            if tool_dir not in sys.path:
                sys.path.insert(0, tool_dir)
            mod = importlib.import_module(tool["module"])
            # Run first-time dependency check if the tool exposes one
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
