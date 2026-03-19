"""
Voice Studio - Конфигурация
===============================
Менеджер настроек. Хранение в config.json.
"""

import json
import threading
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT_DIR / "config.json"

# Голоса Yandex SpeechKit (id → {gender, roles})
YANDEX_VOICES = {
    "kirill":    {"gender": "М", "roles": ["neutral", "strict", "good"]},
    "alexander": {"gender": "М", "roles": ["neutral", "good"]},
    "anton":     {"gender": "М", "roles": ["neutral", "good"]},
    "filipp":    {"gender": "М", "roles": ["neutral"]},
    "zahar":     {"gender": "М", "roles": ["neutral", "good"]},
    "ermil":     {"gender": "М", "roles": ["neutral", "good"]},
    "alena":     {"gender": "Ж", "roles": ["neutral", "good"]},
    "dasha":     {"gender": "Ж", "roles": ["neutral", "good", "friendly"]},
    "julia":     {"gender": "Ж", "roles": ["neutral", "strict"]},
    "lera":      {"gender": "Ж", "roles": ["neutral", "friendly"]},
    "masha":     {"gender": "Ж", "roles": ["good", "strict", "friendly"]},
    "marina":    {"gender": "Ж", "roles": ["neutral", "whisper", "friendly"]},
    "jane":      {"gender": "Ж", "roles": ["neutral", "good", "evil"]},
}

DEEPSEEK_MODELS = ["deepseek-chat", "deepseek-reasoner"]

DEFAULTS = {
    "deepseek_api_key": "",
    "deepseek_model": "deepseek-chat",
    "yandex_api_key": "",
    "yandex_folder_id": "",
    "voice": "kirill",
    "speed": 1.0,
    "role": "neutral",
    "pitch_shift": 0.0,
    "volume": -19.0,
    "theme": "dark",
}


class ConfigManager:
    """Менеджер настроек — Singleton, thread-safe, JSON."""

    def __init__(self):
        self._data: dict = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}
        # Дополняем дефолтами
        for k, v in DEFAULTS.items():
            self._data.setdefault(k, v)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        with self._lock:
            self._data[key] = value

    def save(self) -> bool:
        with self._lock:
            try:
                tmp = CONFIG_PATH.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=4)
                tmp.replace(CONFIG_PATH)
                return True
            except Exception:
                return False

    def get_voice_roles(self, voice: str) -> list:
        info = YANDEX_VOICES.get(voice)
        if info:
            return info["roles"]
        return ["neutral"]

    # Для совместимости с theme.py
    def get_value(self, section: str, key: str, default=None):
        return self.get(key, default)


# Singleton
_instance = None
_init_lock = threading.Lock()


def get_config() -> ConfigManager:
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = ConfigManager()
    return _instance
