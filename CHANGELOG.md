# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2025-01-01

### Added
- Text cleaning pipeline: encoding detection, artifact removal, chapter splitting
- AI-powered TTS markup via DeepSeek API (stress marks, pauses, intonation)
- Speech synthesis via Yandex SpeechKit gRPC with 13 voice options
- Batch processing queue for multiple files
- Desktop GUI with ttkbootstrap (dark/light theme)
- Quality testing: STT verification and audio clarity checks
- Configuration via `config.json` and in-app Settings screen
- Support for voice styles: neutral, good, strict, friendly
- Pitch shift and volume (LUFS) controls
- Automatic book title detection and removal
- Chapter pattern recognition (Глава, Пролог, Эпилог, Часть, etc.)
- Manual processing mode for introductory sections (Вступление, Предисловие, etc.)
