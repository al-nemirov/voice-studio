"""
Тест чёткости произношения: разные скорости и паузы.
Создаёт сэмплы, прогоняет STT, считает потерянные слова.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.utils.config import get_config
from src.core.synthesizer import YandexTTSConnection
import grpc
import yandex.cloud.ai.tts.v3.tts_pb2 as tts_pb2

import speech_recognition as sr
from pydub import AudioSegment

OUTPUT_DIR = ROOT / "test_clarity"
OUTPUT_DIR.mkdir(exist_ok=True)

# Реальный текст из книги - сложные длинные предложения
SAMPLE_TEXT = (
    "Пашка остановился и женщина вручила ему всё необходимое для достойного заработка. "
    "Он принял пакет и ещё раз поблагодарив поспешил уйти. "
    "Оставалось позаботиться о ночлеге. "
    "Уже более уверенно шагая по улице города, Пашка прокручивал разные варианты."
)

# То же самое с разметкой
SAMPLE_MARKED = (
    "П+ашка остановился и ж+енщина вручила ему всё необходимое для дост+ойного заработка. "
    "sil<[300]> "
    "Он принял пакет <[small]> и ещё раз поблагодарив <[tiny]> поспешил уйти. "
    "sil<[400]> "
    "Оставалось позаботиться о ночлеге. "
    "sil<[300]> "
    "Уж+е более уверенно шагая по улице г+орода, <[small]> П+ашка прокр+учивал разные варианты."
)

# Слова для подсчёта точности
REFERENCE_WORDS = [
    "пашка", "остановился", "женщина", "вручила", "необходимое",
    "достойного", "заработка", "принял", "поблагодарив", "поспешил",
    "оставалось", "позаботиться", "ночлеге", "уверенно", "шагая",
    "прокручивал", "варианты",
]


def synthesize(conn, text, mp3_path, voice, speed, role, pitch_shift, volume):
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
        for response in conn.stub.UtteranceSynthesis(request, metadata=conn.metadata):
            f_out.write(response.audio_chunk.data)
    return os.path.getsize(mp3_path) / 1024


def stt(mp3_path):
    wav_path = mp3_path.replace(".mp3", ".wav")
    audio = AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(wav_path, format="wav")

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio_data, language="ru-RU")
    except sr.UnknownValueError:
        text = ""
    except sr.RequestError as e:
        text = ""
    os.remove(wav_path)
    return text


def word_accuracy(stt_text, ref_words):
    stt_lower = stt_text.lower()
    found = sum(1 for w in ref_words if w in stt_lower)
    if not ref_words:
        return 0, 0, 0
    return found, len(ref_words), round(found / len(ref_words) * 100)


def main():
    config = get_config()
    ya_key = config.get("yandex_api_key")
    ya_folder = config.get("yandex_folder_id")
    voice = config.get("voice", "alexander")
    role = config.get("role", "neutral")
    pitch_shift = config.get("pitch_shift", 0.0)
    volume = config.get("volume", -19.0)

    # Тестовые варианты: (имя, скорость, текст, описание)
    variants = [
        ("speed_090_plain",  0.9,  SAMPLE_TEXT,   "Скорость 0.9, без разметки"),
        ("speed_090_marked", 0.9,  SAMPLE_MARKED, "Скорость 0.9, с разметкой"),
        ("speed_085_plain",  0.85, SAMPLE_TEXT,    "Скорость 0.85, без разметки"),
        ("speed_085_marked", 0.85, SAMPLE_MARKED,  "Скорость 0.85, с разметкой"),
        ("speed_080_plain",  0.80, SAMPLE_TEXT,    "Скорость 0.80, без разметки"),
        ("speed_080_marked", 0.80, SAMPLE_MARKED,  "Скорость 0.80, с разметкой"),
    ]

    print(f"Голос: {voice}, роль: {role}")
    print(f"Эталон: {len(REFERENCE_WORDS)} ключевых слов\n")

    conn = YandexTTSConnection(ya_key, ya_folder)

    try:
        # Синтез
        print("=" * 70)
        print("СИНТЕЗ")
        print("=" * 70)

        mp3s = {}
        for name, speed, text, desc in variants:
            mp3_path = str(OUTPUT_DIR / f"{name}.mp3")
            print(f"  {desc}...", end=" ", flush=True)
            try:
                kb = synthesize(conn, text, mp3_path, voice, speed, role, pitch_shift, volume)
                mp3s[name] = mp3_path
                print(f"OK ({kb:.0f} KB)")
            except Exception as e:
                print(f"ОШИБКА: {e}")
            time.sleep(0.5)
    finally:
        conn.close()

    # STT + сравнение
    print("\n" + "=" * 70)
    print("РАСПОЗНАВАНИЕ + ТОЧНОСТЬ")
    print("=" * 70)

    for name, speed, text, desc in variants:
        if name not in mp3s:
            continue
        stt_text = stt(mp3s[name])
        found, total, pct = word_accuracy(stt_text, REFERENCE_WORDS)

        # Какие слова потерялись?
        stt_lower = stt_text.lower()
        missing = [w for w in REFERENCE_WORDS if w not in stt_lower]

        print(f"\n  {desc}")
        print(f"    STT:      {stt_text}")
        print(f"    Точность: {found}/{total} ({pct}%)")
        if missing:
            print(f"    Потеряны: {', '.join(missing)}")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
