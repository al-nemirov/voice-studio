"""
Voice Studio - TTS-разметка через DeepSeek (Шаг 2)
====================================================
Добавляет ударения, паузы и акценты для Yandex SpeechKit.
"""

import logging
import os
import re
import time
from openai import OpenAI, APITimeoutError, APIConnectionError
from src.core.text_cleaner import _MANUAL_TITLES, clean_text

logger = logging.getLogger(__name__)

# Настройки retry
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2  # секунды, экспоненциально: 2, 4, 8


SYSTEM_PROMPT = """Ты — эксперт по TTS-разметке для Yandex SpeechKit.

ПРАВИЛА УДАРЕНИЙ (символ + перед ударной гласной):
- Ставь ТОЛЬКО в омографах, где без ударения смысл меняется:
  з+амок/зам+ок, м+ука/мук+а, ст+оит/сто+ит, п+отом/пот+ом, +уже/уж+е, б+ольшая/больш+ая
- Максимум 3-5 ударений на абзац. Если сомневаешься — НЕ СТАВЬ.
- В обычных словах (дом, кошка, бежать, пошёл, сказал, стоит) ударение НЕ НУЖНО.
- Yandex SpeechKit и так правильно произносит 95% слов. Помогай только там, где он ошибётся.

ПАУЗЫ:
- sil<[400]> — между абзацами
- sil<[800]> — смена сцены
- sil<[1500]> — переход между частями
- <[small]>, <[medium]>, <[large]> — интонационные паузы внутри предложения
- Между обычными предложениями паузы НЕ нужны — синтезатор справляется сам.
- ЗАПИСЬ ПАУЗЫ: ТОЛЬКО sil<[число]> с квадратными скобками. Голое слово sil ЗАПРЕЩЕНО.

ЗАПРЕТЫ:
- НЕ менять текст
- НЕ писать комментариев
- НЕ использовать *, **, _, `, #, код-блоки
- НЕ ставить ударения в каждом слове — это ГЛАВНЫЙ ЗАПРЕТ
- НЕ писать голое sil — только sil<[число]>

Верни ТОЛЬКО размеченный текст."""


def _clean_response(text: str) -> str:
    """Убирает markdown-артефакты и мусор из ответа AI.

    Сохраняет только чистый текст + валидную TTS-разметку:
    sil<[N]>, <[size]>, +ударения.
    """
    # Удаление код-блоков
    text = re.sub(r'```[a-z]*\n?', '', text).replace('```', '')

    # Удаление вступительных/заключительных фраз AI
    text = re.sub(
        r'^(Понял|Конечно|Вот|Хорошо|Предоставляю|Привет|Текст|Размеченный|'
        r'Готово|Результат|Ниже|Пожалуйста|Далее|Выполнено|Сделано|Разметка).*?\n',
        '', text, flags=re.IGNORECASE,
    )
    text = re.sub(
        r'\n\s*(Примечани[ея]|Замечани[ея]|Комментари[ий]|Обратите внимание|'
        r'Надеюсь|Если есть|Если нужн|Готово|P\.?S\.?).*$',
        '', text, flags=re.IGNORECASE | re.DOTALL,
    )

    # Markdown bold/italic: **text**, *text*, __text__, _text_
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'(?<!\w)_{1,2}(.+?)_{1,2}(?!\w)', r'\1', text)
    text = text.replace('*', '')

    # Markdown заголовки: # ## ###
    text = re.sub(r'(?m)^#{1,6}\s+', '', text)

    # Backtick code spans
    text = re.sub(r'`([^`]*)`', r'\1', text)

    # Markdown ссылки [text](url) → text
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)

    # HTML-теги (но не TTS-разметку <[size]>)
    text = re.sub(r'<(?![\[/])[^>]+>', '', text)

    # Голые sil без <[N]> — Яндекс прочитает "сил" вслух
    # Ловим: sil в конце строки, sil перед буквой, sil перед пробелом, sil<> без скобок
    text = re.sub(r'sil(?!\s*<\[\d+\]>)', ' ', text)

    # Убираем паузы ВНУТРИ слов (без пробелов вокруг = внутри слова)
    text = re.sub(r'(\w)sil<\[\d+\]>(\w)', r'\1\2', text)
    text = re.sub(r'(\w)<\[\w+\]>(\w)', r'\1\2', text)

    # Гарантируем пробел перед sil<
    text = re.sub(r'(\S)(sil<)', r'\1 \2', text)

    # Защита от переизбытка ударений: если AI поставил + на >15% слов,
    # убираем все ударения кроме известных омографов
    text = _guard_excessive_stresses(text)

    # Множественные пробелы
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


