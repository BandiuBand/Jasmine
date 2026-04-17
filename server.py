from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from faster_whisper import WhisperModel
import uvicorn
import tempfile
import os
import io

import torch

# Set cache directory to avoid GitHub checks on every startup
_CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ["UKRAINIAN_TTS_CACHE_DIR"] = _CACHE_DIR

# Monkey-patch ukrainian-tts to skip download check when files exist
def _patched_setup_cache(self, cache_folder=None):
    """Patched version that checks if files exist before printing download message"""
    from os.path import exists, join
    from espnet2.bin.tts_inference import Text2Speech
    from kaldiio import load_ark
    
    if cache_folder is None:
        cache_folder = "."
    
    model_path = join(cache_folder, "model.pth")
    config_path = join(cache_folder, "config.yaml")
    speakers_path = join(cache_folder, "spk_xvector.ark")
    feat_stats_path = join(cache_folder, "feats_stats.npz")
    
    # Check if all files exist
    if exists(model_path) and exists(config_path) and exists(speakers_path) and exists(feat_stats_path):
        print("[TTS] Using cached model files (skipping GitHub check)")
        # Set up synthesizer directly without downloading
        self.synthesizer = Text2Speech(
            train_config=config_path, model_file=model_path, device=self.device
        )
        self.xvectors = {k: v for k, v in load_ark(speakers_path)}
    else:
        # Files don't exist, use original setup
        from ukrainian_tts.tts import TTS as OriginalTTS
        OriginalTTS._TTS__setup_cache(self, cache_folder)

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

# Завантажуємо українську TTS
try:
    from ukrainian_tts.tts import TTS, Voices, Stress
    # Apply monkey-patch to skip download when files exist
    TTS.__setup_cache = _patched_setup_cache
    tts_model = TTS(device=DEVICE, cache_folder=_CACHE_DIR)
    print("[TTS] Українська TTS завантажена успішно")
except ImportError:
    print("[TTS] ukrainian-tts не встановлено. Встановіть: pip install git+https://github.com/robinhad/ukrainian-tts.git")
    tts_model = None

class TranscriptionResult(BaseModel):
    text: str

class TTSRequest(BaseModel):
    text: str
    voice: str = "Dmytro"  # Dmytro, Mykyta, Oleksa, Tetiana, Lada
    stress: str = "Dictionary"  # Dictionary, Model, Auto

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
    """Генерує українське озвучення тексту без збереження файлу на диск"""
    if tts_model is None:
        raise HTTPException(status_code=500, detail="TTS model not loaded")

    try:
        # Отримуємо voice та stress об'єкти
        voice_obj = getattr(Voices, request.voice, Voices.Dmytro)
        stress_obj = getattr(Stress, request.stress, Stress.Dictionary)

        print(f"[TTS] Generating audio for: {request.text[:50]}... voice={request.voice}")

        # Генеруємо аудіо в пам'яті
        audio_buffer = io.BytesIO()
        _, accented_text = tts_model.tts(
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
