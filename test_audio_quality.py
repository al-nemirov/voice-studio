"""
Тест качества TTS: создаёт несколько аудио-сэмплов с разной разметкой,
затем прогоняет STT (распознавание) и сравнивает с оригиналом.
"""
import os
import sys
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.utils.config import get_config
from src.core.synthesizer import YandexTTSConnection, split_text_for_yandex
import grpc
import yandex.cloud.ai.tts.v3.tts_pb2 as tts_pb2
import yandex.cloud.ai.tts.v3.tts_service_pb2_grpc as tts_service_pb2_grpc

OUTPUT_DIR = ROOT / "test_samples"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Тестовые тексты с разной разметкой ──

SAMPLES = {
    "01_plain": {
        "desc": "Без разметки (чистый текст)",
        "text": (
            "От окружающего тебя мира, ты желаешь получать уважение и похвалу. "
            "Ждешь то, чего сам этому миру дать не в силах. "
            "Поэтому в основном, твои мнимые ожидания, не заслуженные. "
            "Ведь ты ни ценишь то, что существует и живёт лишь для тебя."
        ),
    },
    "02_stress": {
        "desc": "С ударениями (+)",
        "text": (
            "От окружающего тебя м+ира, ты желаешь получать уваж+ение и похвал+у. "
            "Ждешь то, чего сам +этому м+иру дать не в с+илах. "
            "Поэтому в основн+ом, твои мн+имые ожид+ания, не заслуженные. "
            "Ведь ты ни цен+ишь то, что существует и живёт лишь для теб+я."
        ),
    },
    "03_pauses": {
        "desc": "С паузами (sil<> и <[]>)",
        "text": (
            "От окружающего тебя мира, ты желаешь получать уважение и похвалу. "
            "sil<[400]> "
            "Ждешь то, чего сам этому миру дать не в силах. "
            "Поэтому в основном, <[medium]> твои мнимые ожидания, не заслуженные. "
            "sil<[400]> "
            "Ведь ты ни ценишь то, что существует и живёт лишь для тебя."
        ),
    },
    "04_stress_pauses": {
        "desc": "Ударения + паузы (полная разметка)",
        "text": (
            "От окружающего тебя м+ира, ты желаешь получать уваж+ение и похвал+у. "
            "sil<[400]> "
            "Ждешь то, чего сам +этому м+иру дать не в с+илах. "
            "Поэтому в основн+ом, <[medium]> твои мн+имые ожид+ания, не заслуженные. "
            "sil<[400]> "
            "Ведь ты ни цен+ишь то, что существует и живёт лишь для теб+я."
        ),
    },
    "05_emphasis": {
        "desc": "С акцентами (**) — проверяем поддержку",
        "text": (
            "От окружающего тебя мира, ты желаешь получать **уважение** и **похвалу**. "
            "Ждешь то, чего сам этому миру дать не в силах. "
            "Поэтому в основном, твои **мнимые** ожидания, не заслуженные. "
            "Ведь ты ни ценишь то, что существует и живёт лишь для тебя."
        ),
    },
    "06_full_markup": {
        "desc": "Полная разметка: ударения + паузы + акценты",
        "text": (
            "От окружающего тебя м+ира, ты желаешь получать **уваж+ение** и **похвал+у**. "
            "sil<[400]> "
            "Ждешь то, чего сам +этому м+иру дать не в с+илах. "
            "Поэтому в основн+ом, <[medium]> твои **мн+имые** ожид+ания, не заслуженные. "
            "sil<[400]> "
            "Ведь ты ни цен+ишь то, что существует и живёт лишь для теб+я."
        ),
    },
}


def synthesize_sample(conn, text, mp3_path, voice, speed, role, pitch_shift, volume):
    """Синтезирует один сэмпл."""
    os.makedirs(os.path.dirname(mp3_path), exist_ok=True)

    with open(mp3_path, 'wb') as f_out:
        request = tts_pb2.UtteranceSynthesisRequest(
            text=text,
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
            unsafe_mode=True,
        )

        for response in conn.stub.UtteranceSynthesis(
            request, metadata=conn.metadata,
        ):
            f_out.write(response.audio_chunk.data)

    size_kb = os.path.getsize(mp3_path) / 1024
    return size_kb