_KNOWN_HOMOGRAPHS = {
    "замок", "замка", "замку", "замком", "замке",
    "мука", "муки", "муку", "мукой", "муке",
    "стоит", "стоят", "стоишь", "стоим",
    "атлас", "атласа", "атласу", "атласом",
    "парить", "парит", "парят",
    "потом", "уже",
    "дорога", "дорогой", "дороги", "дорогу",
    "большая", "большой", "большие",
    "кружки", "кружек", "кружку",
    "белки", "белок", "белку",
    "вина", "вины", "вину", "виной",
    "забыли", "забыла", "забыл",
    "стрелки", "стрелок", "стрелку",
    "село", "села", "полы", "пола",
    "орган", "органа", "хлопок", "хлопка",
    "ирис", "ириса", "духи", "духов",
    "пары", "пар", "видение",
    "проклятый", "проклятая", "проклятые",
    "ношу", "косой", "косая", "трусы",
    "писать", "пишу", "плачу",
}


def _guard_excessive_stresses(text: str) -> str:
    """Если ударений слишком много (>15% слов), убираем все кроме омографов."""
    words = re.findall(r'[а-яёА-ЯЁ+]+', text)
    if not words:
        return text

    stressed = sum(1 for w in words if '+' in w)
    ratio = stressed / len(words) if words else 0

    if ratio <= 0.15:
        return text

    def _keep_stress(m):
        full = m.group(0)
        bare = full.replace('+', '').lower()
        if bare in _KNOWN_HOMOGRAPHS:
            return full
        return full.replace('+', '')

    return re.sub(r'[а-яёА-ЯЁ]*\+[а-яёА-ЯЁ+]*', _keep_stress, text)


def _process_intro_manual(intro_text: str) -> str:
    """Обрабатывает вступление без AI — только паузы."""
    lines = intro_text.split('\n')
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        result.append(f"{stripped} sil<[2000]>")
    return "\n\n".join(result)


def markup_chapter(
    raw_path: str,
    marked_path: str,
    api_key: str,
    model: str = "deepseek-chat",
    on_progress=None,
) -> bool:
    """
    Размечает одну главу через DeepSeek API.

    Args:
        raw_path: путь к очищенному тексту главы
        marked_path: путь для сохранения размеченного текста
        api_key: ключ DeepSeek API
        model: модель DeepSeek
        on_progress: callback(message, level)

    Returns:
        True при успехе, False при ошибке.
    """
    def log(msg, level="info"):
        if on_progress:
            on_progress(msg, level)

    with open(raw_path, "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    if not full_text:
        log("Пустой файл, пропуск", "warning")
        return True

    # Разделяем заголовок и контент
    lines = full_text.split('\n', 1)
    title = lines[0].strip()
    content = lines[1].strip() if len(lines) > 1 else ""

    if not content:
        _save(marked_path, title)
        return True

    # Предочистка контента перед AI — убираем markdown, HTML, якоря,
    # спецсимволы, чтобы AI работал с чистым текстом
    content = clean_text(content)

    # Определяем тип заголовка
    title_lower = title.lower().strip()
    is_intro = title_lower in _MANUAL_TITLES

    # Любой заголовок (глава, название книги, автор) — озвучиваем с паузой
    final_text = f"{title} sil<[2000]>\n\n"

    if is_intro:
        log("Ручная обработка вступления (без AI)")
        final_text += _process_intro_manual(content)
        _save(marked_path, final_text.strip())
        log("Вступление размечено", "success")
        return True

    # Обработка через DeepSeek
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=120)

    paragraphs = [p for p in content.split('\n') if p.strip()]
    current_chunk = ""
    chunk_count = 0
    total_chunks = _estimate_chunks(content)

    try:
        for p in paragraphs:
            if len(current_chunk) + len(p) > 4000:
                chunk_count += 1
                log(f"  AI порция {chunk_count}/{total_chunks}...")
                result = _call_deepseek(client, model, current_chunk, log)
                final_text += result + "\n\n"
                current_chunk = p
                time.sleep(2)
            else:
                current_chunk += "\n" + p if current_chunk else p

        if current_chunk:
            chunk_count += 1
            log(f"  AI порция {chunk_count}/{total_chunks}...")
            result = _call_deepseek(client, model, current_chunk, log)
            final_text += result + "\n"

        _save(marked_path, final_text.strip())
        log(f"Глава размечена ({chunk_count} порций)", "success")
        return True

    except Exception as e:
        log(f"Ошибка разметки: {e}", "error")
        return False


