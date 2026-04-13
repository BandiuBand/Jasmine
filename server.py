from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic import BaseModel
from faster_whisper import WhisperModel
import uvicorn
import tempfile
import os

import torch
print(torch.version.cuda)         # версія CUDA, з якою зібраний PyTorch
print(torch.backends.cudnn.version())  # якщо None – cuDNN не знайдено
print(torch.cuda.is_available())  # має повернути True

app = FastAPI(title="Whisper GPU Server")

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

class TranscriptionResult(BaseModel):
    text: str

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

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8002, log_level="info")
