"""
Voice Studio - Синтез аудио через Yandex SpeechKit (Шаг 3)
============================================================
gRPC API v3, streaming MP3.
"""

import os
import re
import time
import grpc
import yandex.cloud.ai.tts.v3.tts_pb2 as tts_pb2
import yandex.cloud.ai.tts.v3.tts_service_pb2_grpc as tts_service_pb2_grpc


def _sanitize_for_tts(text: str) -> str:
    """Финальная очистка текста перед отправкой в Yandex SpeechKit.

    Удаляет всё, что Яндекс прочитает вслух как мусор,
    сохраняя валидную TTS-разметку: sil<[N]>, <[size]>, +ударения.
    """
    # HTML-теги
    text = re.sub(r'<(?![\[/])[^>]+>', '', text)

    # Markdown: **bold**, *italic*, __bold__, _italic_
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'(?<!\w)_{1,2}(.+?)_{1,2}(?!\w)', r'\1', text)

    # Markdown заголовки: # ## ### в начале строки
    text = re.sub(r'(?m)^#{1,6}\s+', '', text)

    # Markdown ссылки [text](url) → text
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)

    # Markdown code spans: `code` → code
    text = re.sub(r'`([^`]*)`', r'\1', text)

    # Markdown code blocks (```...```)
    text = re.sub(r'```[a-z]*\n?', '', text).replace('```', '')

    # Markdown blockquotes: > text → text
    text = re.sub(r'(?m)^>\s?', '', text)

    # Markdown horizontal rules: --- / *** / ___
    text = re.sub(r'(?m)^[\-\*_]{3,}\s*$', '', text)

    # Image anchors from book-admin: {{img_N}}
    text = re.sub(r'\{\{img_?\d*\}\}', '', text)

    # Оставшиеся одиночные * не входящие в TTS-разметку
    text = text.replace('*', '')

    # Фигурные/квадратные скобки-сироты (не часть TTS-разметки sil<[N]> / <[size]>)
    text = re.sub(r'(?<!<)\[(?!\d+\]>)(?!\w+\]>)', '', text)
    text = re.sub(r'(?<!\d)(?<!\w)\](?!>)', '', text)
    text = re.sub(r'(?<!sil<)(?<!<)\{', '', text)
    text = re.sub(r'(?<!\d)\}(?!>)', '', text)

    # Символы, которые Яндекс прочитает вслух
    text = text.replace('~', '')
    text = text.replace('^', '')
    text = text.replace('|', '')
    text = text.replace('\\', '')

    # Голые sil без <[N]>
    text = re.sub(r'sil(?!\s*<\[\d+\]>)', ' ', text)

    # Unicode мусор: soft hyphen, zero-width chars, BOM
    for ch in ('\u00ad', '\u200b', '\u200c', '\u200d', '\u2028', '\u2029', '\ufeff'):
        text = text.replace(ch, '')

    # Множественные пробелы → один
    text = re.sub(r' {2,}', ' ', text)

    # Пустые строки подряд → максимум одна
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def split_text_for_yandex(text: str, max_chars: int = 240) -> list[str]:
    """
    Разбивает текст на части по предложениям, макс ~240 символов каждая.

    Зачем: Yandex SpeechKit без unsafe_mode принимает макс 250 символов.
    Мы режем текст сами по границам предложений — так нет автоматической
    нарезки Яндексом, которая проглатывает окончания на стыках.

    sil<[N]> и <[size]> паузы остаются приклеены к окружающему тексту,
    никогда не отправляются отдельным куском.
    """
    import re

    if len(text) <= max_chars:
        return [text]

    # Разбиваем по границам предложений: . ! ? за которыми идёт пробел
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    parts = []
    current = ""

    for sent in sentences:
        # Если одно предложение длиннее лимита — отправим с unsafe_mode
        if len(sent) > max_chars:
            if current:
                parts.append(current.strip())
                current = ""
            parts.append(sent)
            continue

        if current and len(current) + 1 + len(sent) > max_chars:
            parts.append(current.strip())
            current = sent
        else:
            current = current + " " + sent if current else sent

    if current:
        parts.append(current.strip())

    # Защита: если кусок — только sil/пауза без текста, приклеиваем к соседу
    cleaned = []
    sil_pattern = re.compile(r'^(sil<\[\d+\]>\s*)+$')
    for part in parts:
        if sil_pattern.match(part):
            # Приклеиваем к предыдущему или следующему
            if cleaned:
                cleaned[-1] = cleaned[-1] + " " + part
            # Иначе останется для следующего цикла — см. ниже
        else:
            cleaned.append(part)

    return cleaned if cleaned else [text]


