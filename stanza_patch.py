"""
Агресивний патч для відключення Stanza завантажень.
ІМПОРТУЙ ЦЕЙ ФАЙЛ ПЕРЕД українським TTS!
"""
import sys
import os

# Встановлюємо змінні оточення
os.environ["STANZA_RESOURCES_DIR"] = "/home/bandiu/.cache/stanza"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Спочатку імпортуємо справжній stanza
import stanza

# Патчимо download
_original_download = stanza.download
def _patched_download(*args, **kwargs):
    print("[Stanza Patch] BLOCKED stanza.download() call")
    return None
stanza.download = _patched_download

# Патчимо Pipeline
_original_pipeline_init = stanza.Pipeline.__init__
def _patched_pipeline_init(self, *args, **kwargs):
    kwargs['download_method'] = None  # Відключаємо завантаження
    return _original_pipeline_init(self, *args, **kwargs)
stanza.Pipeline.__init__ = _patched_pipeline_init

print("[Stanza Patch] Real stanza module patched - downloads disabled")
