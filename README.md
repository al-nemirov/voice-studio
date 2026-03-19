# Voice Studio

[Русский](#русский) | [English](#english)

---

## English

Text-to-speech studio for Russian language using Yandex SpeechKit and AI-powered TTS markup.

### Features

- **Text cleaning** — auto-split into chapters, remove artifacts, normalize formatting
- **AI markup** — automatic stress marks, pauses, and intonation via DeepSeek API
- **Speech synthesis** — Yandex SpeechKit gRPC with 13 voice options
- **Batch processing** — process multiple files in queue
- **Desktop GUI** — ttkbootstrap interface with dark/light theme
- **Quality testing** — STT verification and audio clarity checks

### Pipeline

1. **Clean** — Load .txt file, detect encoding, split into chapters, remove junk
2. **Mark** — AI adds TTS markup: stress (+), pauses (sil<[N]>), accents
3. **Synthesize** — Yandex SpeechKit converts marked text to MP3

### Voices

Alexander, Kirill, Alena, Dasha, Marina, Lera, Amira, Madi, Nigora, Lea, Naomi, John, Filipp

### Configuration

Edit `config.json` or use the Settings screen:
- `deepseek_api_key` — DeepSeek API key (for AI markup)
- `yandex_api_key` — Yandex Cloud API key (for synthesis)
- `yandex_folder_id` — Yandex Cloud folder ID
- `voice` — voice name
- `speed` — playback speed (default: 1.0)
- `role` — voice style: neutral, good, strict, friendly
- `pitch_shift` — pitch adjustment (-1000 to +1000 Hz)
- `volume` — loudness in LUFS (default: -19)

### Requirements

- Python 3.8+
- `grpcio`, `protobuf`
- `ttkbootstrap`
- `yandex-cloud` (gRPC stubs)

### Setup

1. Get [Yandex Cloud API key](https://cloud.yandex.ru/docs/iam/operations/api-key/create)
2. Get [DeepSeek API key](https://platform.deepseek.com/)
3. Fill in `config.json` or configure via GUI

---

## Русский

Студия озвучки текстов на русском языке с Яндекс SpeechKit и AI-разметкой.

### Возможности

- **Очистка текста** — авторазбивка на главы, удаление артефактов, нормализация
- **AI-разметка** — автоматические ударения, паузы, интонации через DeepSeek API
- **Синтез речи** — Яндекс SpeechKit gRPC, 13 голосов
- **Пакетная обработка** — очередь из нескольких файлов
- **GUI** — интерфейс ttkbootstrap с тёмной/светлой темой
- **Тестирование качества** — проверка через STT и анализ чёткости

### Конвейер

1. **Очистка** — загрузка .txt, определение кодировки, разбивка на главы
2. **Разметка** — AI расставляет ударения (+), паузы (sil<[N]>), акценты
3. **Синтез** — Яндекс SpeechKit конвертирует размеченный текст в MP3

### Голоса

Александр, Кирилл, Алёна, Даша, Марина, Лера, Амира, Мади, Нигора, Леа, Наоми, Джон, Филипп

### Настройка

Отредактируйте `config.json` или используйте экран настроек:
- `deepseek_api_key` — ключ DeepSeek API (для AI-разметки)
- `yandex_api_key` — ключ Yandex Cloud API (для синтеза)
- `yandex_folder_id` — ID каталога Yandex Cloud
- `voice` — имя голоса
- `speed` — скорость (по умолчанию: 1.0)
- `role` — стиль: neutral, good, strict, friendly
- `pitch_shift` — сдвиг тона (-1000 до +1000 Гц)
- `volume` — громкость в LUFS (по умолчанию: -19)

### Требования

- Python 3.8+
- `grpcio`, `protobuf`
- `ttkbootstrap`
- `yandex-cloud` (gRPC-стабы)

### Установка

1. Получите [ключ Yandex Cloud API](https://cloud.yandex.ru/docs/iam/operations/api-key/create)
2. Получите [ключ DeepSeek API](https://platform.deepseek.com/)
3. Заполните `config.json` или настройте через GUI

## Author / Автор

Alexander Nemirov
