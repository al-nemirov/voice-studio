"""
Voice Studio — Главный запуск приложения
"""

import sys
import traceback
from pathlib import Path
import logging

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src import APP_TITLE, __version__
from src.ui.theme import (
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    FONT_FAMILY, init_theme,
)
from src.ui.screens.base import BaseScreen


class VoiceStudioApp:
    """Главный класс приложения"""

    def __init__(self):
        self.current_screen: BaseScreen | None = None
        self.screens: dict[str, BaseScreen] = {}
        self.nav_buttons: dict[str, ttk.Button] = {}

        # Окно
        self.root = ttk.Window(title=APP_TITLE, resizable=(True, True))
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self._center_window()
        init_theme(self.root)

        self._setup_layout()
        self._init_screens()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self._fix_clipboard_bindings()
        self.root.after(100, lambda: self.show_screen("batch"))

    def _center_window(self):
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - WINDOW_WIDTH) // 2
        y = (self.root.winfo_screenheight() - WINDOW_HEIGHT) // 2
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")

    def _setup_layout(self):
        self.root.configure(highlightthickness=0, bd=0)
        self.base_layout = ttk.Frame(self.root)
        self.base_layout.pack(fill=BOTH, expand=YES, padx=0, pady=0)

        # ══ Top Navbar ══
        self.navbar = ttk.Frame(self.base_layout, bootstyle="dark")
        self.navbar.pack(fill=X)

        logo_frame = ttk.Frame(self.navbar, bootstyle="dark")
        logo_frame.pack(side=LEFT, padx=(16, 0), pady=(6, 6))

        ttk.Label(
            logo_frame, text="VS",
            font=(FONT_FAMILY, 11, "bold"),
            foreground="#5a9fd4", bootstyle="inverse-dark",
        ).pack(side=LEFT, padx=(0, 8))

        ttk.Label(
            logo_frame, text=f"v{__version__}",
            font=(FONT_FAMILY, 8),
            foreground="#6c7a89", bootstyle="inverse-dark",
        ).pack(side=LEFT, pady=(2, 0))

        nav_frame = ttk.Frame(self.navbar, bootstyle="dark")
        nav_frame.pack(side=LEFT, padx=(32, 0))

        menu_items = [
            ("batch", "Пакетная"),
            ("settings", "Настройки"),
        ]

        for screen_id, text in menu_items:
            btn = ttk.Button(
                nav_frame, text=text,
                bootstyle="link", cursor="hand2",
                padding=(10, 6),
                command=lambda s=screen_id: self.show_screen(s),
            )
            btn.pack(side=LEFT, padx=1)
            self.nav_buttons[screen_id] = btn

        # ══ Content Area ══
        self.content_area = ttk.Frame(self.base_layout)
        self.content_area.pack(fill=BOTH, expand=YES)

        self.page_title = ttk.Label(
            self.content_area, text="",
            font=(FONT_FAMILY, 14, "bold"), bootstyle="light",
        )
        self.page_title.pack(anchor="nw", padx=20, pady=(10, 2))

        self.screen_container = ttk.Frame(self.content_area)
        self.screen_container.pack(fill=BOTH, expand=YES)

    def _init_screens(self):
        try:
            from src.ui.screens.batch import BatchScreen
            from src.ui.screens.settings import SettingsScreen

            self.screens = {
                "batch": BatchScreen(self.screen_container, self),
                "settings": SettingsScreen(self.screen_container, self),
            }
        except ImportError as e:
            print(f"ОШИБКА импорта экранов: {e}")
            traceback.print_exc()

            class ErrorScreen(BaseScreen):
                def _create_ui(self):
                    ttk.Label(
                        self.frame,
                        text=f"Ошибка загрузки экранов\n{e}",
                        font=(FONT_FAMILY, 14),
                        bootstyle="danger", justify="center",
                    ).pack(expand=True, fill=BOTH, padx=60, pady=100)

            self.screens = {"batch": ErrorScreen(self.screen_container, self)}

    def show_screen(self, screen_name: str, **kwargs):
        if screen_name not in self.screens:
            return

        if self.current_screen:
            self.current_screen.hide()

        titles = {
            "batch": "Пакетная обработка",
            "settings": "Настройки",
        }
        self.page_title.configure(text=titles.get(screen_name, "Voice Studio"))

        for sid, btn in self.nav_buttons.items():
            btn.configure(bootstyle="info" if sid == screen_name else "link")

        try:
            self.current_screen = self.screens[screen_name]
            self.current_screen.show(**kwargs)
        except Exception as e:
            logging.getLogger(__name__).error(f"Ошибка экрана {screen_name}: {e}")

    def _fix_clipboard_bindings(self):
        """Ctrl+C/V/X/A для всех Entry и Text виджетов."""
        self.root.event_add("<<SelectAll>>", "<Control-a>", "<Control-A>")

        def _select_all(event):
            w = event.widget
            if hasattr(w, "select_range"):  # Entry
                w.select_range(0, "end")
                w.icursor("end")
                return "break"
            elif hasattr(w, "tag_add"):  # Text
                w.tag_add("sel", "1.0", "end")
                return "break"

        self.root.bind_class("TEntry", "<Control-a>", _select_all)
        self.root.bind_class("TEntry", "<Control-A>", _select_all)
        self.root.bind_class("Text", "<Control-a>", _select_all)
        self.root.bind_class("Text", "<Control-A>", _select_all)

        # Принудительные биндинги Ctrl+C/V/X через виртуальные события
        for cls in ("TEntry", "TCombobox", "TSpinbox", "Text"):
            self.root.bind_class(cls, "<Control-c>", lambda e: e.widget.event_generate("<<Copy>>"))
            self.root.bind_class(cls, "<Control-C>", lambda e: e.widget.event_generate("<<Copy>>"))
            self.root.bind_class(cls, "<Control-v>", lambda e: e.widget.event_generate("<<Paste>>"))
            self.root.bind_class(cls, "<Control-V>", lambda e: e.widget.event_generate("<<Paste>>"))
            self.root.bind_class(cls, "<Control-x>", lambda e: e.widget.event_generate("<<Cut>>"))
            self.root.bind_class(cls, "<Control-X>", lambda e: e.widget.event_generate("<<Cut>>"))

    def _on_closing(self):
        if getattr(self, "_closing", False):
            return
        self._closing = True
        if self.current_screen:
            try:
                self.current_screen.hide()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logging.getLogger(__name__).error(f"Критическая ошибка: {e}")
        finally:
            try:
                self._on_closing()
            except Exception:
                pass
