"""
Проверка аудио-сэмплов через Google STT (бесплатный).
Конвертирует MP3 -> WAV, распознаёт, ищет артефакты.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLES_DIR = ROOT / "test_samples"

import speech_recognition as sr
from pydub import AudioSegment


EXPECTED_WORDS = [
    "окружающего", "мира", "желаешь", "получать", "уважение", "похвалу",
    "ждешь", "миру", "мнимые", "ожидания", "заслуженные",
    "ценишь", "существует", "живёт",
]

ARTIFACT_WORDS = ["звездочк", "звёздочк", "плюс", "сир ", "сил "]


def check_mp3(mp3_path):
    """Конвертирует MP3 в WAV и распознаёт через Google STT."""
    wav_path = mp3_path.replace(".mp3", ".wav")

    # MP3 -> WAV
    audio = AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(wav_path, format="wav")

    # STT
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio_data, language="ru-RU")
    except sr.UnknownValueError:
        text = "[НЕ РАСПОЗНАНО]"
    except sr.RequestError as e:
        text = f"[ОШИБКА: {e}]"

    # Cleanup
    os.remove(wav_path)
    return text


def main():
    mp3_files = sorted(SAMPLES_DIR.glob("*.mp3"))
    if not mp3_files:
        print("Нет MP3 файлов в test_samples/")
        return

    print("=" * 70)
    print("ПРОВЕРКА АУДИО ЧЕРЕЗ GOOGLE STT")
    print("=" * 70)

    results = {}
    for mp3 in mp3_files:
        name = mp3.stem
        print(f"\n{'-' * 50}")
        print(f"  {name}")
        print(f"  Файл: {mp3.name} ({mp3.stat().st_size // 1024} KB)")

        text = check_mp3(str(mp3))
        results[name] = text
        print(f"  STT:  {text}")

        # Проверяем артефакты
        text_lower = text.lower()
        issues = []
        for artifact in ARTIFACT_WORDS:
            if artifact in text_lower:
                issues.append(f"'{artifact.strip()}' НАЙДЕНО!")

        if issues:
            print(f"  ПРОБЛЕМЫ: {' | '.join(issues)}")
        else:
            print(f"  Артефактов: НЕТ")

    # Итого
    print(f"\n{'=' * 70}")
    print("ИТОГО:")
    print(f"{'=' * 70}")
    for name, text in results.items():
        text_lower = text.lower()
        has_issues = any(a in text_lower for a in ARTIFACT_WORDS)
        marker = "!!!" if has_issues else "OK "
        print(f"  [{marker}] {name}: {text[:80]}...")


if __name__ == "__main__":
    main()
