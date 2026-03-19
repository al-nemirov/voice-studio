"""
Voice Studio - Очистка текста (Шаг 1)
======================================
Читает .txt файл, очищает от мусора, разбивает на главы.
"""

import os
import re
from pathlib import Path


# Кодировки для автоопределения
_ENCODINGS = ["utf-8", "utf-8-sig", "cp1251", "cp1252", "latin-1"]


def _read_file_any_encoding(path: str) -> tuple[str, str]:
    """Читает файл, пробуя разные кодировки. Возвращает (текст, кодировка)."""
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
    """Очищает имя файла от спецсимволов."""
    clean = re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9]', '_', name)
    clean = re.sub(r'_+', '_', clean)
    return clean.strip('_')[:60]


def clean_text(text: str) -> str:
    """Очищает текст от мусора."""
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
_CHAPTER_KEYWORDS = (
    r'Глава|Пролог|Эпилог|Часть|Предисловие|Послесловие|'
    r'Заключение|Введение|Вступление|От\s+автора|Примечания'
)
# Два формата: "Глава 1" и "1 Глава" / "15 глава"
_CHAPTER_PATTERN = re.compile(
    rf'(?m)^((?:(?:{_CHAPTER_KEYWORDS})\s*.+|\d+\s*(?:глава|часть).*))\s*$',
    re.IGNORECASE,
)

# Вступительные заголовки (обработка без AI)
_MANUAL_TITLES = {
    "вступление", "введение", "предисловие", "от автора",
    "примечания", "послесловие",
}


def _strip_book_title(text: str) -> tuple[str, str]:
    """
    Убирает название книги из первой строки текста.
    Название = первая непустая строка, если она короткая (<100 символов)
    и за ней идёт пустая строка.

    Returns:
        (название, оставшийся текст)
    """
    lines = text.split('\n')
    first_nonempty = -1
    for i, line in enumerate(lines):
        if line.strip():
            first_nonempty = i
            break

    if first_nonempty == -1:
        return "", text

    title_line = lines[first_nonempty].strip()

    # Название: короткая строка, за которой пустая строка
    if len(title_line) > 100:
        return "", text

    # Проверяем что после названия есть пустая строка
    has_blank_after = False
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
    remaining = '\n'.join(lines[first_nonempty + 1:]).strip()
    return title_line, remaining


def split_into_chapters(text: str) -> tuple[list[tuple[str, str, str]], str]:
    """
    Разбивает текст на главы.

    Returns:
        list of (title, content, mode):
            mode="manual" для вступительных/служебных разделов (без AI)
            mode="ai" для глав (через DeepSeek)
    """
    # Убираем название книги из первой строки
    book_title, text = _strip_book_title(text)

    matches = list(_CHAPTER_PATTERN.finditer(text))

    segments = []

    if matches:
        # Текст до первой главы/части
        intro_text = text[:matches[0].start()].strip()
        if intro_text and len(intro_text) > 20:
            # Используем название книги или просто "Начало"
            intro_title = book_title if book_title else "Начало"
            segments.append((intro_title, intro_text, "ai"))

        # Главы/части
        for i in range(len(matches)):
            title = matches[i].group(1).strip()
            start = matches[i].end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            if not content:
                continue

            # Определяем режим обработки
            title_lower = title.lower().strip()
            # Убираем цифры/пунктуацию для сравнения
            title_base = re.sub(r'[\d.:,\s]+$', '', title_lower).strip()
            mode = "manual" if title_base in _MANUAL_TITLES else "ai"

            segments.append((title, content, mode))
    else:
        # Нет глав — весь текст как одна "глава"
        segments.append(("Книга", text, "ai"))

    return segments, book_title


def clean_and_split(
    txt_path: str,
    output_dir: str,
    on_progress=None,
) -> list[str]:
    """
    Основная функция: очищает .txt и разбивает на главы.

    Args:
        txt_path: путь к .txt файлу
        output_dir: папка для сохранения глав (chapters/{book}/raw/)
        on_progress: callback(message, level) для логирования

    Returns:
        Список путей к созданным файлам глав.
    """
    def log(msg, level="info"):
        if on_progress:
            on_progress(msg, level)

    # Чтение файла (автоопределение кодировки)
    log(f"Чтение файла: {os.path.basename(txt_path)}")
    raw_text, encoding = _read_file_any_encoding(txt_path)
    log(f"Кодировка: {encoding}, размер: {len(raw_text):,} символов")

    # Очистка
    log("Очистка текста от мусора...")
    cleaned = clean_text(raw_text)
    removed = len(raw_text) - len(cleaned)
    if removed > 0:
        log(f"Удалено {removed:,} символов мусора", "success")
    else:
        log("Мусор не найден", "info")

    # Разбиение на главы
    log("Разбиение на главы...")
    segments, book_title = split_into_chapters(cleaned)

    if book_title:
        log(f"Название книги: \"{book_title}\" (убрано из текста)", "success")

    if not segments:
        log("Не удалось разбить на главы!", "error")
        return []

    # Логируем найденные главы
    for title, content, mode in segments:
        mode_label = "ручн." if mode == "manual" else "AI"
        log(f"  [{mode_label}] {title} ({len(content):,} симв.)")

    log(f"Найдено {len(segments)} глав/разделов", "success")

    # Сохранение
    os.makedirs(output_dir, exist_ok=True)
    created_files = []

    for idx, (title, content, mode) in enumerate(segments):
        filename = f"{idx:03d}_{sanitize_filename(title)}.txt"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            # Заголовок главы в первой строке
            f.write(f"{title}\n\n{content}")

        created_files.append(filepath)

    log(f"Сохранено {len(created_files)} файлов в {output_dir}", "success")
    return created_files
