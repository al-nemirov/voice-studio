import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.app import VoiceStudioApp

if __name__ == "__main__":
    app = VoiceStudioApp()
    app.run()