class YandexTTSConnection:
    """
    Переиспользуемое gRPC-подключение к Yandex SpeechKit.
    Создаётся один раз на всю книгу, как в оригинальном скрипте.
    """

    def __init__(self, api_key: str, folder_id: str):
        self.cred = grpc.ssl_channel_credentials()
        self.channel = grpc.secure_channel('tts.api.cloud.yandex.net:443', self.cred)
        self.stub = tts_service_pb2_grpc.SynthesizerStub(self.channel)
        self.metadata = (
            ('authorization', f'Api-Key {api_key}'),
            ('x-folder-id', folder_id),
        )

    def close(self):
        try:
            self.channel.close()
        except Exception:
            pass


def synthesize_chapter(
    marked_path: str,
    mp3_path: str,
    voice: str = "kirill",
    speed: float = 1.0,
    role: str = "neutral",
    pitch_shift: float = 0.0,
    volume: float = -19.0,
    on_progress=None,
    connection: YandexTTSConnection = None,
    api_key: str = None,
    folder_id: str = None,
) -> bool:
    """
    Синтезирует один текстовый файл в MP3.

    Args:
        marked_path: путь к размеченному тексту
        mp3_path: путь для MP3 файла
        voice: ID голоса
        speed: скорость речи
        role: роль/эмоция голоса
        pitch_shift: смещение тембра (-1000..+1000 Гц)
        volume: громкость LUFS (-149..0), по умолчанию -19
        on_progress: callback(message, level)
        connection: переиспользуемое gRPC-подключение (предпочтительно)
        api_key: Yandex API key (если нет connection — создаст своё)
        folder_id: Yandex folder ID (если нет connection)

    Returns:
        True при успехе.
    """
    def log(msg, level="info"):
        if on_progress:
            on_progress(msg, level)

    with open(marked_path, "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    if not full_text:
        log("Пустой файл, пропуск", "warning")
        return True

    full_text = _sanitize_for_tts(full_text)

    text_parts = split_text_for_yandex(full_text)
    log(f"Синтез: {len(text_parts)} частей, {len(full_text):,} символов")

    # Используем переданное подключение или создаём одноразовое
    own_connection = False
    if connection is None:
        if not api_key or not folder_id:
            log("Не указаны API-ключ или Folder ID", "error")
            return False
        connection = YandexTTSConnection(api_key, folder_id)
        own_connection = True

    try:
        os.makedirs(os.path.dirname(mp3_path), exist_ok=True)

        with open(mp3_path, 'wb') as f_out:
            for i, part in enumerate(text_parts):
                # unsafe_mode только если кусок > 250 символов (длинное предложение)
                use_unsafe = len(part) > 250

                request = tts_pb2.UtteranceSynthesisRequest(
                    text=part,
                    output_audio_spec=tts_pb2.AudioFormatOptions(
                        container_audio=tts_pb2.ContainerAudio(
                            container_audio_type=tts_pb2.ContainerAudio.MP3,
                        )
                    ),
                    hints=[
                        tts_pb2.Hints(voice=voice),
                        tts_pb2.Hints(speed=speed),
                        tts_pb2.Hints(role=role),
                        tts_pb2.Hints(pitch_shift=int(pitch_shift)),
                        tts_pb2.Hints(volume=volume),
                    ],
                    loudness_normalization_type=tts_pb2.UtteranceSynthesisRequest.LUFS,
                    unsafe_mode=use_unsafe,
                )

                for response in connection.stub.UtteranceSynthesis(
                    request, metadata=connection.metadata,
                ):
                    f_out.write(response.audio_chunk.data)

                if len(text_parts) > 1:
                    time.sleep(0.15)

        # Размер файла
        size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
        log(f"MP3: {size_mb:.1f} MB", "success")
        return True

    except Exception as e:
        log(f"Ошибка синтеза: {e}", "error")
        # Удаляем битый файл
        if os.path.exists(mp3_path):
            try:
                os.remove(mp3_path)
            except Exception:
                pass
        return False

    finally:
        if own_connection:
            connection.close()
