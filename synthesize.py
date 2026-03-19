import os
import grpc
import time
import re
import yandex.cloud.ai.tts.v3.tts_pb2 as tts_pb2
import yandex.cloud.ai.tts.v3.tts_service_pb2_grpc as tts_service_pb2_grpc

# ==========================================================
# НАСТРОЙКИ (ВАШИ ДАННЫЕ)
# ==========================================================
API_KEY = os.environ.get('YANDEX_API_KEY', '')
FOLDER_ID = os.environ.get('YANDEX_FOLDER_ID', '')

VOICE = 'kirill'  # Кирилл
SPEED = 1       # Скорость 0.9x
ROLE = 'neutral'  # Амплуа: Нейтральный
# ==========================================================

def split_text_for_yandex(text, max_chars=3500):
    """
    Разбивает длинный текст на части, чтобы не превысить лимиты Яндекса.
    Режет по точкам и восклицательным знакам.
    """
    if len(text) <= max_chars:
        return [text]
    
    parts = []
    while text:
        if len(text) <= max_chars:
            parts.append(text)
            break
        
        # Ищем конец предложения в пределах лимита
        cut_idx = -1
        for char in [". ", "! ", "? "]:
            idx = text.rfind(char, 0, max_chars)
            if idx > cut_idx:
                cut_idx = idx
        
        # Если не нашли точку, режем по пробелу
        if cut_idx == -1:
            cut_idx = text.rfind(" ", 0, max_chars)
            
        # Если совсем нет пробелов, режем жестко
        if cut_idx == -1:
            cut_idx = max_chars
            
        parts.append(text[:cut_idx+1].strip())
        text = text[cut_idx+1:].strip()
    return parts

def synthesize_chapter(text_path, audio_path, stub, metadata):
    """Синтезирует один текстовый файл в один MP3."""
    with open(text_path, "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    if not full_text:
        return

    # Разбиваем на части, если файл очень длинный
    text_parts = split_text_for_yandex(full_text)

    try:
        with open(audio_path, 'wb') as f_out:
            for i, part in enumerate(text_parts):
                request = tts_pb2.UtteranceSynthesisRequest(
                    text=part,
                    output_audio_spec=tts_pb2.AudioFormatOptions(
                        container_audio=tts_pb2.ContainerAudio(
                            container_audio_type=tts_pb2.ContainerAudio.MP3
                        )
                    ),
                    hints=[
                        tts_pb2.Hints(voice=VOICE),
                        tts_pb2.Hints(speed=SPEED),
                        tts_pb2.Hints(role=ROLE)
                    ],
                    loudness_normalization_type=tts_pb2.UtteranceSynthesisRequest.LUFS,
                    unsafe_mode=True # Включает поддержку TTS-разметки (sil, **, +)
                )
                
                # Потоковая запись аудио чанков
                for response in stub.UtteranceSynthesis(request, metadata=metadata):
                    f_out.write(response.audio_chunk.data)
                
                # Небольшая пауза между запросами для стабильности
                if len(text_parts) > 1:
                    time.sleep(0.2)
        return True
    except Exception as e:
        print(f"   [ОШИБКА] Не удалось синтезировать {os.path.basename(text_path)}: {e}")
        return False

def main():
    # Подключаемся к Яндекс gRPC
    cred = grpc.ssl_channel_credentials()
    channel = grpc.secure_channel('tts.api.cloud.yandex.net:443', cred)
    stub = tts_service_pb2_grpc.SynthesizerStub(channel)
    metadata = (('authorization', f'Api-Key {API_KEY}'), ('x-folder-id', FOLDER_ID))

    chapters_root = "chapters"
    output_root = "output"

    if not os.path.exists(chapters_root):
        print("Папка 'chapters' не найдена. Сначала запустите prepare_gemini.py")
        return

    # Перебираем все папки с книгами
    book_folders = [d for d in os.listdir(chapters_root) if os.path.isdir(os.path.join(chapters_root, d))]

    if not book_folders:
        print("В папке 'chapters' нет подпапок с книгами.")
        return

    for book_name in book_folders:
        in_dir = os.path.join(chapters_root, book_name)
        out_dir = os.path.join(output_root, book_name)
        
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        print(f"\n>>> НАЧИНАЕМ СИНТЕЗ КНИГИ: {book_name}")
        
        # Получаем список txt файлов в алфавитном порядке
        txt_files = sorted([f for f in os.listdir(in_dir) if f.endswith(".txt")])
        
        for f in txt_files:
            print(f"  Синтезирую главу: {f} ...")
            txt_path = os.path.join(in_dir, f)
            mp3_path = os.path.join(out_dir, f.replace(".txt", ".mp3"))
            
            success = synthesize_chapter(txt_path, mp3_path, stub, metadata)
            if success:
                # Пауза между разными файлами глав
                time.sleep(0.5)

    print("\n[ГОТОВО] Все аудиокниги находятся в папке 'output'.")

if __name__ == "__main__":
    main()