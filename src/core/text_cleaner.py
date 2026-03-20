"""
Voice Studio - Очистка текста (Шаг 1)
======================================
Читает .txt файл, очищает от мусора, разбивает на главы.

Модуль выполняет первый этап конвейера обработки текста:
- Чтение файлов с автоопределением кодировки
- Удаление артефактов форматирования (Markdown, HTML, спецсимволы)
- Нормализация пробелов и переносов строк
- Разбиение текста на главы по заголовкам
"""

import os
import re
from pathlib import Path
from typing import Callable, Optional


# Кодировки для автоопределения
_ENCODINGS: list[str] = ["utf-8", "utf-8-sig", "cp1251", "cp1252", "latin-1"]


def _read_file_any_encoding(path: str) -> tuple[str, str]:
    """Читает файл, пробуя разные кодировки.

    Перебирает список кодировок ``_ENCODINGS`` по порядку и возвращает
    содержимое файла при первой успешной попытке декодирования.

    Args:
        path: Абсолютный или относительный путь к текстовому файлу.

    Returns:
        Кортеж ``(текст, кодировка)`` -- содержимое файла и имя кодировки,
        которой удалось его прочитать.

    Raises:
        RuntimeError: Если ни одна из кодировок не подошла
            (на практике ``latin-1`` читает любой файл).
    """
    for enc in _ENCODINGS:
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            return text, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    # latin-1 уже в _ENCODINGS и читает всё — сюда не дойдёт
    raise RuntimeError(f"Не удалось прочитать файл: {path}")


def sanitize_filename(name: str) -> str:
    """Очищает имя файла от спецсимволов.

    Заменяет все символы, кроме букв (латиница и кириллица) и цифр,
    на символ подчёркивания. Множественные подчёркивания схлопываются
    в одно. Результат обрезается до 60 символов.

    Args:
        name: Исходная строка (например, заголовок главы).

    Returns:
        Очищенная строка, пригодная для использования в имени файла.
    """
    clean: str = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9]', '_', name)
    clean = re.sub(r'_+', '_', clean)
    return clean.strip('_')[:60]


def clean_text(text: str) -> str:
    """Очищает текст от мусора и артефактов форматирования.

    Выполняет следующие операции (порядок важен):
    - Удаление BOM-маркеров
    - Удаление номеров страниц (отдельная строка с числом)
    - Удаление сносок: ``[1]``, ``(1)``, ``[*]``, ``(*)``
    - Удаление блоков сносок внизу страницы
    - Замена неразрывных пробелов и zero-width символов
    - Нормализация переносов строк и табуляций
    - Удаление image-якорей ``{{img_N}}``
    - Удаление Markdown-разметки (bold, italic, заголовки, ссылки, код, цитаты)
    - Удаление HTML-тегов
    - Удаление непроизносимых символов для TTS
    - Нормализация пробелов и пустых строк

    Args:
        text: Исходный «сырой» текст.

    Returns:
        Очищенный текст, готовый к разбиению на главы.
    """
    # Удаление BOM
    text = text.lstrip('\ufeff')

    # Удаление номеров страниц (отдельная строка с числом)
    text = re.sub(r'(?m)^\s*\d{1,4}\s*$', '', text)

    # Удаление сносок: [1], [2], (1), (*), [*]
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\(\d+\)', '', text)
    text = re.sub(r'\[\*+\]', '', text)
    text = re.sub(r'\(\*+\)', '', text)

    # Удаление блоков сносок внизу (цифра + точка + текст, только после пустой строки)
    text = re.sub(r'(?m)(?<=\n\n)\d+\.\s+.{0,200}$', '', text)

    # Удаление неразрывных пробелов и спецсимволов
    text = text.replace('\xa0', ' ')
    text = text.replace('\u200b', '')  # zero-width space
    text = text.replace('\u200c', '')  # zero-width non-joiner
    text = text.replace('\u200d', '')  # zero-width joiner
    text = text.replace('\u00ad', '')  # soft hyphen
    text = text.replace('\u2028', '\n')  # line separator
    text = text.replace('\u2029', '\n\n')  # paragraph separator
    text = text.replace('\ufeff', '')  # BOM

    # Нормализация переносов строк
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Удаление табуляций -> пробелы
    text = text.replace('\t', ' ')

    # Image anchors из book-admin: {{img_N}}
    text = re.sub(r'\{\{img_?\d*\}\}', '', text)

    # Markdown bold/italic: **text** → text, *text* → text
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'(?<!\w)_{1,2}(.+?)_{1,2}(?!\w)', r'\1', text)

    # Markdown заголовки: # ## ### → текст
    text = re.sub(r'(?m)^#{1,6}\s+', '', text)

    # Markdown ссылки [text](url) → text
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)

    # Markdown code spans: `code` → code
    text = re.sub(r'`([^`]*)`', r'\1', text)

    # Markdown code blocks
    text = re.sub(r'```[a-z]*\n?', '', text).replace('```', '')

    # Markdown blockquotes: > text → text
    text = re.sub(r'(?m)^>\s?', '', text)

    # Markdown horizontal rules: ---, ***, ___
    text = re.sub(r'(?m)^[\-\*_]{3,}\s*$', '', text)

    # HTML-теги
    text = re.sub(r'<[^>]+>', '', text)

    # Символы, непроизносимые / мусорные для TTS
    for ch in ('~', '^', '|', '\\'):
        text = text.replace(ch, '')

    # Удаление множественных пробелов
    text = re.sub(r' {2,}', ' ', text)

    # Удаление пробелов в начале/конце строк
    text = re.sub(r'(?m)^[ ]+|[ ]+$', '', text)

    # Удаление множественных пустых строк (оставляем максимум 2)
    text = re.sub(r'\n{4,}', '\n\n\n', text)

    return text.strip()


