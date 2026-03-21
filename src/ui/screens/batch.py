"""
Voice Studio - Экран пакетной обработки
========================================
Единый экран: добавляешь .txt -> очистка -> разметка -> синтез.
Layout: [Очередь | Лог] + прогрессбар внизу.
"""

import glob
import logging
import os
import queue
import shutil
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from src.ui.screens.base import BaseScreen
from src.ui.theme import FONT_FAMILY, FONT_FAMILY_MONO, COLORS
from src.utils.config import get_config, get_api_key, ROOT_DIR


class BatchScreen(BaseScreen):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue_tree = None
        self.log_text = None
        self.progress_bar = None
        self.status_label = None

        self._books = []  # [{name, path, status}]
        self._is_running = False
        self._stop_requested = False
        self._worker_thread = None
        self._log_queue = queue.Queue()
        self._flush_id = None

    def _create_ui(self):
        container = ttk.Frame(self.frame)
        container.pack(fill=BOTH, expand=YES)

        # == Верхняя панель кнопок ==
        toolbar = ttk.Frame(container)
        toolbar.pack(fill=X, padx=20, pady=(8, 4))

        ttk.Button(
            toolbar, text="+ Добавить .txt",
            bootstyle="info-outline", padding=(10, 5),
            command=self._add_files,
        ).pack(side=LEFT, padx=(0, 4))

        ttk.Button(
            toolbar, text="Удалить",
            bootstyle="secondary-outline", padding=(10, 5),
            command=self._remove_selected,
        ).pack(side=LEFT, padx=(0, 4))

        ttk.Separator(toolbar, orient="vertical").pack(side=LEFT, fill=Y, padx=8)

        self._start_btn = ttk.Button(
            toolbar, text="Старт",
            bootstyle="success", padding=(10, 5),
            command=self._start,
        )
        self._start_btn.pack(side=LEFT, padx=(0, 4))

        self._test_btn = ttk.Button(
            toolbar, text="Тест (5 мин)",
            bootstyle="warning-outline", padding=(10, 5),
            command=self._start_test,
        )
        self._test_btn.pack(side=LEFT, padx=(0, 4))

        self._synth_btn = ttk.Button(
            toolbar, text="Синтез",
            bootstyle="info", padding=(10, 5),
            command=self._start_synth, state="disabled",
        )
        self._synth_btn.pack(side=LEFT, padx=(0, 4))

        self._stop_btn = ttk.Button(
            toolbar, text="Стоп",
            bootstyle="danger", padding=(10, 5),
            command=self._stop, state="disabled",
        )
        self._stop_btn.pack(side=LEFT)

        # == Основной контент: Очередь | Лог ==
        paned = tk.PanedWindow(
            container, orient=tk.HORIZONTAL,
            sashwidth=8, bg="#333333",
        )
        paned.pack(fill=BOTH, expand=YES, padx=20, pady=(4, 4))

        # -- Левая панель: Очередь --
        left_panel = ttk.Frame(paned)
        paned.add(left_panel, stretch="always", minsize=200)

        ttk.Label(
            left_panel, text="Очередь",
            font=(FONT_FAMILY, 11, "bold"), bootstyle="light",
        ).pack(anchor="w", padx=8, pady=(4, 4))

        tree_frame = ttk.Frame(left_panel)
        tree_frame.pack(fill=BOTH, expand=YES, padx=4, pady=(0, 4))

        self.queue_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "status"),
            show="headings",
            selectmode="extended",
            style="queue.Treeview",
        )
        self.queue_tree.heading("name", text="Книга")
        self.queue_tree.heading("status", text="Статус")
        self.queue_tree.column("name", width=180, minwidth=100)
        self.queue_tree.column("status", width=100, minwidth=80, anchor="center")

        tree_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical",
            command=self.queue_tree.yview, bootstyle="round",
        )
        self.queue_tree.configure(yscrollcommand=tree_scroll.set)
        self.queue_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        tree_scroll.pack(side=RIGHT, fill=Y)

        # Стили строк
        ttk.Style().configure(
            "queue.Treeview",
            rowheight=26,
            font=(FONT_FAMILY, 9),
        )
        self.queue_tree.tag_configure("pending", foreground="#95a5a6")
        self.queue_tree.tag_configure("running", foreground="#FFD740")
        self.queue_tree.tag_configure("marked", foreground="#42A5F5")
        self.queue_tree.tag_configure("done", foreground="#4CAF50")
        self.queue_tree.tag_configure("error", foreground="#FF5252")

        # -- Правая панель: Лог --
        right_panel = ttk.Frame(paned)
        paned.add(right_panel, stretch="always", minsize=400)

        ttk.Label(
            right_panel, text="Лог обработки",
            font=(FONT_FAMILY, 11, "bold"), bootstyle="light",
        ).pack(anchor="w", padx=8, pady=(4, 4))

        log_frame = ttk.Frame(right_panel)
        log_frame.pack(fill=BOTH, expand=YES, padx=4, pady=(0, 4))

        self.log_text = tk.Text(
            log_frame,
            font=(FONT_FAMILY_MONO, 10),
            bg="#111", fg="#eee",
            insertbackground="#eee",
            padx=12, pady=10,
            wrap="word",
            state="disabled",
        )
        log_scroll = ttk.Scrollbar(
            log_frame, orient="vertical",
            command=self.log_text.yview, bootstyle="round",
        )
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=LEFT, fill=BOTH, expand=YES)
        log_scroll.pack(side=RIGHT, fill=Y)

        # Теги для лога
        self.log_text.tag_configure(
            "chapter", font=(FONT_FAMILY_MONO, 11, "bold"), foreground="#CE93D8",
        )
        self.log_text.tag_configure(
            "success", font=(FONT_FAMILY_MONO, 10, "bold"), foreground="#00E676",
        )
        self.log_text.tag_configure(
            "error", font=(FONT_FAMILY_MONO, 10, "bold"), foreground="#FF5252",
        )
        self.log_text.tag_configure(
            "warning", foreground="#FFD700",
        )
        self.log_text.tag_configure(
            "header", font=(FONT_FAMILY_MONO, 11, "bold"), foreground="#64B5F6",
        )
        self.log_text.tag_configure(
            "separator", foreground="#555555",
        )
        self.log_text.tag_configure(
            "info", foreground="#eeeeee",
        )

        self._add_copy_menu(self.log_text)

        # == Нижняя панель: Прогресс ==
        bottom = ttk.Frame(container)
        bottom.pack(fill=X, padx=20, pady=(0, 12))

        self.status_label = ttk.Label(
            bottom, text="Готов к работе",
            font=(FONT_FAMILY, 10), bootstyle="secondary",
        )
        self.status_label.pack(anchor="w", pady=(0, 4))

        self.progress_bar = ttk.Progressbar(
            bottom, mode="determinate", bootstyle="success-striped",
        )
        self.progress_bar.pack(fill=X)

    # =======================================
    #  УПРАВЛЕНИЕ ОЧЕРЕДЬЮ
    # =======================================

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="Выберите .txt файлы книг",
            filetypes=[("Текстовые файлы", "*.txt")],
            initialdir=str(ROOT_DIR / "books"),
        )
        added = 0
        for fp in files:
            name = Path(fp).stem
            # Проверка дублей
            if any(b["path"] == fp for b in self._books):
                continue
            book = {"name": name, "path": fp, "status": "ожидание"}
            self._books.append(book)
            self.queue_tree.insert(
                "", "end",
                iid=fp,
                values=(name, "ожидание"),
                tags=("pending",),
            )
            added += 1
        if added:
            self._log_immediate(
                f"Добавлено файлов: {added}", "success",
            )

    def _remove_selected(self):
        if self._is_running:
            return
        selected = self.queue_tree.selection()
        for iid in selected:
            self.queue_tree.delete(iid)
            self._books = [b for b in self._books if b["path"] != iid]

    def _update_book_status(self, path: str, status: str):
        """Обновляет статус книги в treeview."""
        tag_map = {
            "ожидание": "pending",
            "очистка": "running",
            "разметка": "running",
            "размечено": "marked",
            "синтез": "running",
            "готово": "done",
            "ошибка": "error",
        }
        tag = tag_map.get(status, "pending")

        for b in self._books:
            if b["path"] == path:
                b["status"] = status
                break

        try:
            name = self.queue_tree.item(path, "values")[0]
            self.queue_tree.item(path, values=(name, status), tags=(tag,))
        except (tk.TclError, IndexError) as e:
            logging.getLogger(__name__).debug("Ошибка обновления статуса в treeview: %s", e)

        if not self._is_running:
            has_marked = any(b["status"] == "размечено" for b in self._books)
            self._synth_btn.configure(state="normal" if has_marked else "disabled")

    # =======================================
    #  ЛОГИРОВАНИЕ
    # =======================================

    def _log(self, message: str, level: str = "info"):
        """Thread-safe логирование (из рабочего потока)."""
        self._log_queue.put((message, level))

    def _log_immediate(self, message: str, level: str = "info"):
        """Прямая запись в лог из UI-потока (для ошибок до запуска worker)."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n", level)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _flush_log(self):
        """Вытаскивает сообщения из очереди и пишет в текстовый виджет."""
        batch = []
        try:
            while True:
                batch.append(self._log_queue.get_nowait())
        except queue.Empty:
            pass

        if batch:
            self.log_text.configure(state="normal")
            for msg, level in batch:
                self.log_text.insert("end", msg + "\n", level)
            self.log_text.configure(state="disabled")
            self.log_text.see("end")

        if self._is_running:
            self._flush_id = self.app.root.after(200, self._flush_log)

    # =======================================
    #  ЗАПУСК / ОСТАНОВКА
    # =======================================

    def _start(self):
        self._launch(test_mode=False)

    def _start_test(self):
        self._launch(test_mode=True)

    def _launch(self, test_mode: bool):
        pending = [b for b in self._books if b["status"] in ("ожидание", "ошибка")]
        if not pending:
            self._log_immediate(
                "Нет книг для обработки. Нажмите '+ Добавить .txt'.", "warning",
            )
            return

        config = get_config()
        ds_key = get_api_key("deepseek_api_key", config.get("deepseek_api_key", ""))
        ya_key = get_api_key("yandex_api_key", config.get("yandex_api_key", ""))
        ya_folder = get_api_key("yandex_folder_id", config.get("yandex_folder_id", ""))

        if not ds_key:
            self._log_immediate(
                "Не указан DeepSeek API-ключ! Перейдите в Настройки.", "error",
            )
            return
        if not ya_key or not ya_folder:
            self._log_immediate(
                "Не указаны Yandex API-ключ или Folder ID! Перейдите в Настройки.",
                "error",
            )
            return

        self._is_running = True
        self._stop_requested = False
        self._start_btn.configure(state="disabled")
        self._test_btn.configure(state="disabled")
        self._synth_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")

        if test_mode:
            self.status_label.configure(
                text="Тестовый режим (5 мин)...", bootstyle="warning",
            )
            self._log_immediate(
                "ТЕСТОВЫЙ РЕЖИМ: синтез первых ~5 минут аудио", "warning",
            )
        else:
            self.status_label.configure(text="Запуск...", bootstyle="info")
            self._log_immediate(
                f"Запуск обработки: {len(pending)} книг", "info",
            )

        # Запуск фонового потока
        self._worker_thread = threading.Thread(
            target=self._worker, args=(pending, test_mode), daemon=True,
        )
        self._worker_thread.start()

        # Запуск flush лога
        self._flush_id = self.app.root.after(200, self._flush_log)

    def _stop(self):
        self._stop_requested = True
        self._log("Остановка запрошена...", "warning")

    def _start_synth(self):
        """Запуск только синтеза для книг со статусом 'размечено'."""
        marked_books = [b for b in self._books if b["status"] == "размечено"]
        if not marked_books:
            self._log_immediate(
                "Нет размеченных книг для синтеза. Сначала запустите Старт.",
                "warning",
            )
            return

        config = get_config()
        ya_key = get_api_key("yandex_api_key", config.get("yandex_api_key", ""))
        ya_folder = get_api_key("yandex_folder_id", config.get("yandex_folder_id", ""))
        if not ya_key or not ya_folder:
            self._log_immediate(
                "Не указаны Yandex API-ключ или Folder ID! Перейдите в Настройки.",
                "error",
            )
            return

        self._is_running = True
        self._stop_requested = False
        self._start_btn.configure(state="disabled")
        self._test_btn.configure(state="disabled")
        self._synth_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")

        self.status_label.configure(text="Синтез...", bootstyle="info")
        self._log_immediate(
            f"Запуск синтеза: {len(marked_books)} книг", "info",
        )

        self._worker_thread = threading.Thread(
            target=self._worker_synth, args=(marked_books,), daemon=True,
        )
        self._worker_thread.start()
        self._flush_id = self.app.root.after(200, self._flush_log)

    def _on_finished(self):
        """Вызывается из UI-потока по завершении."""
        self._is_running = False
        self._start_btn.configure(state="normal")
        self._test_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")

        has_marked = any(b["status"] == "размечено" for b in self._books)
        self._synth_btn.configure(state="normal" if has_marked else "disabled")

        if self._flush_id:
            self.app.root.after_cancel(self._flush_id)
            self._flush_id = None

        # Финальный flush
        self._flush_log()

        done = sum(1 for b in self._books if b["status"] == "готово")
        marked = sum(1 for b in self._books if b["status"] == "размечено")
        total = len(self._books)
        if marked > 0:
            self.status_label.configure(
                text=f"Размечено: {marked}, готово: {done}/{total} — нажмите Синтез",
                bootstyle="warning",
            )
        else:
            self.status_label.configure(
                text=f"Завершено: {done}/{total} книг",
                bootstyle="success" if done == total else "warning",
            )

    def _on_hide(self):
        if self._flush_id:
            self.app.root.after_cancel(self._flush_id)
            self._flush_id = None

    # =======================================
    #  РАБОЧИЙ ПОТОК
    # =======================================

    # ~5 минут аудио ~ 6000 символов русского текста при скорости 1.0
    TEST_CHAR_LIMIT = 6000

    def _worker(self, books: list, test_mode: bool = False):
        """Фоновый поток обработки книг."""
        try:
            self._worker_inner(books, test_mode)
        except Exception as e:
            tb = traceback.format_exc()
            self._log(f"\nКРИТИЧЕСКАЯ ОШИБКА в рабочем потоке:", "error")
            self._log(str(e), "error")
            self._log(tb, "error")
        finally:
            self.app.root.after(0, self._on_finished)

    def _worker_inner(self, books: list, test_mode: bool):
        """Внутренняя логика обработки."""
        import time
        from src.core.text_cleaner import clean_and_split
        from src.core.preparer import markup_chapter
        from src.core.synthesizer import synthesize_chapter, YandexTTSConnection

        config = get_config()
        ds_key = get_api_key("deepseek_api_key", config.get("deepseek_api_key", ""))
        ds_model = config.get("deepseek_model", "deepseek-chat")
        ya_key = get_api_key("yandex_api_key", config.get("yandex_api_key", ""))
        ya_folder = get_api_key("yandex_folder_id", config.get("yandex_folder_id", ""))
        voice = config.get("voice", "kirill")
        speed = config.get("speed", 1.0)
        role = config.get("role", "neutral")
        pitch_shift = config.get("pitch_shift", 0.0)
        volume = config.get("volume", -19.0)

        self._log(f"Конфигурация: голос={voice}, скорость={speed}, роль={role}", "info")
        self._log(f"  тембр={pitch_shift} Гц, громкость={volume} LUFS", "info")
        self._log(f"  DeepSeek модель: {ds_model}", "info")

        total_books = len(books)
        # В тестовом режиме — только первая книга
        if test_mode:
            books = books[:1]
            total_books = 1

        for book_idx, book in enumerate(books):
            if self._stop_requested:
                self._log("Обработка остановлена пользователем.", "warning")
                break

            book_name = book["name"]
            book_path = book["path"]

            if test_mode:
                raw_dir = str(ROOT_DIR / "chapters" / book_name / "raw_test")
                marked_dir = str(ROOT_DIR / "chapters" / book_name / "marked_test")
                output_dir = str(ROOT_DIR / "output" / book_name)
                # Очистка старых тестовых файлов
                for d in (raw_dir, marked_dir):
                    if os.path.exists(d):
                        shutil.rmtree(d)
                        self._log(f"Очищена папка: {d}", "info")
                # Удаление старых тестовых MP3
                for old_mp3 in glob.glob(os.path.join(output_dir, "*_test.mp3")):
                    os.remove(old_mp3)
                    self._log(f"Удалён: {os.path.basename(old_mp3)}", "info")
            else:
                raw_dir = str(ROOT_DIR / "chapters" / book_name / "raw")
                marked_dir = str(ROOT_DIR / "chapters" / book_name / "marked")
                output_dir = str(ROOT_DIR / "output" / book_name)

            self._log(f"\n{'='*50}", "separator")
            mode_label = " [ТЕСТ]" if test_mode else ""
            self._log(
                f"Книга: {book_name}{mode_label} ({book_idx+1}/{total_books})",
                "chapter",
            )
            self._log(f"{'='*50}", "separator")
            self._log(f"Файл: {book_path}", "info")
            self._log(f"Raw:    {raw_dir}", "info")
            self._log(f"Marked: {marked_dir}", "info")
            self._log(f"Output: {output_dir}", "info")

            # -- Шаг 1: Очистка --
            self._log(f"\n── Шаг 1: Очистка текста ──", "header")
            self.app.root.after(0, self._update_book_status, book_path, "очистка")
            self._update_progress(book_idx, total_books, "Очистка")

            try:
                raw_files = clean_and_split(
                    book_path, raw_dir,
                    on_progress=self._log,
                )
                self._log(
                    f"Очистка завершена: {len(raw_files)} файлов создано",
                    "success",
                )
            except Exception as e:
                self._log(f"Ошибка очистки: {e}", "error")
                self._log(traceback.format_exc(), "error")
                self.app.root.after(
                    0, self._update_book_status, book_path, "ошибка",
                )
                continue

            if not raw_files:
                self._log("Не найдено глав после очистки!", "error")
                self.app.root.after(
                    0, self._update_book_status, book_path, "ошибка",
                )
                continue

            if self._stop_requested:
                break

            # В тестовом режиме: берём первый файл (начало книги)
            if test_mode and raw_files:
                test_file = raw_files[0]

                self._prepare_test_text(test_file, self.TEST_CHAR_LIMIT)
                raw_files = [test_file]
                self._log(
                    f"Тест: {os.path.basename(test_file)} "
                    f"(~{self.TEST_CHAR_LIMIT} символов, через DeepSeek)",
                    "warning",
                )

            # -- Шаг 2: Разметка DeepSeek --
            self._log(
                f"\n── Шаг 2: Разметка DeepSeek ({len(raw_files)} глав) ──",
                "header",
            )
            self.app.root.after(0, self._update_book_status, book_path, "разметка")

            markup_ok = True
            markup_count = 0
            for ch_idx, raw_file in enumerate(raw_files):
                if self._stop_requested:
                    break

                ch_name = os.path.basename(raw_file)
                marked_file = os.path.join(marked_dir, ch_name)

                # Пропуск уже размеченных
                if os.path.exists(marked_file):
                    self._log(f"  Пропуск: {ch_name} (уже размечен)")
                    continue

                self._log(
                    f"\n  Глава {ch_idx+1}/{len(raw_files)}: {ch_name}", "chapter",
                )
                self._update_progress(
                    book_idx, total_books,
                    f"Разметка: глава {ch_idx+1}/{len(raw_files)}",
                )

                try:
                    ok = markup_chapter(
                        raw_file, marked_file,
                        api_key=ds_key, model=ds_model,
                        on_progress=self._log,
                    )
                except Exception as e:
                    self._log(f"  Исключение при разметке: {e}", "error")
                    self._log(traceback.format_exc(), "error")
                    ok = False

                if ok:
                    markup_count += 1
                else:
                    markup_ok = False
                    self._log(f"  ОШИБКА разметки: {ch_name}", "error")

            if self._stop_requested:
                break

            self._log(
                f"Разметка завершена: {markup_count}/{len(raw_files)} глав",
                "success" if markup_ok else "warning",
            )

            if not markup_ok:
                self._log("Некоторые главы не удалось разметить!", "warning")

            # Сохраняем пути для последующего синтеза
            for b in self._books:
                if b["path"] == book_path:
                    b["marked_dir"] = marked_dir
                    b["output_dir"] = output_dir
                    break

            self.app.root.after(
                0, self._update_book_status, book_path, "размечено",
            )
            self._log(
                f"\n✅ Книга '{book_name}' размечена. "
                f"Проверьте файлы в {marked_dir}",
                "success",
            )
            self._log(
                "Для синтеза нажмите кнопку «Синтез».", "warning",
            )

        # Завершение
        self._update_progress(total_books - 1, total_books, "Разметка завершена", finished=True)
        self._log(f"\n{'='*50}", "separator")
        self._log("Разметка завершена. Проверьте результаты и запустите синтез.", "success")

    def _worker_synth(self, books: list):
        """Фоновый поток синтеза."""
        try:
            self._worker_synth_inner(books)
        except Exception as e:
            tb = traceback.format_exc()
            self._log(f"\nКРИТИЧЕСКАЯ ОШИБКА в потоке синтеза:", "error")
            self._log(str(e), "error")
            self._log(tb, "error")
        finally:
            self.app.root.after(0, self._on_finished)

    def _worker_synth_inner(self, books: list):
        """Синтез размеченных книг через Yandex SpeechKit."""
        import time
        from src.core.synthesizer import synthesize_chapter, YandexTTSConnection

        config = get_config()
        ya_key = get_api_key("yandex_api_key", config.get("yandex_api_key", ""))
        ya_folder = get_api_key("yandex_folder_id", config.get("yandex_folder_id", ""))
        voice = config.get("voice", "kirill")
        speed = config.get("speed", 1.0)
        role = config.get("role", "neutral")
        pitch_shift = config.get("pitch_shift", 0.0)
        volume = config.get("volume", -19.0)

        self._log(f"Конфигурация синтеза: голос={voice}, скорость={speed}, роль={role}", "info")
        self._log(f"  тембр={pitch_shift} Гц, громкость={volume} LUFS", "info")

        total_books = len(books)

        for book_idx, book in enumerate(books):
            if self._stop_requested:
                self._log("Синтез остановлен пользователем.", "warning")
                break

            book_name = book["name"]
            book_path = book["path"]
            marked_dir = book.get("marked_dir", str(ROOT_DIR / "chapters" / book_name / "marked"))
            output_dir = book.get("output_dir", str(ROOT_DIR / "output" / book_name))

            self._log(f"\n{'='*50}", "separator")
            self._log(
                f"Синтез: {book_name} ({book_idx+1}/{total_books})", "chapter",
            )
            self._log(f"{'='*50}", "separator")

            if os.path.exists(marked_dir):
                marked_files = sorted([
                    os.path.join(marked_dir, f)
                    for f in os.listdir(marked_dir) if f.endswith(".txt")
                ])
            else:
                marked_files = []
                self._log(f"Папка разметки не найдена: {marked_dir}", "error")

            if not marked_files:
                self._log("Нет размеченных файлов для синтеза!", "error")
                self.app.root.after(
                    0, self._update_book_status, book_path, "ошибка",
                )
                continue

            self._log(
                f"\n── Синтез Yandex SpeechKit ({len(marked_files)} глав) ──",
                "header",
            )
            self.app.root.after(0, self._update_book_status, book_path, "синтез")

            self._log("Подключение к Yandex SpeechKit gRPC...", "info")
            try:
                tts_conn = YandexTTSConnection(ya_key, ya_folder)
                self._log("gRPC подключение установлено", "success")
            except Exception as e:
                self._log(f"Ошибка подключения к Yandex: {e}", "error")
                self._log(traceback.format_exc(), "error")
                self.app.root.after(
                    0, self._update_book_status, book_path, "ошибка",
                )
                continue

            synth_ok = True
            synth_count = 0
            try:
                for ch_idx, marked_file in enumerate(marked_files):
                    if self._stop_requested:
                        break

                    mp3_name = Path(marked_file).stem
                    mp3_file = os.path.join(output_dir, mp3_name + ".mp3")

                    if os.path.exists(mp3_file) and os.path.getsize(mp3_file) > 100:
                        size_mb = os.path.getsize(mp3_file) / (1024 * 1024)
                        self._log(
                            f"  Пропуск: {mp3_name}.mp3 ({size_mb:.1f} MB, уже есть)",
                        )
                        continue

                    self._log(
                        f"\n  Глава {ch_idx+1}/{len(marked_files)}: {mp3_name}.mp3",
                        "chapter",
                    )

                    try:
                        with open(marked_file, "r", encoding="utf-8") as f:
                            text_len = len(f.read())
                        self._log(f"  Текст: {text_len:,} символов", "info")
                    except OSError as e:
                        self._log(f"  Не удалось прочитать размер текста: {e}", "warning")

                    self._update_progress(
                        book_idx, total_books,
                        f"Синтез: глава {ch_idx+1}/{len(marked_files)}",
                    )

                    try:
                        ok = synthesize_chapter(
                            marked_file, mp3_file,
                            voice=voice, speed=speed, role=role,
                            pitch_shift=pitch_shift, volume=volume,
                            on_progress=self._log,
                            connection=tts_conn,
                        )
                    except Exception as e:
                        self._log(f"  Исключение при синтезе: {e}", "error")
                        self._log(traceback.format_exc(), "error")
                        ok = False

                    if ok:
                        synth_count += 1
                    else:
                        synth_ok = False
                        self._log(f"  ОШИБКА синтеза: {mp3_name}", "error")

                    if ok and ch_idx < len(marked_files) - 1:
                        time.sleep(0.5)
            finally:
                tts_conn.close()
                self._log("gRPC подключение закрыто", "info")

            if self._stop_requested:
                break

            self._log(
                f"\nСинтез завершён: {synth_count}/{len(marked_files)} глав",
                "success" if synth_ok else "warning",
            )

            if synth_ok and synth_count > 0:
                self._log(f"Книга '{book_name}' готова!", "success")
                self.app.root.after(
                    0, self._update_book_status, book_path, "готово",
                )
            else:
                self._log(
                    f"Книга '{book_name}' завершена с ошибками", "warning",
                )
                self.app.root.after(
                    0, self._update_book_status, book_path, "ошибка",
                )

        self._update_progress(total_books - 1, total_books, "Готово", finished=True)
        self._log(f"\n{'='*50}", "separator")
        self._log("Синтез завершён.", "success")

    def _prepare_test_text(self, raw_file: str, char_limit: int):
        """Обрезает файл до char_limit символов по границе предложения.
        Сохраняет структуру: заголовок\\n\\nконтент."""
        with open(raw_file, "r", encoding="utf-8") as f:
            text = f.read()

        # Разделяем заголовок и контент (формат: "title\n\ncontent")
        parts = text.split('\n', 1)
        title_line = parts[0]
        content = parts[1].strip() if len(parts) > 1 else ""

        if len(content) <= char_limit:
            return

        # Ищем конец предложения в пределах лимита (только в контенте)
        cut = -1
        for sep in [". ", "! ", "? "]:
            idx = content.rfind(sep, 0, char_limit)
            if idx > cut:
                cut = idx

        if cut == -1:
            cut = char_limit

        content = content[:cut + 1].strip()

        with open(raw_file, "w", encoding="utf-8") as f:
            f.write(f"{title_line}\n\n{content}")

    def _update_progress(self, book_idx: int, total_books: int, step: str,
                         finished: bool = False):
        """Обновляет прогрессбар и статус (thread-safe)."""
        if finished:
            pct = 100
        else:
            pct = int(((book_idx) / total_books) * 100)
        text = f"Книга {book_idx+1}/{total_books} — {step}"

        def _update():
            self.progress_bar["value"] = pct
            self.status_label.configure(text=text, bootstyle="info")

        self.app.root.after(0, _update)
