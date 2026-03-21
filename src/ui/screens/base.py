import logging
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

logger = logging.getLogger(__name__)


class BaseScreen:
    """
    Базовый класс для всех экранов приложения.
    Ленивая инициализация + управление жизненным циклом.
    """

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.frame = ttk.Frame(self.parent)
        self._initialized = False

    def _create_ui(self):
        raise NotImplementedError(
            f"_create_ui должен быть реализован в {self.__class__.__name__}"
        )

    def _on_show(self, **kwargs):
        pass

    def _on_hide(self):
        pass

    def show(self, **kwargs):
        if not self._initialized:
            try:
                self._create_ui()
                self._initialized = True
            except Exception as e:
                self._create_error_ui(str(e))
                self._initialized = True

        self.frame.pack(fill=BOTH, expand=YES, padx=0, pady=0)

        try:
            self._on_show(**kwargs)
        except Exception as e:
            logger.warning("Ошибка в _on_show(%s): %s", self.__class__.__name__, e)

        self.frame.tkraise()
        self.frame.update_idletasks()

    def hide(self):
        if self._initialized:
            try:
                self._on_hide()
            except Exception as e:
                logger.warning("Ошибка в _on_hide(%s): %s", self.__class__.__name__, e)
            self.frame.pack_forget()

    def destroy(self):
        if self._initialized:
            self.hide()
            self.frame.destroy()
            self._initialized = False

    def refresh(self, **kwargs):
        if self._initialized:
            self.hide()
            self.show(**kwargs)

    def _create_error_ui(self, error_message):
        for widget in self.frame.winfo_children():
            widget.destroy()

        from src.ui.theme import FONT_FAMILY

        error_frame = ttk.Frame(self.frame)
        error_frame.pack(expand=True, fill=BOTH, padx=50, pady=50)

        ttk.Label(
            error_frame,
            text="Ошибка загрузки экрана",
            font=(FONT_FAMILY, 18, "bold"),
            bootstyle="danger",
        ).pack(pady=(0, 20))

        ttk.Label(
            error_frame,
            text=f"Класс: {self.__class__.__name__}",
            font=(FONT_FAMILY, 12),
            bootstyle="secondary",
        ).pack(pady=(0, 10))

        ttk.Label(
            error_frame,
            text=error_message,
            font=(FONT_FAMILY, 10),
            bootstyle="light",
            wraplength=600,
            justify="center",
        ).pack(pady=(0, 30))

    @staticmethod
    def _add_copy_menu(text_widget):
        """Контекстное меню копирования."""
        import ttkbootstrap as _ttk

        def _copy_sel():
            try:
                sel = text_widget.get("sel.first", "sel.last")
                root = text_widget.winfo_toplevel()
                root.clipboard_clear()
                root.clipboard_append(sel)
            except tk.TclError:
                pass  # Нет выделения — это нормально

        def _copy_all():
            content = text_widget.get("1.0", "end-1c")
            root = text_widget.winfo_toplevel()
            root.clipboard_clear()
            root.clipboard_append(content)

        def _show(event):
            m = _ttk.Menu(text_widget, tearoff=0)
            try:
                text_widget.get("sel.first", "sel.last")
                m.add_command(label="Копировать выделенное", command=_copy_sel)
            except tk.TclError:
                pass  # Нет выделения — пункт не добавляется
            m.add_command(label="Копировать всё", command=_copy_all)
            m.post(event.x_root, event.y_root)

        text_widget.bind("<Button-3>", _show)
