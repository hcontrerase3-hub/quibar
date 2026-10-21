"""Spanish speech runs on CPU; no visitor audio/text is persisted."""
from collections import OrderedDict
import io
from pathlib import Path
from threading import Lock
from urllib.request import urlretrieve
import wave

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
import uvicorn

app = FastAPI(docs_url=None, redoc_url=None)
lock = Lock()
voice = None
cache = OrderedDict()
MODEL = 'es_ES-davefx-medium'
ROOT = Path('/models')


def prepare():
    from piper import PiperVoice
    from piper.config import PiperConfig
    from piper.voice import ESPEAK_DATA_DIR
    import onnxruntime
    import json
    onnxruntime.disable_telemetry_events()
    ROOT.mkdir(parents=True, exist_ok=True)
    base = 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/'
    for suffix in ('.onnx', '.onnx.json'):
        target = ROOT / (MODEL + suffix)
        if not target.exists():
            temporary = target.with_suffix(target.suffix + '.part')
            urlretrieve(base + target.name, temporary)
            temporary.replace(target)
    card = ROOT / 'MODEL_CARD'
    if not card.exists():
        urlretrieve(base + 'MODEL_CARD', card)
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return PiperVoice(config=PiperConfig.from_dict(json.loads((ROOT / (MODEL + '.onnx.json')).read_text())),
                      session=onnxruntime.InferenceSession(str(ROOT / (MODEL + '.onnx')), sess_options=options,
                                                         providers=['CPUExecutionProvider']),
                      espeak_data_dir=Path(ESPEAK_DATA_DIR))


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=1200)


@app.get('/health')
def health():
    return {'ready': voice is not None, 'voice': MODEL}


@app.post('/')
def synthesize(data: Speech):
    if voice is None:
        raise HTTPException(503, 'La voz todavía no está preparada')
    if not lock.acquire(blocking=False):
        raise HTTPException(429, 'Voz ocupada')
    try:
        content = cache.get(data.text)
        if content is None:
            output = io.BytesIO()
            with wave.open(output, 'wb') as wav:
                voice.synthesize_wav(data.text, wav)
            content = output.getvalue()
            cache[data.text] = content
            while len(cache) > 12:
                cache.popitem(last=False)
        return Response(content, media_type='audio/wav', headers={'Cache-Control': 'no-store'})
    finally:
        lock.release()


if __name__ == '__main__':
    import threading
    def load():
        global voice
        try:
            voice = prepare()
            print('Voz española local preparada', flush=True)
        except Exception as error:
            print(f'No se pudo preparar la voz: {error}. Reinicia speech para reintentar.', flush=True)
    threading.Thread(target=load, daemon=True).start()
    uvicorn.run(app, host='0.0.0.0', port=5000)
