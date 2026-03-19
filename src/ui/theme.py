"""
Voice Studio - Тема и стили
===============================
Глобальные константы, цвета и темы приложения.
"""

import ttkbootstrap as ttk
from src.utils.config import get_config
from ttkbootstrap.constants import *

# === ОСНОВНЫЕ КОНСТАНТЫ ОКНА ===
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750
WINDOW_MIN_WIDTH = 700
WINDOW_MIN_HEIGHT = 500

# === ШРИФТЫ ===
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

FONT_SIZES = {
    "tiny": 8,
    "small": 9,
    "normal": 10,
    "medium": 11,
    "large": 12,
    "title": 16,
    "header": 18,
    "subtitle": 14,
}

# === ЦВЕТОВЫЕ ТЕМЫ ===
THEMES = {
    "dark": {
        "name": "darkly",
        "bg": "#141414",
        "fg": "#e0e0e0",
        "primary": "#0d7377",
        "success": "#27ae60",
        "info": "#3498db",
        "warning": "#f39c12",
        "danger": "#e74c3c",
        "secondary": "#34495e",
        "light": "#2c3e50",
        "dark": "#0f0f0f",
        "border": "#2a2a2a",
        "hover": "#1e1e1e",
        "selected": "#0d7377",
        "text-muted": "#95a5a6",
    },
    "light": {
        "name": "flatly",
        "bg": "#f8f9fa",
        "fg": "#212529",
        "primary": "#0d6efd",
        "success": "#198754",
        "info": "#0dcaf0",
        "warning": "#ffc107",
        "danger": "#dc3545",
        "secondary": "#6c757d",
        "light": "#ffffff",
        "dark": "#343a40",
        "border": "#dee2e6",
        "hover": "#e9ecef",
        "selected": "#0d6efd",
        "text-muted": "#6c757d",
    },
}

CURRENT_THEME = "dark"
COLORS = dict(THEMES[CURRENT_THEME])

TEXT_STYLES = {
    "title": (FONT_FAMILY, FONT_SIZES["title"], "bold"),
    "header": (FONT_FAMILY, FONT_SIZES["header"], "bold"),
    "subtitle": (FONT_FAMILY, FONT_SIZES["subtitle"], "bold"),
    "normal": (FONT_FAMILY, FONT_SIZES["normal"]),
    "small": (FONT_FAMILY, FONT_SIZES["small"]),
    "mono": (FONT_FAMILY_MONO, FONT_SIZES["normal"]),
}

LABEL_STYLES = {
    "title": "light",
    "header": "light",
    "muted": "secondary",
    "success": "success",
    "warning": "warning",
    "danger": "danger",
}


def apply_theme(root, theme_name: str = "dark"):
    global CURRENT_THEME
    CURRENT_THEME = theme_name
    COLORS.clear()
    COLORS.update(THEMES[theme_name])

    style = ttk.Style()
    style.theme_use(THEMES[theme_name]["name"])
    style.configure(".", background=COLORS["bg"], foreground=COLORS["fg"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["fg"])
    style.configure("TButton", font=(FONT_FAMILY, FONT_SIZES["normal"]))

    root.configure(background=COLORS["bg"])
    root.update_idletasks()


def init_theme(root):
    config = get_config()
    saved_theme = config.get("theme", "dark")
    if saved_theme not in THEMES:
        saved_theme = "dark"
    apply_theme(root, saved_theme)
