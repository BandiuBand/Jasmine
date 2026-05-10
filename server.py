# Патчимо stanza ПЕРЕД будь-якими імпортами
import stanza_patch  # noqa: F401

import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from faster_whisper import WhisperModel
import uvicorn
import tempfile
import io

import torch

# Set cache directory to avoid GitHub checks on every startup
_CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ["UKRAINIAN_TTS_CACHE_DIR"] = _CACHE_DIR

print(torch.version.cuda)         # версія CUDA, з якою зібраний PyTorch
print(torch.backends.cudnn.version())  # якщо None – cuDNN не знайдено
print(torch.cuda.is_available())  # має повернути True

app = FastAPI(title="Whisper GPU Server")


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Змінити на потрібний розмір моделі: tiny, base, small, medium, large
MODEL_SIZE = "small"
DEVICE = "cpu"  # або "cpu", якщо GPU тимчасово недоступний
COMPUTE_TYPE="int8"

# Завантажуємо модель один раз при старті
model = WhisperModel(
    MODEL_SIZE,
    device=DEVICE,
    compute_type=COMPUTE_TYPE
)

# TTS з лінивим завантаженням - завантажується тільки при першому запиті
_tts_model = None
_tts_loaded = False

print("[TTS] TTS з лінивим завантаженням (без завантаження з інтернету)")

class TranscriptionResult(BaseModel):
    text: str

class TTSRequest(BaseModel):
    text: str
    voice: str = "Dmytro"
    stress: str = "Dictionary"

@app.post("/transcribe", response_model=TranscriptionResult)
async def transcribe_audio(file: UploadFile = File(...), language: str = "uk"):
    # Приймаємо будь-який аудіоформат, зберігаємо в тимчасовий файл
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        segments, _ = model.transcribe(tmp_path, language=language)
        text = "".join([seg.text for seg in segments])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(tmp_path)

    return {"text": text}


@app.post("/tts")
async def text_to_speech(request: TTSRequest):
    """Генерує українське озвучення тексту з кешованими моделями без завантаження з інтернету"""
    global _tts_model, _tts_loaded
    
    # Ліниве завантаження TTS моделі при першому запиті
    if not _tts_loaded:
        try:
            from ukrainian_tts.tts import TTS, Voices, Stress
            from os.path import exists, join
            
            # Перевіряємо чи існують кешовані файли
            model_path = join(_CACHE_DIR, "model.pth")
            config_path = join(_CACHE_DIR, "config.yaml")
            speakers_path = join(_CACHE_DIR, "spk_xvector.ark")
            feat_stats_path = join(_CACHE_DIR, "feats_stats.npz")
            
            if not (exists(model_path) and exists(config_path) and exists(speakers_path) and exists(feat_stats_path)):
                raise HTTPException(status_code=500, detail="TTS model files not found in cache")
            
            # Monkey-patch для пропуску завантаження з GitHub
            from espnet2.bin.tts_inference import Text2Speech
            from kaldiio import load_ark
            
            def _patched_setup_cache(self, cache_folder=None):
                if cache_folder is None:
                    cache_folder = _CACHE_DIR
                
                print("[TTS] Using cached model files (skipping GitHub check)")
                self.synthesizer = Text2Speech(
                    train_config=config_path, model_file=model_path, device=self.device
                )
                self.xvectors = {k: v for k, v in load_ark(speakers_path)}
            
            TTS._TTS__setup_cache = _patched_setup_cache
            _tts_model = TTS(device=DEVICE, cache_folder=_CACHE_DIR)
            _tts_loaded = True
            print("[TTS] Модель завантажено з кешу (без завантаження з інтернету)")
        except ImportError:
            raise HTTPException(status_code=500, detail="TTS model not available")
        except Exception as e:
            import traceback
            print(f"[TTS] Error loading model: {e}")
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    if _tts_model is None:
        raise HTTPException(status_code=500, detail="TTS model not loaded")

    try:
        from ukrainian_tts.tts import Voices, Stress
        # Отримуємо voice та stress об'єкти
        voice_obj = getattr(Voices, request.voice, Voices.Dmytro)
        stress_obj = getattr(Stress, request.stress, Stress.Dictionary)

        print(f"[TTS] Generating audio for: {request.text[:50]}... voice={request.voice}")

        # Генеруємо аудіо в пам'яті
        audio_buffer = io.BytesIO()
        _, accented_text = _tts_model.tts(
            request.text,
            voice_obj.value,
            stress_obj.value,
            audio_buffer
        )

        # Отримуємо байти з буфера
        audio_bytes = audio_buffer.getvalue()

        print(f"[TTS] Generated {len(audio_bytes)} bytes")

        from fastapi.responses import Response
        # Encode accented text as UTF-8 for HTTP header compatibility
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
    uvicorn.run("server:app", host="0.0.0.0", port=8002, log_level="info")