# Паттерны для разбиения на главы/части
_CHAPTER_KEYWORDS: str = (
    r'Глава|Пролог|Эпилог|Часть|Предисловие|Послесловие|'
    r'Заключение|Введение|Вступление|От\s+автора|Примечания'
)
# Два формата: "Глава 1" и "1 Глава" / "15 глава"
_CHAPTER_PATTERN: re.Pattern[str] = re.compile(
    rf'(?m)^((?:(?:{_CHAPTER_KEYWORDS})\s*.+|\d+\s*(?:глава|часть).*))\s*$',
    re.IGNORECASE,
)

# Вступительные заголовки (обработка без AI)
_MANUAL_TITLES: set[str] = {
    "вступление", "введение", "предисловие", "от автора",
    "примечания", "послесловие",
}


def _strip_book_title(text: str) -> tuple[str, str]:
    """Убирает название книги из первой строки текста.

    Название определяется как первая непустая строка длиной менее 100
    символов, за которой следует пустая строка. Если строка совпадает
    с паттерном главы/части, она не считается названием.

    Args:
        text: Полный текст книги после очистки.

    Returns:
        Кортеж ``(название, оставшийся_текст)``. Если название не
        обнаружено, первый элемент -- пустая строка.
    """
    lines: list[str] = text.split('\n')
    first_nonempty: int = -1
    for i, line in enumerate(lines):
        if line.strip():
            first_nonempty = i
            break

    if first_nonempty == -1:
        return "", text

    title_line: str = lines[first_nonempty].strip()

    # Название: короткая строка, за которой пустая строка
    if len(title_line) > 100:
        return "", text

    # Проверяем что после названия есть пустая строка
    has_blank_after: bool = False
    for j in range(first_nonempty + 1, min(first_nonempty + 3, len(lines))):
        if not lines[j].strip():
            has_blank_after = True
            break

    if not has_blank_after:
        return "", text

    # Не считаем заголовком, если это уже глава/часть
    if _CHAPTER_PATTERN.match(title_line):
        return "", text

    # Убираем название из текста
    remaining: str = '\n'.join(lines[first_nonempty + 1:]).strip()
    return title_line, remaining


