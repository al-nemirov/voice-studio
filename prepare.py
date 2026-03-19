import os
import time
import re
import google.generativeai as genai

# --- НАСТРОЙКИ ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = 'gemini-2.0-flash-exp'
model = genai.GenerativeModel(MODEL_NAME)

SYSTEM_PROMPT = """Ты — эксперт-лингвист по TTS-разметке для Yandex SpeechKit.

ПРАВИЛА:
1. УДАРЕНИЯ (+): Ставь ТОЛЬКО в омонимах (з+амок/зам+ок, ст+оит/сто+ит, +атлас/атл+ас)
2. ПАУЗЫ: ' sil<[600]> ' (с пробелами!) в конце абзацев
3. АКЦЕНТЫ: **1 важное слово** в абзаце
4. ЗАПРЕТЫ: Не меняй текст. Не пиши вступлений.

Верни только размеченный текст."""

def sanitize_filename(name):
    clean = re.sub(r'[^a-zA-Zа-яА-Я0-9]', '_', name)
    return clean.strip('_')[:60]

def call_gemini(text):
    if not text.strip(): 
        return ""
    try:
        res = model.generate_content(
            f"{SYSTEM_PROMPT}\n\nТЕКСТ:\n{text}",
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                top_p=0.8,
                max_output_tokens=8000,
            )
        )
        clean = re.sub(r'```[a-z]*\n?', '', res.text).replace('```', '')
        clean = re.sub(r'^(Понял|Конечно|Вот|Хорошо|Предоставляю|Привет|Текст).*?\n', '', clean, flags=re.IGNORECASE)
        clean = re.sub(r'(\S)(sil<)', r'\1 \2', clean)
        return clean.strip()
    except Exception as e:
        print(f"    ⚠ Ошибка: {e}")
        return text

def process_intro_manual(intro_text):
    """Обрабатываем вступление БЕЗ AI - только паузы"""
    lines = intro_text.split('\n')
    result = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Просто добавляем паузу БЕЗ плюсов
        result.append(f"{stripped} sil<[2000]>")
    
    return "\n\n".join(result)

def process_book():
    input_file = "books/Провидец.txt" 
    output_dir = "chapters/Провидец"
    if not os.path.exists(output_dir): 
        os.makedirs(output_dir)

    with open(input_file, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Ищем главы
    chapter_pattern = r'(?m)^((?:Глава|Пролог|Эпилог)\s*.+)$'
    matches = list(re.finditer(chapter_pattern, full_text, re.IGNORECASE))
    
    segments = []
    
    # 1. Вступление (БЕЗ AI!)
    if matches:
        intro_text = full_text[:matches[0].start()].strip()
        if intro_text:
            segments.append(("Вступление", intro_text, "manual"))
        
        # 2. Главы (С AI)
        for i in range(len(matches)):
            title = matches[i].group(1).strip()
            start = matches[i].end()
            end = matches[i+1].start() if i+1 < len(matches) else len(full_text)
            content = full_text[start:end].strip()
            content = re.sub(r'(?m)^Часть\s+\d+\s*$', '', content).strip()
            segments.append((title, content, "ai"))
    else:
        segments.append(("Книга", full_text, "ai"))

    for idx, (title, content, mode) in enumerate(segments):
        file_path = os.path.join(output_dir, f"{idx:03d}_{sanitize_filename(title)}.txt")
        if os.path.exists(file_path):
            print(f"⏭ Пропуск: {title}")
            continue
        
        print(f"🔄 Обработка: {title}...")

        final_text = f"{title} sil<[2000]>\n\n"

        if content:
            if mode == "manual":
                # Вступление: ВРУЧНУЮ без AI
                print(f"    └─ Ручная обработка (без плюсов)")
                final_text += process_intro_manual(content)
            
            else:
                # Главы: через AI порциями
                paragraphs = [p for p in content.split('\n') if p.strip()]
                current_chunk = ""
                chunk_count = 0
                
                for p in paragraphs:
                    if len(current_chunk) + len(p) > 4000:
                        chunk_count += 1
                        print(f"    └─ AI порция {chunk_count}...")
                        final_text += call_gemini(current_chunk) + "\n\n"
                        current_chunk = p
                        time.sleep(2)
                    else:
                        current_chunk += "\n" + p
                
                if current_chunk:
                    chunk_count += 1
                    print(f"    └─ AI порция {chunk_count}...")
                    final_text += call_gemini(current_chunk) + "\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_text.strip())
        
        print(f"    ✓ {os.path.basename(file_path)}")
        time.sleep(1)

if __name__ == "__main__":
    print("\n" + "="*60)
    print("📖 РАЗМЕТКА ДЛЯ YANDEX SPEECHKIT")
    print("="*60 + "\n")
    process_book()
    print("\n" + "="*60)
    print("✅ ГОТОВО!")
    print("="*60 + "\n")