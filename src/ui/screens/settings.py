"""
Voice Studio - Экран настроек
"""

import json
import subprocess
import threading
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from src.ui.screens.base import BaseScreen
from src.ui.theme import FONT_FAMILY, FONT_FAMILY_MONO, COLORS, apply_theme, THEMES
from src.utils.config import get_config, YANDEX_VOICES, DEEPSEEK_MODELS


class SettingsScreen(BaseScreen):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vars = {}

    def _add_entry_menu(self, entry_widget):
        """Контекстное меню (ПКМ) с Копировать/Вставить/Вырезать/Выделить всё."""
        menu = tk.Menu(entry_widget, tearoff=0)
        menu.add_command(
            label="Вырезать",
            command=lambda: entry_widget.event_generate("<<Cut>>"),
        )
        menu.add_command(
            label="Копировать",
            command=lambda: entry_widget.event_generate("<<Copy>>"),
        )
        menu.add_command(
            label="Вставить",
            command=lambda: entry_widget.event_generate("<<Paste>>"),
        )
        menu.add_separator()
        menu.add_command(
            label="Выделить всё",
            command=lambda: (
                entry_widget.select_range(0, "end"),
                entry_widget.icursor("end"),
            ),
        )

        def _show_menu(event):
            entry_widget.focus_set()
            menu.tk_popup(event.x_root, event.y_root)

        entry_widget.bind("<Button-3>", _show_menu)

    def _create_entry(self, parent, var_name, config, config_key,
                      default="", show=None, width=50):
        """Создаёт Entry с привязкой к переменной и контекстным меню."""
        self._vars[var_name] = tk.StringVar(value=config.get(config_key, default))
        entry = ttk.Entry(parent, textvariable=self._vars[var_name], width=width)
        if show:
            entry.configure(show=show)
        self._add_entry_menu(entry)
        return entry

    def _create_ui(self):
        config = get_config()

        # Скроллируемый контейнер
        canvas = tk.Canvas(self.frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            self.frame, orient=VERTICAL,
            command=canvas.yview, bootstyle="round",
        )
        scrollable = ttk.Frame(canvas)
        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=YES, padx=20, pady=10)
        scrollbar.pack(side=RIGHT, fill=Y, pady=10)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _on_mousewheel)

        # ═══ DeepSeek API ═══
        ds_frame = ttk.LabelFrame(scrollable, text="  DeepSeek API  ")
        ds_frame.pack(fill=X, pady=(0, 16), padx=5, ipadx=12, ipady=8)

        # API-ключ
        row = ttk.Frame(ds_frame)
        row.pack(fill=X, pady=(0, 8))
        ttk.Label(row, text="API-ключ:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._create_entry(
            row, "deepseek_api_key", config, "deepseek_api_key", show="*"
        ).pack(side=LEFT, fill=X, expand=YES)

        # Модель
        row2 = ttk.Frame(ds_frame)
        row2.pack(fill=X, pady=(0, 4))
        ttk.Label(row2, text="Модель:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._vars["deepseek_model"] = tk.StringVar(
            value=config.get("deepseek_model", "deepseek-chat")
        )
        ttk.Combobox(
            row2, textvariable=self._vars["deepseek_model"],
            values=DEEPSEEK_MODELS, state="readonly", width=25,
        ).pack(side=LEFT)

        # ═══ Yandex SpeechKit ═══
        ya_frame = ttk.LabelFrame(scrollable, text="  Yandex SpeechKit  ")
        ya_frame.pack(fill=X, pady=(0, 16), padx=5, ipadx=12, ipady=8)

        # API-ключ
        row3 = ttk.Frame(ya_frame)
        row3.pack(fill=X, pady=(0, 8))
        ttk.Label(row3, text="API-ключ:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._create_entry(
            row3, "yandex_api_key", config, "yandex_api_key", show="*"
        ).pack(side=LEFT, fill=X, expand=YES)

        # Folder ID
        row4 = ttk.Frame(ya_frame)
        row4.pack(fill=X, pady=(0, 8))
        ttk.Label(row4, text="Folder ID:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._create_entry(
            row4, "yandex_folder_id", config, "yandex_folder_id", width=40
        ).pack(side=LEFT, fill=X, expand=YES)

        # Кнопка: Получить из YC CLI
        row_yc = ttk.Frame(ya_frame)
        row_yc.pack(fill=X, pady=(0, 8))
        self._yc_btn = ttk.Button(
            row_yc, text="Получить из YC CLI",
            bootstyle="info-outline", padding=(10, 4),
            command=self._fetch_yc_keys,
        )
        self._yc_btn.pack(side=LEFT)
        self._yc_status = ttk.Label(
            row_yc, text="", font=(FONT_FAMILY, 9),
        )
        self._yc_status.pack(side=LEFT, padx=(10, 0))

        # Голос
        row5 = ttk.Frame(ya_frame)
        row5.pack(fill=X, pady=(0, 8))
        ttk.Label(row5, text="Голос:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._vars["voice"] = tk.StringVar(value=config.get("voice", "kirill"))
        voice_combo = ttk.Combobox(
            row5, textvariable=self._vars["voice"],
            values=list(YANDEX_VOICES.keys()), state="readonly", width=20,
        )
        voice_combo.pack(side=LEFT, padx=(0, 16))
        voice_combo.bind("<<ComboboxSelected>>", self._on_voice_changed)

        # Роль
        ttk.Label(row5, text="Роль:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._vars["role"] = tk.StringVar(value=config.get("role", "neutral"))
        self._role_combo = ttk.Combobox(
            row5, textvariable=self._vars["role"],
            state="readonly", width=15,
        )
        self._role_combo.pack(side=LEFT)
        self._update_roles()

        # Скорость
        row6 = ttk.Frame(ya_frame)
        row6.pack(fill=X, pady=(0, 4))
        ttk.Label(row6, text="Скорость:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._vars["speed"] = tk.DoubleVar(value=config.get("speed", 1.0))
        ttk.Spinbox(
            row6, textvariable=self._vars["speed"],
            from_=0.5, to=2.0, increment=0.1,
            width=6, font=(FONT_FAMILY, 10),
        ).pack(side=LEFT)
        ttk.Label(
            row6, text="(0.5 - 2.0)",
            font=(FONT_FAMILY, 8), bootstyle="secondary",
        ).pack(side=LEFT, padx=(8, 0))

        # Тембр (pitch_shift)
        row_pitch = ttk.Frame(ya_frame)
        row_pitch.pack(fill=X, pady=(0, 8))
        ttk.Label(row_pitch, text="Тембр (Гц):", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._vars["pitch_shift"] = tk.DoubleVar(
            value=config.get("pitch_shift", 0.0)
        )
        ttk.Spinbox(
            row_pitch, textvariable=self._vars["pitch_shift"],
            from_=-1000, to=1000, increment=50,
            width=8, font=(FONT_FAMILY, 10),
        ).pack(side=LEFT)
        ttk.Label(
            row_pitch, text="(-1000 .. +1000, 0 = без изменений)",
            font=(FONT_FAMILY, 8), bootstyle="secondary",
        ).pack(side=LEFT, padx=(8, 0))

        # Громкость (volume LUFS)
        row_vol = ttk.Frame(ya_frame)
        row_vol.pack(fill=X, pady=(0, 4))
        ttk.Label(row_vol, text="Громкость (LUFS):", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._vars["volume"] = tk.DoubleVar(
            value=config.get("volume", -19.0)
        )
        ttk.Spinbox(
            row_vol, textvariable=self._vars["volume"],
            from_=-149, to=0, increment=1,
            width=8, font=(FONT_FAMILY, 10),
        ).pack(side=LEFT)
        ttk.Label(
            row_vol, text="(-149 .. 0, рекомендуется -19)",
            font=(FONT_FAMILY, 8), bootstyle="secondary",
        ).pack(side=LEFT, padx=(8, 0))

        # ═══ Интерфейс ═══
        ui_frame = ttk.LabelFrame(scrollable, text="  Интерфейс  ")
        ui_frame.pack(fill=X, pady=(0, 16), padx=5, ipadx=12, ipady=8)

        row7 = ttk.Frame(ui_frame)
        row7.pack(fill=X)
        ttk.Label(row7, text="Тёмная тема:", font=(FONT_FAMILY, 10)).pack(
            side=LEFT, padx=(0, 8)
        )
        self._vars["theme_dark"] = tk.BooleanVar(
            value=config.get("theme", "dark") == "dark"
        )
        ttk.Checkbutton(
            row7, variable=self._vars["theme_dark"],
            bootstyle="round-toggle",
        ).pack(side=LEFT)

        # ═══ Кнопка сохранения ═══
        btn_frame = ttk.Frame(scrollable)
        btn_frame.pack(fill=X, pady=(8, 20), padx=5)

        self._save_status = ttk.Label(
            btn_frame, text="", font=(FONT_FAMILY, 10),
        )
        self._save_status.pack(side=RIGHT, padx=(8, 0))

        ttk.Button(
            btn_frame, text="Сохранить",
            bootstyle="success", padding=(20, 8),
            command=self._save,
        ).pack(side=RIGHT)

    def _on_voice_changed(self, event=None):
        self._update_roles()

    def _update_roles(self):
        voice = self._vars["voice"].get()
        roles = YANDEX_VOICES.get(voice, {}).get("roles", ["neutral"])
        self._role_combo.configure(values=roles)
        current = self._vars["role"].get()
        if current not in roles:
            self._vars["role"].set(roles[0])

    def _fetch_yc_keys(self):
        """Получает API-ключ и Folder ID через yc CLI (фоновый поток)."""
        self._yc_btn.configure(state="disabled")
        self._yc_status.configure(text="Получение...", bootstyle="info")

        def _worker():
            try:
                # WARNING: shell=True is used here because yc CLI requires shell
                # environment on Windows. Commands are hardcoded strings (not user
                # input), so shell injection risk is minimal. Do NOT pass unsanitized
                # user input to these calls.
                folder_id = subprocess.check_output(
                    "yc config get folder-id", shell=True,
                ).decode().strip()

                sa_list = subprocess.check_output(
                    "yc iam service-account list --format json", shell=True,
                ).decode()
                accounts = json.loads(sa_list)

                sa_id = None
                for sa in accounts:
                    if sa["name"] == "voice-studio":
                        sa_id = sa["id"]
                        break

                if not sa_id:
                    self.app.root.after(0, lambda: self._yc_done(
                        False, "Сервисный аккаунт 'voice-studio' не найден"
                    ))
                    return

                # sa_id comes from yc CLI JSON output (UUID format), not user input
                key_data = subprocess.check_output(
                    f"yc iam api-key create --service-account-id {sa_id} --format json",
                    shell=True,
                ).decode()
                api_key = json.loads(key_data)["secret"]

                self.app.root.after(0, lambda: self._yc_done(
                    True, "Ключи получены",
                    api_key=api_key, folder_id=folder_id,
                ))

            except FileNotFoundError:
                self.app.root.after(0, lambda: self._yc_done(
                    False, "yc CLI не установлен"
                ))
            except Exception as e:
                msg = str(e)[:80]
                self.app.root.after(0, lambda: self._yc_done(False, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _yc_done(self, success, message, api_key=None, folder_id=None):
        """Callback после получения ключей из YC CLI."""
        self._yc_btn.configure(state="normal")
        if success:
            self._vars["yandex_api_key"].set(api_key)
            self._vars["yandex_folder_id"].set(folder_id)
            self._yc_status.configure(text=message, bootstyle="success")
        else:
            self._yc_status.configure(text=message, bootstyle="danger")
        self.app.root.after(5000, lambda: self._yc_status.configure(text=""))

    def _save(self):
        config = get_config()

        config.set("deepseek_api_key", self._vars["deepseek_api_key"].get().strip())
        config.set("deepseek_model", self._vars["deepseek_model"].get())
        config.set("yandex_api_key", self._vars["yandex_api_key"].get().strip())
        config.set("yandex_folder_id", self._vars["yandex_folder_id"].get().strip())
        config.set("voice", self._vars["voice"].get())
        config.set("role", self._vars["role"].get())
        config.set("speed", self._vars["speed"].get())
        config.set("pitch_shift", self._vars["pitch_shift"].get())
        config.set("volume", self._vars["volume"].get())

        theme = "dark" if self._vars["theme_dark"].get() else "light"
        config.set("theme", theme)

        if config.save():
            apply_theme(self.app.root, theme)
            self._save_status.configure(text="Сохранено", bootstyle="success")
        else:
            self._save_status.configure(text="Ошибка сохранения", bootstyle="danger")

        self.app.root.after(3000, lambda: self._save_status.configure(text=""))