def recognize_audio(api_key, folder_id, mp3_path):
    """Распознаёт аудио через Yandex STT (REST API v1)."""
    import requests

    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    params = {
        "lang": "ru-RU",
        "folderId": folder_id,
    }
    headers = {
        "Authorization": f"Api-Key {api_key}",
    }

    with open(mp3_path, "rb") as f:
        data = f.read()

    max_retries = 3
    retry_base_delay = 2
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, params=params, headers=headers, data=data, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("result", "")
            elif resp.status_code >= 500:
                last_error = f"STT {resp.status_code}: {resp.text[:200]}"
                delay = retry_base_delay * (2 ** attempt)
                print(f"    STT сервер ошибка (попытка {attempt + 1}/{max_retries}), повтор через {delay}с")
                time.sleep(delay)
                continue
            else:
                return f"[ОШИБКА STT {resp.status_code}: {resp.text[:200]}]"
        except requests.exceptions.Timeout:
            last_error = "таймаут"
            delay = retry_base_delay * (2 ** attempt)
            print(f"    STT таймаут (попытка {attempt + 1}/{max_retries}), повтор через {delay}с")
            time.sleep(delay)
        except requests.exceptions.ConnectionError as e:
            last_error = str(e)
            delay = retry_base_delay * (2 ** attempt)
            print(f"    STT ошибка соединения (попытка {attempt + 1}/{max_retries}), повтор через {delay}с")
            time.sleep(delay)
    return f"[ОШИБКА STT: {last_error}]"


def main():
    config = get_config()
    ya_key = config.get("yandex_api_key", "")
    ya_folder = config.get("yandex_folder_id", "")
    voice = config.get("voice", "kirill")
    speed = config.get("speed", 1.0)
    role = config.get("role", "neutral")
    pitch_shift = config.get("pitch_shift", 0.0)
    volume = config.get("volume", -19.0)

    if not ya_key or not ya_folder:
        print("ОШИБКА: Не заданы yandex_api_key / yandex_folder_id в config.json")
        return

    print(f"Голос: {voice}, скорость: {speed}, роль: {role}")
    print(f"Pitch: {pitch_shift}, Volume: {volume} LUFS")
    print(f"Папка: {OUTPUT_DIR}\n")

    # ── Шаг 1: Синтез ──
    print("=" * 60)
    print("ШАГ 1: СИНТЕЗ ТЕСТОВЫХ АУДИО")
    print("=" * 60)

    conn = YandexTTSConnection(ya_key, ya_folder)
    mp3_files = {}

    try:
        for name, sample in SAMPLES.items():
            mp3_path = str(OUTPUT_DIR / f"{name}.mp3")
            print(f"\n  {name}: {sample['desc']}")
            print(f"    Текст: {sample['text'][:80]}...")

            try:
                size_kb = synthesize_sample(
                    conn, sample["text"], mp3_path,
                    voice, speed, role, pitch_shift, volume,
                )
                print(f"    OK: {size_kb:.1f} KB")
                mp3_files[name] = mp3_path
                time.sleep(0.5)
            except Exception as e:
                print(f"    ОШИБКА: {e}")
    finally:
        conn.close()

    # ── Шаг 2: STT ──
    print("\n" + "=" * 60)
    print("ШАГ 2: РАСПОЗНАВАНИЕ (STT)")
    print("=" * 60)

    results = {}
    for name, mp3_path in mp3_files.items():
        print(f"\n  {name}:")
        try:
            text = recognize_audio(ya_key, ya_folder, mp3_path)
            results[name] = text
            print(f"    STT: {text}")
        except Exception as e:
            print(f"    ОШИБКА STT: {e}")
            results[name] = f"[ОШИБКА: {e}]"
        time.sleep(0.5)

    # ── Шаг 3: Сравнение ──
    print("\n" + "=" * 60)
    print("ШАГ 3: СРАВНЕНИЕ")
    print("=" * 60)

    # Эталонный текст (без разметки)
    reference = SAMPLES["01_plain"]["text"].lower()

    for name, stt_text in results.items():
        desc = SAMPLES[name]["desc"]
        stt_lower = stt_text.lower()

        # Проверяем артефакты
        issues = []
        if "звездочк" in stt_lower or "звёздочк" in stt_lower:
            issues.append("ЗВЕЗДОЧКА в озвучке!")
        if "сир " in stt_lower or stt_lower.startswith("сир"):
            issues.append("СИР в озвучке!")
        if "сил " in stt_lower:
            issues.append("СИЛ в озвучке!")
        if "плюс" in stt_lower:
            issues.append("ПЛЮС в озвучке!")

        status = "ЧИСТО" if not issues else " | ".join(issues)
        print(f"\n  {name} ({desc}):")
        print(f"    Статус: {status}")
        if issues:
            print(f"    STT: {stt_text}")

    # Сохраняем результаты
    report_path = OUTPUT_DIR / "report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "settings": {
                "voice": voice, "speed": speed, "role": role,
                "pitch_shift": pitch_shift, "volume": volume,
            },
            "samples": {
                name: {
                    "desc": SAMPLES[name]["desc"],
                    "original": SAMPLES[name]["text"],
                    "stt": results.get(name, ""),
                }
                for name in SAMPLES
            },
        }, f, ensure_ascii=False, indent=2)
    print(f"\nОтчёт сохранён: {report_path}")


if __name__ == "__main__":
    main()
