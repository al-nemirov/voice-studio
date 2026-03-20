# Voice Studio

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)
![TTS](https://img.shields.io/badge/TTS-Yandex%20SpeechKit-red)

[Русский](#русский) | [English](#english)

---

## English

Text-to-speech studio for Russian language using Yandex SpeechKit and AI-powered TTS markup.

### Features

- **Text cleaning** -- auto-split into chapters, remove artifacts, normalize formatting
- **AI markup** -- automatic stress marks, pauses, and intonation via DeepSeek API
- **Speech synthesis** -- Yandex SpeechKit gRPC with 13 voice options
- **Batch processing** -- process multiple files in queue
- **Desktop GUI** -- ttkbootstrap interface with dark/light theme
- **Quality testing** -- STT verification and audio clarity checks

### Architecture

```
voice-studio/
├── run.py / run.pyw          # Application entry points
├── config.json               # User configuration
├── requirements.txt          # Python dependencies
├── src/
│   ├── app.py                # Main application controller
│   ├── core/
│   │   ├── text_cleaner.py   # Step 1: Text cleaning & chapter splitting
│   │   ├── preparer.py       # Step 2: AI markup (DeepSeek)
│   │   └── synthesizer.py    # Step 3: Yandex SpeechKit TTS
│   ├── ui/
│   │   ├── theme.py          # Theme management (dark/light)
│   │   └── screens/          # GUI screens (ttkbootstrap)
│   └── utils/
│       └── config.py         # Configuration loader
├── test_audio_quality.py     # Audio quality tests
├── test_clarity.py           # Clarity analysis
└── test_stt_check.py         # STT verification tests
```

### Pipeline

1. **Clean** -- Load `.txt` file, detect encoding, split into chapters, remove junk
2. **Mark** -- AI adds TTS markup: stress (`+`), pauses (`sil<[N]>`), accents
3. **Synthesize** -- Yandex SpeechKit converts marked text to MP3

### Voices

Alexander, Kirill, Alena, Dasha, Marina, Lera, Amira, Madi, Nigora, Lea, Naomi, John, Filipp

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/al-nemirov/voice-studio.git
   cd voice-studio
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate    # Linux/macOS
   venv\Scripts\activate       # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Obtain API keys:**
   - [Yandex Cloud API key](https://cloud.yandex.ru/docs/iam/operations/api-key/create)
   - [DeepSeek API key](https://platform.deepseek.com/)

5. **Configure the application:**
   Fill in `config.json` or use the Settings screen in the GUI.

6. **Run:**
   ```bash
   python run.py
   ```
   Or double-click `run.pyw` for a windowless launch on Windows.

### Configuration

Edit `config.json` or use the Settings screen in the GUI:

| Parameter          | Description                            | Default  |
|--------------------|----------------------------------------|----------|
| `deepseek_api_key` | DeepSeek API key (for AI markup)       | --       |
| `yandex_api_key`   | Yandex Cloud API key (for synthesis)   | --       |
| `yandex_folder_id` | Yandex Cloud folder ID                 | --       |
| `voice`            | Voice name (see list above)            | --       |
| `speed`            | Playback speed                         | `1.0`    |
| `role`             | Voice style: neutral, good, strict, friendly | `neutral` |
| `pitch_shift`      | Pitch adjustment (-1000 to +1000 Hz)   | `0`      |
| `volume`           | Loudness in LUFS                       | `-19`    |

### Requirements

- Python 3.8+
- `grpcio`, `protobuf`
- `ttkbootstrap`
- `openai` (DeepSeek-compatible client)
- `yandex-cloud` (gRPC stubs)
- `chardet`, `pydub`, `SpeechRecognition`

### Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and commit: `git commit -m "Add my feature"`
4. Push to your fork: `git push origin feature/my-feature`
5. Open a Pull Request

Please ensure your code follows the existing code style and includes docstrings for new functions.

---

## Русский

Студия озвучки текстов на русском языке с Яндекс SpeechKit и AI-разметкой.

### Возможности

- **Очистка текста** -- авторазбивка на главы, удаление артефактов, нормализация
- **AI-разметка** -- автоматические ударения, паузы, интонации через DeepSeek API
- **Синтез речи** -- Яндекс SpeechKit gRPC, 13 голосов
- **Пакетная обработка** -- очередь из нескольких файлов
- **GUI** -- интерфейс ttkbootstrap с тёмной/светлой темой
- **Тестирование качества** -- проверка через STT и анализ чёткости

### Архитектура

```
voice-studio/
├── run.py / run.pyw          # Точки входа
├── config.json               # Конфигурация
├── requirements.txt          # Зависимости Python
├── src/
│   ├── app.py                # Главный контроллер
│   ├── core/
│   │   ├── text_cleaner.py   # Шаг 1: Очистка текста и разбивка на главы
│   │   ├── preparer.py       # Шаг 2: AI-разметка (DeepSeek)
│   │   └── synthesizer.py    # Шаг 3: Синтез через Yandex SpeechKit
│   ├── ui/
│   │   ├── theme.py          # Управление темой (тёмная/светлая)
│   │   └── screens/          # Экраны GUI (ttkbootstrap)
│   └── utils/
│       └── config.py         # Загрузчик конфигурации
├── test_audio_quality.py     # Тесты качества аудио
├── test_clarity.py           # Анализ чёткости
└── test_stt_check.py         # Проверка через STT
```

### Конвейер

1. **Очистка** -- загрузка `.txt`, определение кодировки, разбивка на главы
2. **Разметка** -- AI расставляет ударения (`+`), паузы (`sil<[N]>`), акценты
3. **Синтез** -- Яндекс SpeechKit конвертирует размеченный текст в MP3

### Голоса

Александр, Кирилл, Алёна, Даша, Марина, Лера, Амира, Мади, Нигора, Леа, Наоми, Джон, Филипп

### Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/al-nemirov/voice-studio.git
   cd voice-studio
   ```

2. **Создайте виртуальное окружение (рекомендуется):**
   ```bash
   python -m venv venv
   source venv/bin/activate    # Linux/macOS
   venv\Scripts\activate       # Windows
   ```

3. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Получите API-ключи:**
   - [Ключ Yandex Cloud API](https://cloud.yandex.ru/docs/iam/operations/api-key/create)
   - [Ключ DeepSeek API](https://platform.deepseek.com/)

5. **Настройте приложение:**
   Заполните `config.json` или используйте экран настроек в GUI.

6. **Запуск:**
   ```bash
   python run.py
   ```
   Или дважды кликните `run.pyw` для запуска без консоли на Windows.

### Конфигурация

Отредактируйте `config.json` или используйте экран настроек:

| Параметр           | Описание                                      | По умолчанию |
|--------------------|-----------------------------------------------|--------------|
| `deepseek_api_key` | Ключ DeepSeek API (для AI-разметки)           | --           |
| `yandex_api_key`   | Ключ Yandex Cloud API (для синтеза)           | --           |
| `yandex_folder_id` | ID каталога Yandex Cloud                      | --           |
| `voice`            | Имя голоса (см. список выше)                  | --           |
| `speed`            | Скорость воспроизведения                      | `1.0`        |
| `role`             | Стиль: neutral, good, strict, friendly        | `neutral`    |
| `pitch_shift`      | Сдвиг тона (-1000 до +1000 Гц)               | `0`          |
| `volume`           | Громкость в LUFS                              | `-19`        |

### Требования

- Python 3.8+
- `grpcio`, `protobuf`
- `ttkbootstrap`
- `openai` (DeepSeek-совместимый клиент)
- `yandex-cloud` (gRPC-стабы)
- `chardet`, `pydub`, `SpeechRecognition`

### Участие в разработке

Мы рады вашим вкладам! Чтобы внести изменения:

1. Сделайте форк репозитория
2. Создайте ветку: `git checkout -b feature/my-feature`
3. Внесите изменения и закоммитьте: `git commit -m "Add my feature"`
4. Отправьте в свой форк: `git push origin feature/my-feature`
5. Откройте Pull Request

Пожалуйста, следуйте существующему стилю кода и добавляйте docstring к новым функциям.

---

## Author / Автор

Alexander Nemirov

## License / Лицензия

This project is licensed under the MIT License -- see the [LICENSE](LICENSE) file for details.
