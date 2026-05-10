#!/usr/bin/env python3
"""
Окремий сервер для TTS - запускається тільки якщо потрібен TTS
"""
# Патчимо stanza ПЕРЕД будь-якими імпортами
import stanza_patch  # noqa: F401

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import io
import torch

# Налаштування
_DEVICE = "cpu"
_CACHE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Ukrainian TTS Server")

class TTSRequest(BaseModel):
    text: str
    voice: str = "Dmytro"
    stress: str = "Dictionary"

_tts_model = None
_tts_loaded = False

def load_tts_model():
    """Ліниве завантаження TTS моделі"""
    global _tts_model, _tts_loaded
    
    if _tts_loaded:
        return _tts_model
    
    try:
        from ukrainian_tts.tts import TTS, Voices, Stress
        
        # Monkey-patch для пропуску завантаження з GitHub
        from os.path import exists, join
        from espnet2.bin.tts_inference import Text2Speech
        from kaldiio import load_ark
        
        def _patched_setup_cache(self, cache_folder=None):
            if cache_folder is None:
                cache_folder = _CACHE_DIR
            
            model_path = join(cache_folder, "model.pth")
            config_path = join(cache_folder, "config.yaml")
            speakers_path = join(cache_folder, "spk_xvector.ark")
            feat_stats_path = join(cache_folder, "feats_stats.npz")
            
            if exists(model_path) and exists(config_path) and exists(speakers_path) and exists(feat_stats_path):
                print("[TTS] Using cached model files (skipping GitHub check)")
                self.synthesizer = Text2Speech(
                    train_config=config_path, model_file=model_path, device=self.device
                )
                self.xvectors = {k: v for k, v in load_ark(speakers_path)}
            else:
                from ukrainian_tts.tts import TTS as OriginalTTS
                OriginalTTS._TTS__setup_cache(self, cache_folder)
        
        TTS._TTS__setup_cache = _patched_setup_cache
        _tts_model = TTS(device=_DEVICE, cache_folder=_CACHE_DIR)
        _tts_loaded = True
        print("[TTS] Модель завантажено успішно")
        return _tts_model
    except ImportError:
        print("[TTS] ukrainian-tts не встановлено")
        return None
    except Exception as e:
        print(f"[TTS] Error loading model: {e}")
        return None

@app.get("/")
async def health_check():
    return {"status": "ok", "tts_loaded": _tts_loaded}

@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Генерує українське озвучення тексту"""
    from ukrainian_tts.tts import Voices, Stress
    
    model = load_tts_model()
    if model is None:
        raise HTTPException(status_code=500, detail="TTS model not available")
    
    try:
        voice_obj = getattr(Voices, request.voice, Voices.Dmytro)
        stress_obj = getattr(Stress, request.stress, Stress.Dictionary)
        
        print(f"[TTS] Generating audio for: {request.text[:50]}... voice={request.voice}")
        
        audio_buffer = io.BytesIO()
        _, accented_text = model.tts(
            request.text,
            voice_obj.value,
            stress_obj.value,
            audio_buffer
        )
        
        audio_bytes = audio_buffer.getvalue()
        print(f"[TTS] Generated {len(audio_bytes)} bytes")
        
        from fastapi.responses import Response
        import base64
        accented_text_encoded = base64.b64encode(accented_text.encode('utf-8')).decode('ascii')
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "X-Accented-Text": accented_text_encoded,
                "Access-Control-Expose-Headers": "X-Accented-Text"
            }
        )
    except Exception as e:
        import traceback
        print(f"[TTS] Error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("[TTS] Запуск TTS сервера на порті 8003")
    uvicorn.run("tts_server:app", host="0.0.0.0", port=8003, log_level="info")