def _call_deepseek(client: OpenAI, model: str, text: str, log=None) -> str:
    """Вызов DeepSeek API для разметки текста с retry и таймаутом."""
    if not text.strip():
        return ""

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Разметь этот текст:\n\n{text}"},
                ],
                temperature=0.2,
                max_tokens=8000,
                timeout=120,
            )
            result = response.choices[0].message.content
            result = _clean_response(result)
            result = _verify_text_integrity(text, result, log)
            return result
        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            delay = _RETRY_BASE_DELAY * (2 ** attempt)
            if log:
                log(f"  DeepSeek API таймаут/сеть (попытка {attempt + 1}/{_MAX_RETRIES}), "
                    f"повтор через {delay}с: {e}", "warning")
            logger.warning("DeepSeek retry %d/%d: %s", attempt + 1, _MAX_RETRIES, e)
            time.sleep(delay)
        except Exception as e:
            if log:
                log(f"  DeepSeek API ошибка: {e}", "error")
            logger.error("DeepSeek API ошибка: %s", e)
            return text

    if log:
        log(f"  DeepSeek API: все {_MAX_RETRIES} попытки исчерпаны, "
            f"возврат оригинала: {last_error}", "error")
    return text


def _strip_tts_markup(text: str) -> str:
    """Убирает всю TTS-разметку, оставляя голый текст."""
    t = re.sub(r'sil<\[\d+\]>', ' ', text)
    t = re.sub(r'<\[\w+\]>', ' ', t)
    t = t.replace('+', '')
    t = re.sub(r' {2,}', ' ', t)
    return t.strip()


def _verify_text_integrity(original: str, marked: str, log=None) -> str:
    """Пословно проверяет, что AI не изменил текст — только добавил разметку.

    Если AI подменил слово (стоял→стоил), восстанавливает оригинал.
    Возвращает исправленный размеченный текст.
    """
    orig_bare = _strip_tts_markup(original)
    mark_bare = _strip_tts_markup(marked)

    if orig_bare == mark_bare:
        return marked

    orig_words = orig_bare.split()
    mark_words = mark_bare.split()

    if not orig_words or not mark_words:
        return marked

    if len(orig_words) != len(mark_words):
        mismatches = abs(len(orig_words) - len(mark_words))
        if mismatches > max(3, len(orig_words) * 0.1):
            if log:
                log(f"  ⚠️ AI изменил структуру текста ({len(orig_words)}→{len(mark_words)} слов), откат к оригиналу", "warning")
            return original
        return marked

    corrupted = []
    for i, (ow, mw) in enumerate(zip(orig_words, mark_words)):
        if ow.lower() != mw.lower():
            corrupted.append((i, ow, mw))

    if not corrupted:
        return marked

    if log:
        examples = corrupted[:5]
        ex_str = ", ".join(f"{mw}→{ow}" for _, ow, mw in examples)
        log(f"  ⚠️ AI исказил {len(corrupted)} слов, восстанавливаю: {ex_str}", "warning")

    marked_tokens = _tokenize_with_markup(marked)
    orig_idx = 0
    fixed_tokens = []

    for tok in marked_tokens:
        if tok["type"] == "markup":
            fixed_tokens.append(tok["raw"])
            continue

        bare = tok["raw"].replace('+', '')
        bare_lower = bare.lower()

        if orig_idx < len(orig_words):
            if bare_lower != orig_words[orig_idx].lower():
                stress_pos = tok["raw"].find('+')
                orig_word = orig_words[orig_idx]
                if stress_pos >= 0 and stress_pos < len(orig_word):
                    orig_word = orig_word[:stress_pos] + '+' + orig_word[stress_pos:]
                fixed_tokens.append(orig_word)
            else:
                fixed_tokens.append(tok["raw"])
            orig_idx += 1
        else:
            fixed_tokens.append(tok["raw"])

    return " ".join(fixed_tokens)


def _tokenize_with_markup(text: str) -> list:
    """Разбивает текст на токены, сохраняя TTS-разметку отдельно."""
    tokens = []
    pattern = re.compile(r'(sil<\[\d+\]>|<\[\w+\]>)')
    parts = pattern.split(text)

    for part in parts:
        if pattern.match(part):
            tokens.append({"type": "markup", "raw": part})
        else:
            for word in part.split():
                if word:
                    tokens.append({"type": "word", "raw": word})

    return tokens


def _estimate_chunks(text: str) -> int:
    """Оценивает количество чанков."""
    total = 0
    current = 0
    for p in text.split('\n'):
        if p.strip():
            add = len(p) + (1 if current > 0 else 0)  # +1 для \n
            if current + add > 4000:
                total += 1
                current = len(p)
            else:
                current += add
    if current > 0:
        total += 1
    return max(total, 1)


def _save(path: str, text: str):
    """Сохраняет текст в файл."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