def split_into_chapters(
    text: str,
) -> tuple[list[tuple[str, str, str]], str]:
    """Разбивает текст на главы по заголовкам.

    Ищет паттерны вида «Глава N», «Пролог», «Часть N» и т.д.
    Текст до первой главы включается как отдельный сегмент.
    Вступительные разделы (Предисловие, Введение и пр.) помечаются
    для ручной обработки (без AI-разметки).

    Args:
        text: Очищенный текст книги целиком.

    Returns:
        Кортеж из двух элементов:
        - Список сегментов ``(заголовок, содержимое, режим)``, где
          ``режим`` равен ``"manual"`` для служебных разделов и ``"ai"``
          для глав, обрабатываемых через DeepSeek.
        - Название книги (пустая строка, если не найдено).
    """
    # Убираем название книги из первой строки
    book_title: str
    book_title, text = _strip_book_title(text)

    matches: list[re.Match[str]] = list(_CHAPTER_PATTERN.finditer(text))

    segments: list[tuple[str, str, str]] = []

    if matches:
        # Текст до первой главы/части
        intro_text: str = text[:matches[0].start()].strip()
        if intro_text and len(intro_text) > 20:
            # Используем название книги или просто "Начало"
            intro_title: str = book_title if book_title else "Начало"
            segments.append((intro_title, intro_text, "ai"))

        # Главы/части
        for i in range(len(matches)):
            title: str = matches[i].group(1).strip()
            start: int = matches[i].end()
            end: int = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content: str = text[start:end].strip()

            if not content:
                continue

            # Определяем режим обработки
            title_lower: str = title.lower().strip()
            # Убираем цифры/пунктуацию для сравнения
            title_base: str = re.sub(r'[\d.:,\s]+$', '', title_lower).strip()
            mode: str = "manual" if title_base in _MANUAL_TITLES else "ai"

            segments.append((title, content, mode))
    else:
        # Нет глав — весь текст как одна "глава"
        segments.append(("Книга", text, "ai"))

    return segments, book_title


def clean_and_split(
    txt_path: str,
    output_dir: str,
    on_progress: Optional[Callable[[str, str], None]] = None,
) -> list[str]:
    """Основная функция: очищает .txt и разбивает на главы.

    Выполняет полный цикл первого этапа конвейера:
    1. Чтение файла с автоопределением кодировки
    2. Очистка текста от артефактов
    3. Разбиение на главы/разделы
    4. Сохранение каждой главы в отдельный файл

    Args:
        txt_path: Путь к исходному ``.txt`` файлу.
        output_dir: Папка для сохранения глав
            (например, ``chapters/{book}/raw/``).
        on_progress: Необязательный callback ``(message, level)`` для
            логирования хода обработки. ``level`` принимает значения
            ``"info"``, ``"success"``, ``"error"``.

    Returns:
        Список абсолютных путей к созданным файлам глав.
        Пустой список, если разбиение не удалось.
    """
    def log(msg: str, level: str = "info") -> None:
        if on_progress:
            on_progress(msg, level)

    # Чтение файла (автоопределение кодировки)
    log(f"Чтение файла: {os.path.basename(txt_path)}")
    raw_text: str
    encoding: str
    raw_text, encoding = _read_file_any_encoding(txt_path)
    log(f"Кодировка: {encoding}, размер: {len(raw_text):,} символов")

    # Очистка
    log("Очистка текста от мусора...")
    cleaned: str = clean_text(raw_text)
    removed: int = len(raw_text) - len(cleaned)
    if removed > 0:
        log(f"Удалено {removed:,} символов мусора", "success")
    else:
        log("Мусор не найден", "info")

    # Разбиение на главы
    log("Разбиение на главы...")
    segments: list[tuple[str, str, str]]
    book_title: str
    segments, book_title = split_into_chapters(cleaned)

    if book_title:
        log(f"Название книги: \"{book_title}\" (убрано из текста)", "success")

    if not segments:
        log("Не удалось разбить на главы!", "error")
        return []

    # Логируем найденные главы
    for title, content, mode in segments:
        mode_label: str = "ручн." if mode == "manual" else "AI"
        log(f"  [{mode_label}] {title} ({len(content):,} симв.)")

    log(f"Найдено {len(segments)} глав/разделов", "success")

    # Сохранение
    os.makedirs(output_dir, exist_ok=True)
    created_files: list[str] = []

    for idx, (title, content, mode) in enumerate(segments):
        filename: str = f"{idx:03d}_{sanitize_filename(title)}.txt"
        filepath: str = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            # Заголовок главы в первой строке
            f.write(f"{title}\n\n{content}")

        created_files.append(filepath)

    log(f"Сохранено {len(created_files)} файлов в {output_dir}", "success")
    return created_files
