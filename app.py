import os
import sys
import glob
import json
import time
import base64
import tempfile
import subprocess
import threading
import io
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")
LLAMA_SERVER_EXE = os.path.join(BIN_DIR, "llama-server.exe")
WHISPER_EXE = os.path.join(BIN_DIR, "whisper", "whisper-cli.exe")
PIPER_EXE = os.path.join(BIN_DIR, "piper", "piper.exe")
VOICES_JSON_PATH = os.path.join(BASE_DIR, "voice_models", "voices.json")

# Import EdgeRAG - Lightweight SQLite3 + NumPy Hybrid Vector Database
from rag_engine import EdgeRAG
rag_engine = EdgeRAG()

def load_env():
    env_file = os.path.join(BASE_DIR, ".env.local")
    if not os.path.exists(env_file):
        env_file = os.path.join(BASE_DIR, ".env")
    
    config = {
        "APP_PORT": 3000,
        "LLAMA_PORT": 8080,
        "DEFAULT_MODEL": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "APP_LANGUAGE": "id",
        "TTS_ENGINE": "edge",
        "EDGE_VOICE": "id-ID-GadisNeural",
        "KOKORO_VOICE": "af_heart",
        "VOICE_MODEL": "voice_models/id_ID-news_tts-medium.onnx",
        "VOICE_SPEAKER": 0,
        "VOICE_LENGTH_SCALE": 0.90,
        "VOICE_NOISE_SCALE": 0.75,
        "VOICE_NOISE_W": 0.80,
        "VOICE_SENTENCE_SILENCE": 0.25,
        "WHISPER_MODEL": "voice_models/ggml-small.bin" if os.path.exists(os.path.join(BASE_DIR, "voice_models", "ggml-small.bin")) else "voice_models/ggml-base.bin",
        "WHISPER_LANGUAGE": "id",
        "RAG_ENABLED": 1,
        "RAG_TOP_K": 3
    }

    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.split("#")[0].strip()
                if k in config:
                    if isinstance(config[k], int):
                        try: config[k] = int(v)
                        except: pass
                    elif isinstance(config[k], float):
                        try: config[k] = float(v)
                        except: pass
                    else:
                        config[k] = v
    return config

def save_env_value(key, value):
    env_file = os.path.join(BASE_DIR, ".env.local")
    lines = []
    found = False
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

def save_multiple_env_values(kv_dict):
    for k, v in kv_dict.items():
        save_env_value(k, v)

CONFIG = load_env()
APP_PORT = CONFIG["APP_PORT"]
LLAMA_PORT = CONFIG["LLAMA_PORT"]

current_process = None
current_model_name = None
lock = threading.Lock()

def get_available_models():
    gguf_files = glob.glob(os.path.join(BASE_DIR, "*.gguf"))
    models = []
    for f in gguf_files:
        name = os.path.basename(f)
        if not name.startswith("mmproj-"):
            models.append(name)
    return sorted(models)

def get_voice_catalog():
    if not os.path.exists(VOICES_JSON_PATH):
        return []
    with open(VOICES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    downloaded_files = os.listdir(os.path.join(BASE_DIR, "voice_models")) if os.path.exists(os.path.join(BASE_DIR, "voice_models")) else []
    
    catalog = []
    for key, info in data.items():
        lang_info = info.get("language", {})
        lang_name = lang_info.get("name_english", "Unknown")
        country = lang_info.get("country_english", "")
        code = lang_info.get("code", "")
        fam = code.split("_")[0] if "_" in code else code
        quality = info.get("quality", "medium")
        name = info.get("name", key)
        num_speakers = info.get("num_speakers", 1)
        
        onnx_rel = next((f for f in info.get("files", {}) if f.endswith(".onnx")), None)
        json_rel = next((f for f in info.get("files", {}) if f.endswith(".onnx.json")), None)
        
        filename = os.path.basename(onnx_rel) if onnx_rel else f"{key}.onnx"
        is_downloaded = filename in downloaded_files
        sample_url = f"https://rhasspy.github.io/piper-samples/samples/{fam}/{code}/{name}/{quality}/speaker_0.mp3"
        
        catalog.append({
            "key": key,
            "name": name,
            "filename": f"voice_models/{filename}",
            "language": lang_name,
            "country": country,
            "code": code,
            "family": fam,
            "quality": quality,
            "num_speakers": num_speakers,
            "is_downloaded": is_downloaded,
            "sample_url": sample_url,
            "onnx_url": f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx_rel}" if onnx_rel else None,
            "json_url": f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{json_rel}" if json_rel else None,
        })
    
    def sort_key(item):
        lang = item["language"].lower()
        if "indonesian" in lang: return (0, item["key"])
        if "english" in lang: return (1, item["country"], item["key"])
        if "japanese" in lang: return (2, item["key"])
        if "chinese" in lang: return (3, item["key"])
        if "arabic" in lang: return (4, item["key"])
        if "spanish" in lang: return (5, item["key"])
        if "french" in lang: return (6, item["key"])
        if "german" in lang: return (7, item["key"])
        return (8, item["language"], item["key"])

    return sorted(catalog, key=sort_key)

def download_voice_from_catalog(voice_key):
    if not os.path.exists(VOICES_JSON_PATH):
        raise FileNotFoundError("voices.json tidak ditemukan")
    with open(VOICES_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    entry = data.get(voice_key)
    if not entry:
        raise ValueError(f"Voice key {voice_key} tidak ditemukan di katalog")
    
    onnx_rel = next((f for f in entry.get("files", {}) if f.endswith(".onnx")), None)
    json_rel = next((f for f in entry.get("files", {}) if f.endswith(".onnx.json")), None)
    
    if not onnx_rel:
        raise ValueError("URL file ONNX tidak tersedia")

    onnx_dest = os.path.join(BASE_DIR, "voice_models", os.path.basename(onnx_rel))
    json_dest = os.path.join(BASE_DIR, "voice_models", os.path.basename(json_rel)) if json_rel else None

    if not os.path.exists(onnx_dest):
        url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{onnx_rel}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(onnx_dest, "wb") as f:
            f.write(resp.read())

    if json_dest and not os.path.exists(json_dest):
        url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{json_rel}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
        try:
            jdata = json.loads(content.decode('utf-8'))
            if "phoneme_id_map" in jdata:
                m = jdata["phoneme_id_map"]
                keys_to_remove = [k for k in m if len(k) > 1 and not (k.startswith('^') or k.startswith('$'))]
                for k in keys_to_remove:
                    m.pop(k, None)
            with open(json_dest, "w", encoding="utf-8") as f:
                json.dump(jdata, f, indent=2)
        except Exception:
            with open(json_dest, "wb") as f:
                f.write(content)

    model_rel = f"voice_models/{os.path.basename(onnx_rel)}"
    save_env_value("VOICE_MODEL", model_rel)
    return model_rel

def get_mmproj_for_model(model_name):
    low = model_name.lower()
    if "smol" in low:
        cand = os.path.join(BASE_DIR, "mmproj-SmolVLM-500M-Instruct-Q8_0.gguf")
        if os.path.exists(cand):
            return "mmproj-SmolVLM-500M-Instruct-Q8_0.gguf"
    elif "lfm" in low:
        cand = os.path.join(BASE_DIR, "mmproj-LFM3-Omni-2B-Q8_0.gguf")
        if os.path.exists(cand):
            return "mmproj-LFM3-Omni-2B-Q8_0.gguf"
    return None

def is_multimodal(model_name):
    return get_mmproj_for_model(model_name) is not None

def stop_llama_server():
    global current_process, current_model_name
    with lock:
        if current_process is not None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(current_process.pid)], capture_output=True)
                else:
                    current_process.terminate()
            except Exception as e:
                print("Error stopping process:", e)
            current_process = None
            current_model_name = None
            time.sleep(1)

def start_llama_server(model_name):
    global current_process, current_model_name
    stop_llama_server()
    with lock:
        model_path = os.path.join(BASE_DIR, model_name)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model {model_name} not found")

        cmd = [
            LLAMA_SERVER_EXE,
            "-m", model_path,
            "--host", "127.0.0.1",
            "--port", str(LLAMA_PORT),
            "-c", "4096"
        ]

        mmproj = get_mmproj_for_model(model_name)
        if mmproj:
            cmd.extend(["--mmproj", os.path.join(BASE_DIR, mmproj)])

        if "lfm" in model_name.lower():
            cmd.extend(["--temp", "0.1"])
        else:
            cmd.extend(["--temp", "0.7"])

        print("Starting llama-server:", " ".join(cmd))
        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        current_model_name = model_name

        for _ in range(25):
            time.sleep(0.5)
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{LLAMA_PORT}/health")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                pass

def check_api_auth(headers):
    cfg = load_env()
    api_key = cfg.get("API_KEY") or cfg.get("OPENAI_API_KEY")
    if not api_key:
        return True
    auth = headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:].strip()
        if token == api_key:
            return True
    elif headers.get('X-Api-Key') == api_key:
        return True
    return False

def ensure_model_running(requested_model=None):
    global current_process, current_model_name
    models = get_available_models()
    if not models:
        return False, "Tidak ada model GGUF yang ditemukan di direktori."

    target = None
    if requested_model and requested_model in models:
        target = requested_model
    elif current_model_name and (current_process is not None and current_process.poll() is None):
        target = current_model_name
    else:
        cfg = load_env()
        def_m = cfg.get("DEFAULT_MODEL")
        if def_m in models:
            target = def_m
        else:
            target = models[0]

    is_running = (current_process is not None and current_process.poll() is None)
    if is_running:
        if not requested_model or requested_model not in models or current_model_name == target:
            return True, current_model_name or target

    try:
        start_llama_server(target)
        return True, target
    except Exception as e:
        return False, str(e)

def augment_messages_with_rag(messages, top_k=3, enabled_override=None):
    """
    Mengambil pesan pengguna terakhir, melakukan vector retrieval ke EdgeRAG (SQLite+NumPy),
    dan menyisipkan konteks dokumen ke dalam prompt sebelum dikirim ke LLM.
    """
    cfg = load_env()
    is_enabled = str(cfg.get("RAG_ENABLED", "1")).lower() in ("1", "true", "yes")
    if enabled_override is not None:
        is_enabled = bool(enabled_override)
    
    if not is_enabled:
        return messages, []

    stats = rag_engine.get_stats()
    if stats["total_documents"] == 0:
        return messages, []

    # Cari pesan pengguna (user) terakhir
    user_query = ""
    last_user_idx = -1
    for i in reversed(range(len(messages))):
        msg = messages[i]
        if msg.get('role') == 'user':
            c = msg.get('content')
            if isinstance(c, str):
                user_query = c
            elif isinstance(c, list):
                for part in c:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        user_query += " " + part.get('text', '')
            last_user_idx = i
            break

    user_query = user_query.strip()
    if not user_query or last_user_idx == -1:
        return messages, []

    hits = rag_engine.search(user_query, top_k=top_k, min_similarity=0.12)
    if not hits:
        return messages, []

    context_lines = [
        "=== BASIS PENGETAHUAN LOKAL (RETRIEVED CONTEXT) ===",
        "Gunakan informasi relevan berikut ini dari dokumen internal untuk melengkapi jawaban Anda:"
    ]
    sources = []
    for h in hits:
        pct = int(round(h['score'] * 100))
        sources.append({
            "filename": h['filename'],
            "score": round(h['score'], 3),
            "percent": pct,
            "chunk_id": h['chunk_id'],
            "chunk_index": h['chunk_index']
        })
        context_lines.append(f"\n[Sumber: {h['filename']} (Bagian {h['chunk_index']+1}) | Relevansi: {pct}%]\n{h['content']}")
    context_lines.append("=== AKHIR KONTEKS DOKUMEN ===\n")

    rag_context_text = "\n".join(context_lines)

    augmented_messages = [dict(m) for m in messages]
    target_msg = augmented_messages[last_user_idx]
    orig_content = target_msg.get('content')
    if isinstance(orig_content, str):
        target_msg['content'] = f"{rag_context_text}\n\nPertanyaan Pengguna:\n{orig_content}"
    elif isinstance(orig_content, list):
        target_msg['content'] = [{"type": "text", "text": rag_context_text}] + orig_content

    return augmented_messages, sources

model_download_lock = threading.Lock()
model_download_state = {
    "status": "idle",
    "model_key": "",
    "model_name": "",
    "pct": 0,
    "mb_done": 0,
    "mb_total": 0,
    "error": ""
}

def _bg_download_model(key):
    global model_download_state
    from download_models import download_item, MODEL_CATALOG
    if key not in MODEL_CATALOG:
        with model_download_lock:
            model_download_state["status"] = "error"
            model_download_state["error"] = f"Model {key} tidak ditemukan di katalog"
        return

    with model_download_lock:
        model_download_state["status"] = "downloading"
        model_download_state["model_key"] = key
        model_download_state["model_name"] = MODEL_CATALOG[key]["name"]
        model_download_state["pct"] = 0
        model_download_state["mb_done"] = 0
        model_download_state["mb_total"] = MODEL_CATALOG[key].get("size_mb", 0)
        model_download_state["error"] = ""

    def on_prog(done, total):
        with model_download_lock:
            model_download_state["mb_done"] = round(done / (1024 * 1024), 1)
            model_download_state["mb_total"] = round(total / (1024 * 1024), 1) if total > 0 else model_download_state["mb_total"]
            if total > 0:
                model_download_state["pct"] = round((done / total) * 100, 1)

    try:
        ok = download_item(key, progress_callback=on_prog)
        with model_download_lock:
            if ok:
                model_download_state["status"] = "done"
                model_download_state["pct"] = 100
            else:
                model_download_state["status"] = "error"
                model_download_state["error"] = "Gagal mengunduh file dari Hugging Face"
    except Exception as e:
        with model_download_lock:
            model_download_state["status"] = "error"
            model_download_state["error"] = str(e)

def transcribe_audio(audio_bytes):
    cfg = load_env()
    w_model_rel = cfg.get("WHISPER_MODEL", "voice_models/ggml-small.bin")
    w_model = os.path.join(BASE_DIR, w_model_rel)
    if not os.path.exists(w_model):
        # Fallback ke base jika small tidak ditemukan
        w_model = os.path.join(BASE_DIR, "voice_models", "ggml-base.bin")
    lang = cfg.get("WHISPER_LANGUAGE", "id")

    if not os.path.exists(WHISPER_EXE) or not os.path.exists(w_model):
        return None
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
        in_path = tf.name
        tf.write(audio_bytes)
    try:
        cmd = [WHISPER_EXE, '-m', w_model, '-f', in_path, '-l', lang, '--no-timestamps']
        
        # Initial prompt biasing per bahasa untuk mengunci kosakata & ejaan akurat
        lang_prompts = {
            "id": "Halo, saya sedang berbicara dalam Bahasa Indonesia dengan santai, jelas, dan tata bahasa yang baik.",
            "en": "Hello, this is natural spoken English with clear pronunciation.",
            "ja": "こんにちは、日本語の音声入力です。",
            "zh": "你好，这是中文普通话语音输入。",
            "ar": "مرحباً، هذا تسجيل صوتي باللغة العربية الفصحى.",
            "es": "Hola, esta es una conversación en español con buena pronunciación.",
            "fr": "Bonjour, ceci est un enregistrement vocal en français.",
            "de": "Hallo, dies ist eine Sprachaufnahme auf Deutsch."
        }
        if lang in lang_prompts:
            cmd.extend(['--prompt', lang_prompts[lang]])

        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        lines = [line.strip() for line in res.stdout.split('\n') if line.strip() and not line.startswith('whisper_') and not line.startswith('system_info') and not line.startswith('main:')]
        return ' '.join(lines)
    finally:
        if os.path.exists(in_path):
            os.remove(in_path)

# ========================================================
# TTS ENGINES CATALOGS & HELPERS (Edge-TTS, Kokoro, Piper, Melo)
# ========================================================

EDGE_VOICES_CATALOG = [
    {"key": "id-ID-GadisNeural", "name": "Gadis (ID Perempuan - Super Alami & Ramah) ⭐", "lang": "id", "gender": "Female", "engine": "edge"},
    {"key": "id-ID-ArdiNeural", "name": "Ardi (ID Laki-laki - Formal & Berwibawa)", "lang": "id", "gender": "Male", "engine": "edge"},
    {"key": "en-US-JennyNeural", "name": "Jenny (US Female - Natural Conversational)", "lang": "en", "gender": "Female", "engine": "edge"},
    {"key": "en-US-GuyNeural", "name": "Guy (US Male - Casual & Clear)", "lang": "en", "gender": "Male", "engine": "edge"},
    {"key": "en-US-AriaNeural", "name": "Aria (US Female - Expressive)", "lang": "en", "gender": "Female", "engine": "edge"},
    {"key": "en-GB-SoniaNeural", "name": "Sonia (UK Female - British Elegant)", "lang": "en", "gender": "Female", "engine": "edge"},
    {"key": "ja-JP-NanamiNeural", "name": "Nanami (JA Female - Fluent Anime/Natural)", "lang": "ja", "gender": "Female", "engine": "edge"},
    {"key": "ja-JP-KeitaNeural", "name": "Keita (JA Male - Natural Japanese)", "lang": "ja", "gender": "Male", "engine": "edge"},
    {"key": "zh-CN-XiaoxiaoNeural", "name": "Xiaoxiao (ZH Female - Expressive Mandarin)", "lang": "zh", "gender": "Female", "engine": "edge"},
    {"key": "zh-CN-YunxiNeural", "name": "Yunxi (ZH Male - Natural Mandarin)", "lang": "zh", "gender": "Male", "engine": "edge"},
    {"key": "ar-SA-ZariyahNeural", "name": "Zariyah (AR Female - Modern Arabic)", "lang": "ar", "gender": "Female", "engine": "edge"},
    {"key": "fr-FR-DeniseNeural", "name": "Denise (FR Female - Parisian French)", "lang": "fr", "gender": "Female", "engine": "edge"},
    {"key": "es-ES-ElviraNeural", "name": "Elvira (ES Female - Castilian Spanish)", "lang": "es", "gender": "Female", "engine": "edge"},
    {"key": "de-DE-KatjaNeural", "name": "Katja (DE Female - Standard German)", "lang": "de", "gender": "Female", "engine": "edge"},
    {"key": "ko-KR-SunHiNeural", "name": "Sun-Hi (KO Female - Natural Korean)", "lang": "ko", "gender": "Female", "engine": "edge"}
]

KOKORO_VOICES_CATALOG = [
    {"key": "af_heart", "name": "Heart (US Female - SOTA Studio Top #1 ⭐)", "lang": "en", "gender": "Female", "engine": "kokoro"},
    {"key": "af_bella", "name": "Bella (US Female - Warm & Melodic)", "lang": "en", "gender": "Female", "engine": "kokoro"},
    {"key": "af_nicole", "name": "Nicole (US Female - Clear & Professional)", "lang": "en", "gender": "Female", "engine": "kokoro"},
    {"key": "af_sarah", "name": "Sarah (US Female - Soft Conversational)", "lang": "en", "gender": "Female", "engine": "kokoro"},
    {"key": "af_sky", "name": "Sky (US Female - Bright & Energetic)", "lang": "en", "gender": "Female", "engine": "kokoro"},
    {"key": "am_michael", "name": "Michael (US Male - Deep & Natural)", "lang": "en", "gender": "Male", "engine": "kokoro"},
    {"key": "am_adam", "name": "Adam (US Male - Friendly Conversational)", "lang": "en", "gender": "Male", "engine": "kokoro"},
    {"key": "am_fenrir", "name": "Fenrir (US Male - Deep Cinematic)", "lang": "en", "gender": "Male", "engine": "kokoro"},
    {"key": "bf_emma", "name": "Emma (UK Female - British RP Elegant)", "lang": "en", "gender": "Female", "engine": "kokoro"},
    {"key": "bf_isabella", "name": "Isabella (UK Female - British Warm)", "lang": "en", "gender": "Female", "engine": "kokoro"},
    {"key": "bm_george", "name": "George (UK Male - BBC Broadcast Style)", "lang": "en", "gender": "Male", "engine": "kokoro"},
    {"key": "bm_lewis", "name": "Lewis (UK Male - British Modern)", "lang": "en", "gender": "Male", "engine": "kokoro"},
    {"key": "jf_alpha", "name": "Alpha (JA Female - Japanese Soft)", "lang": "ja", "gender": "Female", "engine": "kokoro"},
    {"key": "jm_kumo", "name": "Kumo (JA Male - Japanese Natural)", "lang": "ja", "gender": "Male", "engine": "kokoro"}
]

MELO_VOICES_CATALOG = [
    {"key": "melo_id_gadis", "name": "Melo-ID (Bahasa Indonesia Alami - Gadis)", "lang": "id", "gender": "Female", "engine": "melo", "ref": "id-ID-GadisNeural"},
    {"key": "melo_en_heart", "name": "Melo-EN (English Studio SOTA - Heart)", "lang": "en", "gender": "Female", "engine": "melo", "ref": "af_heart"},
    {"key": "melo_ja_nanami", "name": "Melo-JA (Japanese Fluent - Nanami)", "lang": "ja", "gender": "Female", "engine": "melo", "ref": "ja-JP-NanamiNeural"},
    {"key": "melo_zh_xiaoxiao", "name": "Melo-ZH (Mandarin Expressive - Xiaoxiao)", "lang": "zh", "gender": "Female", "engine": "melo", "ref": "zh-CN-XiaoxiaoNeural"}
]

EDGE_VOICE_PERSONAS = {
    "female": {
        "id": "id-ID-GadisNeural",
        "en": "en-US-JennyNeural",
        "ja": "ja-JP-NanamiNeural",
        "zh": "zh-CN-XiaoxiaoNeural",
        "ar": "ar-SA-ZariyahNeural",
        "fr": "fr-FR-DeniseNeural",
        "es": "es-ES-ElviraNeural",
        "de": "de-DE-KatjaNeural",
        "ko": "ko-KR-SunHiNeural"
    },
    "male": {
        "id": "id-ID-ArdiNeural",
        "en": "en-US-GuyNeural",
        "ja": "ja-JP-KeitaNeural",
        "zh": "zh-CN-YunxiNeural",
        "ar": "ar-SA-HamedNeural",
        "fr": "fr-FR-HenriNeural",
        "es": "es-ES-AlvaroNeural",
        "de": "de-DE-ConradNeural",
        "ko": "ko-KR-InJoonNeural"
    }
}

KOKORO_VOICE_PERSONAS = {
    "female": {
        "en": "af_heart",
        "ja": "jf_alpha",
        "zh": "zf_xiaobei"
    },
    "male": {
        "en": "am_michael",
        "ja": "jm_kumo",
        "zh": "zm_yunjian"
    }
}

PIPER_VOICE_PERSONAS = {
    "female": {
        "id": "voice_models/id_ID-news_tts-medium.onnx",
        "en": "voice_models/en_US-lessac-medium.onnx",
        "ja": "voice_models/ja_JP-hi_fi_captain-medium.onnx",
        "zh": "voice_models/zh_CN-huayan-medium.onnx"
    },
    "male": {
        "id": "voice_models/id_ID-news_tts-medium.onnx",
        "en": "voice_models/en_US-lessac-medium.onnx",
        "ja": "voice_models/ja_JP-hi_fi_captain-medium.onnx",
        "zh": "voice_models/zh_CN-huayan-medium.onnx"
    }
}

import re

def detect_language(text):
    if not text:
        return 'id'
    # 1. Non-latin script check
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
        return 'ja'
    if re.search(r'[\uac00-\ud7af]', text):
        return 'ko'
    if re.search(r'[\u0600-\u06ff]', text):
        return 'ar'
    if re.search(r'[\u4e00-\u9fff]', text):
        return 'zh'

    # 2. Latin word frequency
    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]{2,}\b', text)]
    if not words:
        return 'id'
    
    id_words = {'yang', 'dan', 'di', 'ini', 'itu', 'dengan', 'untuk', 'tidak', 'adalah', 'pada', 'ke', 'saya', 'kamu', 'anda', 'bisa', 'sudah', 'ada', 'dari', 'dalam', 'akan', 'juga', 'karena', 'oleh', 'seperti', 'halo', 'terima', 'kasih', 'bagaimana', 'apa', 'kita', 'mereka'}
    en_words = {'the', 'and', 'is', 'in', 'to', 'of', 'it', 'you', 'that', 'this', 'with', 'for', 'are', 'have', 'not', 'from', 'be', 'can', 'will', 'as', 'hello', 'how', 'what', 'your', 'about', 'would', 'there', 'their', 'which', 'sure', 'here', 'code', 'please'}
    es_words = {'el', 'la', 'en', 'de', 'que', 'es', 'por', 'con', 'para', 'un', 'una', 'hola', 'como', 'los', 'las'}
    fr_words = {'le', 'la', 'et', 'en', 'dans', 'est', 'pour', 'avec', 'un', 'une', 'bonjour', 'que', 'qui', 'les', 'des'}
    de_words = {'der', 'die', 'das', 'und', 'ist', 'in', 'zu', 'mit', 'fuer', 'für', 'nicht', 'hallo', 'wie', 'eine', 'einer'}

    scores = {
        'id': sum(1 for w in words if w in id_words),
        'en': sum(1 for w in words if w in en_words),
        'es': sum(1 for w in words if w in es_words),
        'fr': sum(1 for w in words if w in fr_words),
        'de': sum(1 for w in words if w in de_words)
    }
    best_lang = max(scores, key=scores.get)
    if scores[best_lang] > 0:
        return best_lang
    return 'en' if any(w in words for w in ['hello', 'hi', 'ok', 'yes', 'no', 'sure']) else 'id'

def get_voice_gender(voice_key):
    if not voice_key:
        return 'female'
    vk = str(voice_key).lower()
    if any(m in vk for m in ['ardi', 'guy', 'keita', 'yunxi', 'michael', 'adam', 'george', 'lewis', 'kumo', 'male', 'henri', 'alvaro', 'conrad', 'injoon']):
        return 'male'
    return 'female'

_KOKORO_INSTANCE = None

def get_kokoro_model():
    global _KOKORO_INSTANCE
    if _KOKORO_INSTANCE is None:
        m_path = os.path.join(BASE_DIR, "voice_models", "kokoro", "kokoro-v1.0.onnx")
        v_path = os.path.join(BASE_DIR, "voice_models", "kokoro", "voices-v1.0.bin")
        if os.path.exists(m_path) and os.path.exists(v_path):
            try:
                from kokoro_onnx import Kokoro
                _KOKORO_INSTANCE = Kokoro(m_path, v_path)
            except Exception as e:
                print(f"[Kokoro] Error loading model: {e}")
    return _KOKORO_INSTANCE

async def _synthesize_edge_tts_async(text, voice="id-ID-GadisNeural", rate_str="+0%"):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate_str)
    bio = io.BytesIO()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            bio.write(chunk["data"])
    return bio.getvalue()

def synthesize_speech(text, custom_params=None):
    cfg = load_env()
    if custom_params:
        for k, v in custom_params.items():
            if v is not None:
                cfg[k] = v

    engine = str(cfg.get("TTS_ENGINE", "edge")).lower()
    auto_adapt = True
    if custom_params and "auto_adapt_lang" in custom_params:
        auto_adapt = bool(custom_params["auto_adapt_lang"])

    detected_lang = detect_language(text) if auto_adapt else cfg.get("APP_LANGUAGE", "id")

    # 1. EDGE-TTS ENGINE
    if engine == "edge":
        voice = cfg.get("EDGE_VOICE", "id-ID-GadisNeural")
        if custom_params and "edge_voice" in custom_params and custom_params["edge_voice"]:
            voice = custom_params["edge_voice"]
        elif custom_params and "voice_model" in custom_params and "Neural" in str(custom_params["voice_model"]):
            voice = custom_params["voice_model"]

        # Otomatis adaptasi bahasa output sambil mempertahankan persona/gender (Pria / Wanita)
        if auto_adapt and detected_lang:
            gender = get_voice_gender(voice)
            persona_map = EDGE_VOICE_PERSONAS.get(gender, EDGE_VOICE_PERSONAS["female"])
            if detected_lang in persona_map:
                voice = persona_map[detected_lang]

        length_scale = float(cfg.get("VOICE_LENGTH_SCALE", 0.90))
        pct = int(round((1.0 - length_scale) * 100))
        rate_str = f"{pct:+d}%" if pct != 0 else "+0%"

        try:
            mp3_bytes = asyncio.run(_synthesize_edge_tts_async(text, voice, rate_str))
            if mp3_bytes and len(mp3_bytes) > 500:
                return mp3_bytes, "audio/mp3", detected_lang, voice
        except Exception as e:
            print(f"[TTS] Edge-TTS error ({e}), falling back to Kokoro/Piper...")
            engine = "kokoro" if os.path.exists(os.path.join(BASE_DIR, "voice_models", "kokoro", "kokoro-v1.0.onnx")) else "piper"

    # 2. KOKORO-82M ENGINE (100% Offline StyleTTS2 SOTA)
    if engine in ("kokoro", "melo"):
        k = get_kokoro_model()
        if k:
            voice = cfg.get("KOKORO_VOICE", "af_heart")
            if custom_params and "kokoro_voice" in custom_params and custom_params["kokoro_voice"]:
                voice = custom_params["kokoro_voice"]
            elif custom_params and "voice_model" in custom_params and str(custom_params["voice_model"]) in k.get_voices():
                voice = custom_params["voice_model"]

            if auto_adapt and detected_lang:
                gender = get_voice_gender(voice)
                kokoro_map = KOKORO_VOICE_PERSONAS.get(gender, KOKORO_VOICE_PERSONAS["female"])
                if detected_lang in kokoro_map:
                    voice = kokoro_map[detected_lang]

            speed = 1.0
            try:
                ls = float(cfg.get("VOICE_LENGTH_SCALE", 0.90))
                speed = max(0.5, min(2.0, 1.0 / ls))
            except:
                pass

            target_l = detected_lang if auto_adapt else cfg.get("APP_LANGUAGE", "id")
            k_lang = "en-us"
            if target_l == "ja": k_lang = "ja"
            elif target_l == "zh": k_lang = "cmn"
            else: k_lang = "en-us"

            try:
                import soundfile as sf
                samples, sample_rate = k.create(text, voice=voice, speed=speed, lang=k_lang)
                bio = io.BytesIO()
                sf.write(bio, samples, sample_rate, format='WAV')
                wav_bytes = bio.getvalue()
                if wav_bytes:
                    return wav_bytes, "audio/wav", detected_lang, voice
            except Exception as ke:
                print(f"[TTS] Kokoro synthesis error ({ke}), falling back to Piper...")

    # 3. PIPER TTS ENGINE (100% Offline Edge Fallback)
    v_model_rel = cfg.get("VOICE_MODEL", "voice_models/id_ID-news_tts-medium.onnx")
    if auto_adapt and detected_lang:
        gender = get_voice_gender(v_model_rel)
        piper_map = PIPER_VOICE_PERSONAS.get(gender, PIPER_VOICE_PERSONAS["female"])
        cand = piper_map.get(detected_lang)
        if cand and os.path.exists(os.path.join(BASE_DIR, cand)):
            v_model_rel = cand

    v_model = os.path.join(BASE_DIR, v_model_rel)
    speaker = str(cfg.get("VOICE_SPEAKER", 0))
    length_scale = str(cfg.get("VOICE_LENGTH_SCALE", 0.90))
    noise_scale = str(cfg.get("VOICE_NOISE_SCALE", 0.75))
    noise_w = str(cfg.get("VOICE_NOISE_W", 0.80))
    silence = str(cfg.get("VOICE_SENTENCE_SILENCE", 0.25))

    if not os.path.exists(PIPER_EXE) or not os.path.exists(v_model):
        return None, "audio/wav", detected_lang, v_model_rel
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
        out_path = tf.name
    try:
        espeak_data = os.path.join(BIN_DIR, "piper", "espeak-ng-data")
        tashkeel_model = os.path.join(BIN_DIR, "piper", "libtashkeel_model.ort")

        cmd = [
            PIPER_EXE,
            '--model', v_model,
            '--output_file', out_path,
            '--speaker', speaker,
            '--length_scale', length_scale,
            '--noise_scale', noise_scale,
            '--noise_w', noise_w,
            '--sentence_silence', silence
        ]
        if os.path.exists(espeak_data):
            cmd.extend(['--espeak_data', espeak_data])
        if os.path.exists(tashkeel_model):
            cmd.extend(['--tashkeel_model', tashkeel_model])

        p = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8'
        )
        p.communicate(input=text)
        with open(out_path, 'rb') as f:
            audio_bytes = f.read()
        return audio_bytes, "audio/wav", detected_lang, v_model_rel
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)

HTML_PAGE = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Edge Studio - Multilingual Voice & LLM</title>
  <style>
    :root {
      --bg-color: #0b0f19;
      --card-bg: #151e32;
      --border-color: #263554;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --purple: #8b5cf6;
      --user-msg: #1d4ed8;
      --bot-msg: #1e293b;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    body {
      background-color: var(--bg-color);
      color: var(--text-main);
      display: flex;
      flex-direction: column;
      height: 100dvh;
      overflow: hidden;
    }

    header {
      background-color: var(--card-bg);
      border-bottom: 1px solid var(--border-color);
      padding: 10px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .brand h1 {
      font-size: 1.02rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 7px;
    }

    .lang-badge {
      background: #1e293b;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 5px 9px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      transition: all 0.2s ease;
    }

    .lang-badge:hover {
      border-color: var(--primary);
    }

    .btn-realtime-nav {
      background: linear-gradient(135deg, #10b981, #059669);
      color: white;
      padding: 5px 10px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.35);
      border: none;
    }

    .btn-realtime-nav:hover {
      opacity: 0.92;
    }

    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 4px 9px;
      border-radius: 9999px;
      font-size: 0.72rem;
      font-weight: 600;
      background-color: rgba(239, 68, 68, 0.2);
      color: var(--danger);
    }

    .status-badge.online {
      background-color: rgba(16, 185, 129, 0.2);
      color: var(--success);
    }

    .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background-color: currentColor;
    }

    .btn-header {
      background: #1e293b;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 5px 10px;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }

    .controls {
      background-color: var(--card-bg);
      border-bottom: 1px solid var(--border-color);
      padding: 8px 14px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      flex-shrink: 0;
    }

    select {
      flex: 1 1 180px;
      background-color: var(--bg-color);
      color: var(--text-main);
      border: 1px solid var(--border-color);
      padding: 7px 10px;
      border-radius: 8px;
      font-size: 0.83rem;
      outline: none;
    }

    .btn-group {
      display: flex;
      gap: 6px;
      align-items: center;
    }

    button {
      cursor: pointer;
      border: none;
      border-radius: 8px;
      padding: 6px 11px;
      font-size: 0.82rem;
      font-weight: 600;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }

    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    .btn-start {
      background-color: var(--primary);
      color: white;
    }
    .btn-stop {
      background-color: var(--danger);
      color: white;
    }

    /* Pengaturan Suara Drawer */
    .settings-panel {
      display: none;
      background-color: #0d1527;
      border-bottom: 1px solid var(--border-color);
      padding: 14px 16px;
      font-size: 0.82rem;
      flex-shrink: 0;
      max-height: 70dvh;
      overflow-y: auto;
    }

    .settings-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    /* Preset Profil Hardware */
    .preset-cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 8px;
      margin-bottom: 8px;
    }

    .preset-card {
      background: #0f172a;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 8px 10px;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }

    .preset-card:hover {
      border-color: var(--primary);
      transform: translateY(-1px);
    }

    .preset-card.active {
      border-color: #10b981;
      background: rgba(16, 185, 129, 0.12);
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.25);
    }

    .preset-card-title {
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--text-main);
    }

    .preset-card-desc {
      font-size: 0.69rem;
      color: var(--text-muted);
      line-height: 1.25;
    }

    .preset-card-stats {
      margin-top: 4px;
      display: flex;
      justify-content: space-between;
      font-size: 0.68rem;
      color: #cbd5e1;
      border-top: 1px dashed rgba(255, 255, 255, 0.1);
      padding-top: 3px;
    }

    .resource-meter-box {
      background: rgba(15, 23, 42, 0.8);
      border-radius: 6px;
      padding: 6px 10px;
      border: 1px solid var(--border-color);
    }

    /* Multilingual Pills Container */
    .lang-pills-scroll {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 6px;
      margin-bottom: 8px;
      -webkit-overflow-scrolling: touch;
    }

    .lang-pills-scroll::-webkit-scrollbar {
      height: 4px;
    }
    .lang-pills-scroll::-webkit-scrollbar-thumb {
      background: var(--border-color);
      border-radius: 4px;
    }

    .lang-pill-btn {
      flex: 0 0 auto;
      background: #1e293b;
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 5px 11px;
      border-radius: 20px;
      font-size: 0.77rem;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      white-space: nowrap;
    }

    .lang-pill-btn.active {
      background: var(--primary);
      color: white;
      border-color: #60a5fa;
    }

    .lang-info-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      padding: 6px 10px;
      background: rgba(30, 41, 59, 0.4);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      margin-bottom: 12px;
      font-size: 0.73rem;
      color: var(--text-muted);
    }

    .voice-action-bar {
      background: rgba(30, 41, 59, 0.7);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 8px 12px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }

    .btn-preview-online {
      background-color: #6366f1;
      color: white;
      padding: 5px 11px;
      font-size: 0.76rem;
    }

    .btn-download-voice {
      background-color: var(--primary);
      color: white;
      padding: 5px 11px;
      font-size: 0.76rem;
    }

    .preset-chips {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }

    .chip-btn {
      background: #1e293b;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 0.72rem;
      font-weight: 600;
      cursor: pointer;
    }

    .settings-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }

    .setting-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .setting-label {
      color: var(--text-muted);
      font-size: 0.75rem;
      display: flex;
      justify-content: space-between;
    }

    input[type=range] {
      width: 100%;
      accent-color: var(--primary);
    }

    .test-box-area {
      background: rgba(15, 23, 42, 0.7);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 12px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .test-input {
      background: #0b0f19;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 7px 10px;
      border-radius: 6px;
      font-size: 0.82rem;
      width: 100%;
      outline: none;
    }

    .btn-test-voice {
      background-color: #10b981;
      color: white;
      padding: 7px 14px;
      font-size: 0.8rem;
    }

    /* Chat Area */
    .chat-container {
      flex: 1;
      overflow-y: auto;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      -webkit-overflow-scrolling: touch;
    }

    .message {
      max-width: 88%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 0.92rem;
      line-height: 1.45;
      word-break: break-word;
      white-space: pre-wrap;
    }

    .message.user {
      align-self: flex-end;
      background-color: var(--user-msg);
      color: white;
      border-bottom-right-radius: 2px;
    }

    .message.assistant {
      align-self: flex-start;
      background-color: var(--bot-msg);
      color: var(--text-main);
      border-bottom-left-radius: 2px;
      border: 1px solid var(--border-color);
    }

    .message.system {
      align-self: center;
      background-color: transparent;
      color: var(--text-muted);
      font-size: 0.78rem;
      text-align: center;
    }

    .message-img {
      max-width: 100%;
      max-height: 200px;
      border-radius: 8px;
      margin-bottom: 8px;
      display: block;
    }

    .msg-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-top: 6px;
    }

    .speed-tag {
      font-size: 0.7rem;
      color: var(--text-muted);
    }

    .btn-audio-replay {
      background: rgba(255, 255, 255, 0.1);
      color: var(--text-main);
      border-radius: 6px;
      padding: 2px 7px;
      font-size: 0.75rem;
      cursor: pointer;
    }

    .recording-bar {
      display: none;
      background-color: rgba(239, 68, 68, 0.15);
      border-top: 1px solid rgba(239, 68, 68, 0.4);
      padding: 8px 14px;
      align-items: center;
      justify-content: space-between;
      color: var(--danger);
      font-size: 0.85rem;
      font-weight: 600;
    }

    .rec-pulse {
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--danger);
      animation: pulse 1s infinite alternate;
    }

    @keyframes pulse {
      from { opacity: 0.3; transform: scale(0.9); }
      to { opacity: 1; transform: scale(1.2); }
    }

    .preview-bar {
      display: none;
      background-color: var(--card-bg);
      border-top: 1px solid var(--border-color);
      padding: 8px 14px;
      align-items: center;
      gap: 10px;
    }

    .preview-container {
      position: relative;
      display: inline-block;
    }

    .preview-thumb {
      width: 46px;
      height: 46px;
      object-fit: cover;
      border-radius: 6px;
      border: 1px solid var(--primary);
    }

    .btn-remove-img {
      position: absolute;
      top: -6px;
      right: -6px;
      background: var(--danger);
      color: white;
      border-radius: 50%;
      width: 18px;
      height: 18px;
      font-size: 11px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      cursor: pointer;
    }

    .input-bar {
      background-color: var(--card-bg);
      border-top: 1px solid var(--border-color);
      padding: 8px 12px;
      display: flex;
      gap: 7px;
      align-items: center;
      flex-shrink: 0;
    }

    textarea {
      flex: 1;
      background-color: var(--bg-color);
      color: var(--text-main);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 9px 12px;
      font-size: 0.95rem;
      resize: none;
      height: 40px;
      max-height: 110px;
      outline: none;
    }

    textarea:focus {
      border-color: var(--primary);
    }

    .btn-action {
      background-color: #334155;
      color: white;
      height: 40px;
      width: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      flex-shrink: 0;
      font-size: 1.1rem;
    }

    .btn-realtime-action {
      background: linear-gradient(135deg, #10b981, #059669);
      color: white;
      height: 40px;
      padding: 0 11px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 5px;
      font-size: 0.8rem;
      font-weight: 700;
      flex-shrink: 0;
      white-space: nowrap;
    }

    .btn-realtime-action:hover {
      filter: brightness(1.1);
    }

    .btn-mic.recording {
      background-color: var(--danger) !important;
      animation: pulse 1s infinite alternate;
    }

    .btn-send {
      background-color: var(--primary);
      color: white;
      height: 40px;
      width: 40px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      flex-shrink: 0;
      font-size: 1.1rem;
    }

    /* REALTIME HANDS-FREE VOICE OVERLAY / ROOM */
    .realtime-modal {
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100dvh;
      background: rgba(11, 15, 25, 0.95);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      z-index: 1000;
      flex-direction: column;
      align-items: center;
      justify-content: space-between;
      padding: 20px 16px;
      box-sizing: border-box;
    }

    .rt-header {
      width: 100%;
      max-width: 480px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
    }

    .rt-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 20px;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: var(--success);
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }

    /* Switch Toggle for Auto-Sela (Barge-in) */
    .rt-toggle-group {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: rgba(30, 41, 59, 0.6);
      padding: 5px 10px;
      border-radius: 20px;
      border: 1px solid var(--border-color);
    }

    .switch-toggle {
      position: relative;
      display: inline-block;
      width: 36px;
      height: 20px;
    }

    .switch-toggle input {
      opacity: 0;
      width: 0;
      height: 0;
    }

    .slider-toggle {
      position: absolute;
      cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: #334155;
      transition: .25s;
      border-radius: 20px;
    }

    .slider-toggle:before {
      position: absolute;
      content: "";
      height: 14px;
      width: 14px;
      left: 3px;
      bottom: 3px;
      background-color: white;
      transition: .25s;
      border-radius: 50%;
    }

    input:checked + .slider-toggle {
      background-color: #10b981;
    }

    input:checked + .slider-toggle:before {
      transform: translateX(16px);
    }

    .rt-center-stage {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 18px;
      width: 100%;
      max-width: 480px;
    }

    /* The Animated Pulsing Glowing Voice Orb */
    .orb-wrapper {
      position: relative;
      width: 140px;
      height: 140px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .orb-ring {
      position: absolute;
      width: 100%;
      height: 100%;
      border-radius: 50%;
      border: 2px solid rgba(59, 130, 246, 0.4);
      animation: ringPulse 2.4s infinite ease-out;
    }

    @keyframes ringPulse {
      0% { transform: scale(0.9); opacity: 0.8; }
      100% { transform: scale(1.6); opacity: 0; }
    }

    .voice-orb {
      width: 96px;
      height: 96px;
      border-radius: 50%;
      background: radial-gradient(circle at 35% 35%, #60a5fa, #1d4ed8 75%);
      box-shadow: 0 0 35px rgba(59, 130, 246, 0.65), inset 0 0 15px rgba(255, 255, 255, 0.4);
      transition: all 0.15s ease-out;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 2.2rem;
      user-select: none;
      cursor: pointer;
    }

    .voice-orb.listening {
      background: radial-gradient(circle at 35% 35%, #34d399, #059669 75%);
      box-shadow: 0 0 35px rgba(16, 185, 129, 0.7), inset 0 0 15px rgba(255, 255, 255, 0.4);
    }

    .voice-orb.processing {
      background: radial-gradient(circle at 35% 35%, #fbbf24, #d97706 75%);
      box-shadow: 0 0 35px rgba(245, 158, 11, 0.75), inset 0 0 15px rgba(255, 255, 255, 0.4);
      animation: orbSpin 2s infinite linear;
    }

    @keyframes orbSpin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .voice-orb.speaking {
      background: radial-gradient(circle at 35% 35%, #c084fc, #7e22ce 75%);
      box-shadow: 0 0 40px rgba(168, 85, 247, 0.85), inset 0 0 15px rgba(255, 255, 255, 0.4);
      animation: speakingPulse 1.2s infinite alternate ease-in-out;
    }

    @keyframes speakingPulse {
      0% { transform: scale(0.96); box-shadow: 0 0 25px rgba(168, 85, 247, 0.6); }
      100% { transform: scale(1.12); box-shadow: 0 0 50px rgba(168, 85, 247, 0.95); }
    }

    .rt-status-text {
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--text-main);
      text-align: center;
      min-height: 28px;
    }

    .rt-substatus {
      font-size: 0.8rem;
      color: var(--text-muted);
      text-align: center;
    }

    /* Live Transcription Box */
    .rt-live-box {
      width: 100%;
      background: rgba(30, 41, 59, 0.6);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 12px 14px;
      max-height: 160px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
      font-size: 0.86rem;
    }

    .rt-bubble {
      padding: 8px 12px;
      border-radius: 8px;
      line-height: 1.4;
      word-break: break-word;
    }
    .rt-bubble.user {
      background: var(--user-msg);
      color: white;
      align-self: flex-end;
    }
    .rt-bubble.ai {
      background: #1e293b;
      color: var(--text-main);
      border: 1px solid var(--border-color);
      align-self: flex-start;
    }

    .rt-footer-controls {
      width: 100%;
      max-width: 480px;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 10px;
    }

    .btn-rt-interrupt {
      background: linear-gradient(135deg, #f59e0b, #d97706);
      color: white;
      padding: 10px 22px;
      border-radius: 24px;
      font-size: 0.88rem;
      font-weight: 700;
      box-shadow: 0 4px 14px rgba(245, 158, 11, 0.4);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .btn-rt-exit {
      background-color: #334155;
      color: white;
      padding: 10px 20px;
      border-radius: 24px;
      font-size: 0.88rem;
      font-weight: 700;
    }

    /* OPENAI API & AI AGENTS MODAL STYLES */
    .btn-api-nav {
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(168, 85, 247, 0.25));
      border: 1px solid rgba(168, 85, 247, 0.6);
      color: #c084fc;
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 0.77rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
    }
    .btn-api-nav:hover {
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(168, 85, 247, 0.4));
      color: #f3e8ff;
      border-color: #d8b4fe;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(168, 85, 247, 0.25);
    }
    .api-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(11, 15, 25, 0.85);
      backdrop-filter: blur(8px);
      z-index: 1000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .api-modal-content {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      width: 100%;
      max-width: 680px;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
      display: flex;
      flex-direction: column;
    }
    .api-modal-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      background: var(--card-bg);
      z-index: 10;
    }
    .api-modal-header h3 {
      margin: 0;
      font-size: 1.05rem;
      display: flex;
      align-items: center;
      gap: 8px;
      color: #f1f5f9;
    }
    .api-modal-close {
      background: #1e293b;
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      border-radius: 8px;
      padding: 4px 10px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
    }
    .api-modal-close:hover {
      color: white;
      background: #334155;
    }
    .api-modal-body {
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .api-endpoint-card {
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .api-endpoint-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      flex-wrap: wrap;
    }
    .api-endpoint-badge {
      background: #0284c7;
      color: white;
      font-size: 0.68rem;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 4px;
      letter-spacing: 0.5px;
    }
    .api-endpoint-url {
      font-family: monospace;
      font-size: 0.82rem;
      color: #38bdf8;
      background: #0b1329;
      padding: 4px 8px;
      border-radius: 6px;
      border: 1px solid #1e293b;
      flex: 1;
      overflow-x: auto;
    }
    .btn-copy-chip {
      background: #1e293b;
      border: 1px solid var(--border-color);
      color: #94a3b8;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .btn-copy-chip:hover {
      background: #334155;
      color: white;
    }
    .api-tabs-nav {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 6px;
      margin-top: 4px;
      -webkit-overflow-scrolling: touch;
    }
    .api-tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    .api-tab-btn.active {
      background: #1e293b;
      color: #38bdf8;
      border-bottom: 2px solid #38bdf8;
    }
    .api-code-block {
      position: relative;
      background: #090d16;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 12px;
      overflow-x: auto;
    }
    .api-code-block pre {
      margin: 0;
      font-family: 'Consolas', 'Courier New', monospace;
      font-size: 0.77rem;
      color: #e2e8f0;
      line-height: 1.45;
    }
    .api-code-copy-btn {
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid var(--border-color);
      color: #94a3b8;
      font-size: 0.7rem;
      padding: 3px 8px;
      border-radius: 4px;
      cursor: pointer;
    }
    .api-code-copy-btn:hover {
      background: #334155;
      color: white;
    }

    /* RAG KNOWLEDGE BASE STYLES */
    .btn-rag-nav {
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.22), rgba(6, 182, 212, 0.22));
      border: 1px solid rgba(16, 185, 129, 0.55);
      color: #34d399;
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 0.77rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s ease;
    }
    .btn-rag-nav:hover {
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.38), rgba(6, 182, 212, 0.38));
      color: #a7f3d0;
      border-color: #6ee7b7;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25);
    }
    .btn-rag-toggle {
      background: #1e293b;
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 0 10px;
      height: 38px;
      border-radius: 8px;
      font-size: 0.76rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      white-space: nowrap;
      transition: all 0.2s ease;
    }
    .btn-rag-toggle.active {
      background: rgba(16, 185, 129, 0.2);
      border-color: #10b981;
      color: #34d399;
    }
    .rag-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(11, 15, 25, 0.85);
      backdrop-filter: blur(8px);
      z-index: 1000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .rag-modal-content {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      width: 100%;
      max-width: 680px;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
      display: flex;
      flex-direction: column;
    }
    .rag-dropzone {
      border: 2px dashed #334155;
      border-radius: 12px;
      padding: 20px 16px;
      text-align: center;
      background: rgba(15, 23, 42, 0.5);
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .rag-dropzone:hover, .rag-dropzone.dragover {
      border-color: #10b981;
      background: rgba(16, 185, 129, 0.08);
    }
    .rag-doc-card {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      gap: 10px;
      transition: border-color 0.2s ease;
    }
    .rag-doc-card:hover {
      border-color: #3b82f6;
    }
    .rag-badge-ext {
      font-size: 0.66rem;
      padding: 2px 6px;
      border-radius: 4px;
      background: #0284c7;
      color: white;
      font-weight: 700;
      text-transform: uppercase;
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <span style="font-size: 1.25rem;">🌐</span>
      <div>
        <h1>Edge Studio</h1>
        <div id="subTitle" style="font-size: 0.7rem; color: var(--text-muted);">Multilingual Voice & Realtime Studio</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn-rag-nav" onclick="openRagModal()" title="Kelola Basis Pengetahuan Dokumen (RAG)">
        📚 Dokumen RAG
      </button>
      <button class="btn-api-nav" onclick="openApiModal()" title="Panduan OpenAI-Compatible API untuk AI Agents">
        🔌 OpenAI API
      </button>
      <button class="btn-realtime-nav" onclick="openRealtimeVoiceModal()" title="Mode Hands-Free Suara Otomatis">
        ⚡ Realtime Voice
      </button>
      <button id="btnHeaderLang" class="lang-badge" onclick="toggleSettingsPanel()">🇮🇩 ID</button>
      <button class="btn-header" onclick="toggleSettingsPanel()">🎛️ Pengaturan</button>
      <div id="statusBadge" class="status-badge">
        <div class="dot"></div>
        <span id="statusText">STOPPED</span>
      </div>
    </div>
  </header>

  <section class="controls">
    <select id="modelSelect"></select>
    <div class="btn-group">
      <button id="btnStart" class="btn-start" onclick="handleStart()">▶ Jalankan</button>
      <button id="btnStop" class="btn-stop" onclick="handleStop()" disabled>⏹ Stop</button>
    </div>
  </section>

  <!-- PENGATURAN SUARA & MULTILINGUAL DRAWER -->
  <section id="settingsPanel" class="settings-panel">
    <div class="settings-header">
      <div style="font-weight: 700; color: var(--text-main);">🎛️ Pengaturan Sistem & Suara (.env.local)</div>
      <span id="savedIndicator" style="font-size: 0.72rem; color: var(--success); font-weight: 600;">✓ Tersinkron</span>
    </div>

    <!-- PRESET PROFIL PERANGKAT (HARDWARE RESOURCE PROFILES) -->
    <div class="setting-item" style="margin-bottom: 12px; background: rgba(30, 41, 59, 0.45); padding: 10px; border-radius: 8px; border: 1px solid var(--border-color);">
      <div class="setting-label" style="margin-bottom: 5px;">
        <span style="font-weight: 700; color: #60a5fa;">⚡ Profil Hardware (RAM & Penyimpanan)</span>
        <span id="activePresetBadge" style="font-size: 0.72rem; color: #10b981; font-weight: 700;">⚖️ Balanced ⭐</span>
      </div>
      <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 8px;">
        Pilih preset optimal sesuai kapasitas RAM komputer/laptop Anda:
      </div>

      <!-- Grid Cards Preset -->
      <div class="preset-cards-grid">
        <div class="preset-card" id="cardPresetUltraLight" onclick="applyHardwarePreset('ultra_light')">
          <div class="preset-card-title">🪶 Ultra-Light</div>
          <div class="preset-card-desc">Qwen 0.5B + Whisper Base + Piper</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~1.15 GB</b></span>
            <span>Disk: <b>~780 MB</b></span>
          </div>
        </div>

        <div class="preset-card" id="cardPresetBalanced" onclick="applyHardwarePreset('balanced')">
          <div class="preset-card-title">⚖️ Balanced Pro ⭐</div>
          <div class="preset-card-desc">Qwen 0.5B + Whisper Small + Piper</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~1.75 GB</b></span>
            <span>Disk: <b>~1.10 GB</b></span>
          </div>
        </div>

        <div class="preset-card" id="cardPresetKokoro" onclick="applyHardwarePreset('kokoro_studio')">
          <div class="preset-card-title">🌸 Kokoro Studio</div>
          <div class="preset-card-desc">Qwen 0.5B + Small + Kokoro-82M</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~1.95 GB</b></span>
            <span>Disk: <b>~1.45 GB</b></span>
          </div>
        </div>

        <div class="preset-card active" id="cardPresetEdge" onclick="applyHardwarePreset('edge_natural')">
          <div class="preset-card-title">🌐 Edge Natural</div>
          <div class="preset-card-desc">Qwen 0.5B + Small + Edge Gadis</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~1.75 GB</b></span>
            <span>Disk: <b>~1.10 GB</b></span>
          </div>
        </div>

        <div class="preset-card" id="cardPresetVision" onclick="applyHardwarePreset('vision')">
          <div class="preset-card-title">👁️ Vision Studio</div>
          <div class="preset-card-desc">SmolVLM 500M + Small + Edge/Piper</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~2.00 GB</b></span>
            <span>Disk: <b>~1.35 GB</b></span>
          </div>
        </div>

        <div class="preset-card" id="cardPresetMax" onclick="applyHardwarePreset('max')">
          <div class="preset-card-title">🧠 Max Omni 2B</div>
          <div class="preset-card-desc">LFM3 Omni 2B + Small + Kokoro/Edge</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~3.45 GB</b></span>
            <span>Disk: <b>~2.55 GB</b></span>
          </div>
        </div>

        <div class="preset-card" id="cardPresetAgenticFast" onclick="applyHardwarePreset('agentic_fast')">
          <div class="preset-card-title" style="color: #38bdf8;">🤖 Agentic Fast (3B) ⭐</div>
          <div class="preset-card-desc">Qwen 2.5 3B + Small + Edge (Function Calling)</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~3.80 GB</b></span>
            <span>Disk: <b>~2.60 GB</b></span>
          </div>
        </div>

        <div class="preset-card" id="cardPresetAgenticPro" onclick="applyHardwarePreset('agentic_pro')">
          <div class="preset-card-title" style="color: #a855f7;">👑 Agentic Pro (7B)</div>
          <div class="preset-card-desc">Qwen 2.5 7B + Small + Edge (Advanced Chains)</div>
          <div class="preset-card-stats">
            <span>RAM: <b>~6.80 GB</b></span>
            <span>Disk: <b>~5.20 GB</b></span>
          </div>
        </div>
      </div>

      <!-- Meteran Resource Live Status -->
      <div class="resource-meter-box">
        <div style="display: flex; justify-content: space-between; font-size: 0.73rem; flex-wrap: wrap; gap: 4px;">
          <span>Perkiraan Total RAM Aktif: <b id="statRamActive" style="color: #34d399;">~1.75 GB</b></span>
          <span>Penyimpanan Model Dipakai: <b id="statDiskActive" style="color: #60a5fa;">~1.10 GB</b></span>
        </div>
        <div style="font-size: 0.70rem; color: #94a3b8; margin-top: 3px; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 4px;">
          <span>Engine Suara: <b id="statTtsEngineActive" style="color: #38bdf8;">🌐 Edge-TTS (Gadis)</b></span>
          <span>Preset: <b id="activePresetBadge" style="color: #10b981; font-weight: 700;">🌐 Edge Natural</b></span>
        </div>
      </div>

      <!-- Banner Download Model Progress (Muncul dinamis saat unduh) -->
      <div id="modelDownloadProgressBox" style="display: none; margin-top: 10px; background: rgba(15, 23, 42, 0.9); border: 1px solid #38bdf8; border-radius: 8px; padding: 10px 12px;">
        <div style="display: flex; justify-content: space-between; font-size: 0.76rem; font-weight: 700; color: #38bdf8; margin-bottom: 6px;">
          <span id="dlModelTitle">Mengunduh Model...</span>
          <span id="dlModelPercent">0%</span>
        </div>
        <div style="width: 100%; height: 6px; background: #1e293b; border-radius: 4px; overflow: hidden; margin-bottom: 5px;">
          <div id="dlModelProgressBar" style="width: 0%; height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8); transition: width 0.2s ease;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.70rem; color: #94a3b8;">
          <span id="dlModelMb">0 / 0 MB</span>
          <span id="dlModelSpeed">Mengambil langsung dari Hugging Face Hub...</span>
        </div>
      </div>
    </div>

    <!-- Pilihan Bahasa Terpadu (Multilingual Selector) -->
    <div class="setting-item" style="margin-bottom: 8px;">
      <div class="setting-label"><span>Pilih Bahasa Sistem (LLM + Whisper STT + Suara TTS)</span></div>
      
      <!-- Scrollable Quick Pills for Mobile -->
      <div class="lang-pills-scroll" id="langPills"></div>

      <!-- Full Dropdown Language Selector -->
      <select id="langSelect" style="width: 100%; margin-bottom: 6px;" onchange="switchLanguage(this.value)"></select>

      <!-- Sync Status Info -->
      <div class="lang-info-bar">
        <span>Whisper STT: <b id="infoWhisperLang" style="color: #60a5fa;">id</b></span>
        <span>LLM System: <b id="infoLLMLang" style="color: #34d399;">Bahasa Indonesia</b></span>
        <span>Mesin TTS: <b id="infoTtsEngine" style="color: #f59e0b;">Edge-TTS</b></span>
      </div>

      <!-- Auto-Adapt Bahasa Balasan AI Switch -->
      <div style="margin-top: 4px; padding: 7px 10px; background: rgba(56, 189, 248, 0.08); border: 1px dashed rgba(56, 189, 248, 0.35); border-radius: 8px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <div style="flex: 1;">
          <div style="font-size: 0.74rem; font-weight: 700; color: #38bdf8;">🌐 Auto-Adapt Bahasa Balasan AI</div>
          <div style="font-size: 0.68rem; color: var(--text-muted); line-height: 1.25;">Suara otomatis berbicara bahasa Inggris/Jepang/dll sesuai teks balasan AI, tetap menjaga karakter suara Anda (wanita/pria).</div>
        </div>
        <button id="btnAutoLangAdapt" onclick="toggleAutoLangAdapt()" style="padding: 5px 10px; font-size: 0.73rem; font-weight: 700; border-radius: 6px; background: #10b981; color: white; white-space: nowrap; flex-shrink: 0; cursor: pointer; border: none;">ON (Aktif)</button>
      </div>
    </div>

    <!-- Pilihan Mesin Suara (TTS Engine) -->
    <div class="setting-item" style="margin-bottom: 8px;">
      <div class="setting-label">
        <span>Mesin Sintesis Suara (TTS Engine)</span>
        <span id="ttsEngineBadge" style="font-size: 0.72rem; color: #38bdf8; font-weight: 600;">🌐 Sangat Alami</span>
      </div>
      <select id="ttsEngineSelect" style="width: 100%;" onchange="onTtsEngineChange(this.value)">
        <option value="edge">🌐 Edge-TTS — Suara Super Alami (Gadis/Ardi, Cloud Hybrid, 0 MB Disk) ⭐</option>
        <option value="kokoro">🌸 Kokoro-82M — Studio SOTA Natural (StyleTTS2, 100% Offline, ~337MB)</option>
        <option value="piper">⚡ Piper TTS — Ultra Cepat & Ringan (180+ Karakter, 100% Offline, ~60MB)</option>
        <option value="melo">🎙️ MeloTTS Mode — Multilingual Neural Expressive</option>
      </select>
    </div>

    <!-- Pilihan Model Suara -->
    <div class="setting-item" style="margin-bottom: 8px;">
      <div class="setting-label">
        <span id="labelVoiceModel">Karakter Model Suara</span>
        <span id="voiceStatusBadge" style="font-size: 0.72rem; color: var(--success);">✓ Siap</span>
      </div>
      <select id="voiceModelSelect" style="width: 100%;" onchange="onVoiceSelectionChange(this.value)"></select>
    </div>

    <!-- Pilihan Model Pengenal Suara (Whisper STT) -->
    <div class="setting-item" style="margin-bottom: 8px;">
      <div class="setting-label">
        <span>Model Pengenal Suara (Whisper STT)</span>
        <span id="whisperBadge" style="font-size: 0.72rem; color: #10b981; font-weight: 600;">⭐ Akurasi Tinggi</span>
      </div>
      <select id="whisperModelSelect" style="width: 100%;" onchange="onWhisperModelChange(this.value)">
        <option value="voice_models/ggml-small.bin">⭐ Whisper Small (465MB) — Akurasi Tinggi Bahasa Indonesia (Rekomendasi)</option>
        <option value="voice_models/ggml-base.bin">⚡ Whisper Base (148MB) — Lebih Cepat & Hemat RAM</option>
      </select>
    </div>

    <!-- Bar Aksi Suara -->
    <div class="voice-action-bar">
      <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
        <button id="btnOnlineSample" class="btn-preview-online" onclick="playOnlineSample()">🎧 Dengar Rekaman Contoh</button>
        <button id="btnDownloadVoice" class="btn-download-voice" onclick="downloadSelectedVoice()" style="display: none;">⬇️ Unduh 1-Klik (~60MB)</button>
      </div>
      <span id="voiceDownloadNotice" style="font-size: 0.72rem; color: var(--text-muted);">Diuji lokal di bawah</span>
    </div>

    <!-- Preset Cepat -->
    <div style="font-size: 0.72rem; color: var(--text-muted); margin-bottom: 4px;">Preset Karakter Ekspresi:</div>
    <div class="preset-chips">
      <button class="chip-btn" onclick="applyPreset(1.0, 0.35, 0.80, 0.25)">📢 Berita / Tegas</button>
      <button class="chip-btn" onclick="applyPreset(0.90, 0.75, 0.80, 0.25)">✨ Santai & Natural</button>
      <button class="chip-btn" onclick="applyPreset(0.75, 0.90, 0.85, 0.20)">⚡ Cepat & Ceria</button>
      <button class="chip-btn" onclick="applyPreset(1.20, 0.70, 0.75, 0.40)">🧘 Tenang & Lambat</button>
    </div>

    <!-- Sliders -->
    <div class="settings-grid">
      <div class="setting-item">
        <div class="setting-label">
          <span>🏃 Kecepatan Bicara (Tempo)</span>
          <span id="valSpeed">0.90x</span>
        </div>
        <input type="range" id="sliderSpeed" min="0.60" max="1.50" step="0.05" value="0.90" oninput="onSliderChange('VOICE_LENGTH_SCALE', this.value, 'valSpeed', this.value + 'x')">
      </div>

      <div class="setting-item">
        <div class="setting-label">
          <span>🎭 Dinamika Ekspresi / Intonasi</span>
          <span id="valExpr">0.75</span>
        </div>
        <input type="range" id="sliderExpr" min="0.20" max="0.95" step="0.05" value="0.75" oninput="onSliderChange('VOICE_NOISE_SCALE', this.value, 'valExpr', this.value)">
      </div>

      <div class="setting-item">
        <div class="setting-label">
          <span>🎵 Ritme Penekanan Suku Kata</span>
          <span id="valNoiseW">0.80</span>
        </div>
        <input type="range" id="sliderNoiseW" min="0.50" max="1.0" step="0.05" value="0.80" oninput="onSliderChange('VOICE_NOISE_W', this.value, 'valNoiseW', this.value)">
      </div>

      <div class="setting-item">
        <div class="setting-label">
          <span>⏸️ Jeda Nafas Antar Kalimat</span>
          <span id="valSilence">0.25s</span>
        </div>
        <input type="range" id="sliderSilence" min="0.10" max="0.60" step="0.05" value="0.25" oninput="onSliderChange('VOICE_SENTENCE_SILENCE', this.value, 'valSilence', this.value + 's')">
      </div>
    </div>

    <!-- Kotak Uji Suara Dinamis -->
    <div class="test-box-area">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 600; font-size: 0.78rem;">🔊 Uji Suara Langsung (Sesuai Slider):</span>
      </div>
      <input type="text" id="testSentenceInput" class="test-input" value="Halo, ini adalah pengujian suara lokal dengan setelan slider Anda.">
      <button id="btnTestLocal" class="btn-test-voice" onclick="testCurrentVoice()" style="align-self: flex-start;">
        ▶ Bunyikan Suara Sekarang
      </button>
    </div>
  </section>

  <main class="chat-container" id="chatContainer">
    <div id="welcomeMessage" class="message system">
      💡 <b>Tips:</b> Anda bisa mengetik biasa, gunakan tombol 🎙️ (Push-to-Talk), atau aktifkan tombol hijau <b>⚡ Realtime Voice</b> untuk berbicara hands-free secara otomatis dengan dukungan sela bicara (barge-in)!
    </div>
  </main>

  <div id="recordingBar" class="recording-bar">
    <div style="display: flex; align-items: center; gap: 8px;">
      <div class="rec-pulse"></div>
      <span id="recordingStatus">Mendengarkan... Silakan berbicara.</span>
    </div>
    <button class="btn-stop" style="padding: 4px 10px; font-size: 0.75rem;" onclick="stopVoiceRecording()">Kirim Suara ✓</button>
  </div>

  <div id="previewBar" class="preview-bar">
    <div class="preview-container">
      <img id="previewImg" class="preview-thumb" src="">
      <div class="btn-remove-img" onclick="clearAttachedImage()">×</div>
    </div>
    <span style="font-size: 0.78rem; color: var(--text-muted);">Gambar terlampir</span>
  </div>

  <footer class="input-bar">
    <button class="btn-realtime-action" onclick="openRealtimeVoiceModal()" title="Buka Mode Percakapan Realtime">
      ⚡ Hands-Free
    </button>
    <button id="btnToggleRagChat" class="btn-rag-toggle active" onclick="toggleRagActiveChat()" title="Pencarian Cerdas Dokumen RAG (Aktif)">
      📚 <span id="lblRagChat">RAG</span>
    </button>
    <input type="file" id="fileInput" accept="image/*" style="display: none;" onchange="handleFileSelect(event)">
    <button id="btnAttach" class="btn-action" onclick="triggerFileInput()" title="Lampirkan Gambar">
      📷
    </button>
    <button id="btnMic" class="btn-action btn-mic" onclick="toggleVoiceRecording()" title="Bicara Manual (Push-to-Talk)">
      🎙️
    </button>
    <textarea id="promptInput" placeholder="Ketik atau bicara..." rows="1" onkeydown="handleKey(event)"></textarea>
    <button id="btnSend" class="btn-send" onclick="sendMessage()" disabled>
      ➤
    </button>
  </footer>

  <!-- REALTIME HANDS-FREE VOICE OVERLAY / ROOM -->
  <div id="realtimeModal" class="realtime-modal">
    <div class="rt-header">
      <div class="rt-badge">
        <span class="dot"></span>
        <span id="rtLangBadgeText">🇮🇩 Bahasa Indonesia</span>
      </div>

      <!-- Auto-Sela (Barge-in) Toggle Switch -->
      <div class="rt-toggle-group" title="Saat aktif, ucapan Anda akan langsung memotong pembicaraan AI (Disarankan pakai headset)">
        <span style="font-size: 0.74rem; color: var(--text-muted);">⚡ Auto-Sela:</span>
        <label class="switch-toggle">
          <input type="checkbox" id="chkAutoBargeIn" onchange="toggleAutoBargeIn(this.checked)">
          <span class="slider-toggle"></span>
        </label>
        <span id="badgeAutoBargeIn" style="font-size: 0.72rem; font-weight: 700; color: #94a3b8;">OFF</span>
      </div>
    </div>

    <div class="rt-center-stage">
      <div class="orb-wrapper">
        <div class="orb-ring" id="orbRing"></div>
        <div class="voice-orb listening" id="voiceOrb" onclick="onOrbClick()" title="Klik untuk sela / bicara">
          🎙️
        </div>
      </div>

      <div>
        <div class="rt-status-text" id="rtStatusMain">Mendengarkan...</div>
        <div class="rt-substatus" id="rtStatusSub">Silakan langsung berbicara santai</div>
      </div>

      <div class="rt-live-box" id="rtLiveBox">
        <div id="rtUserBubble" class="rt-bubble user" style="display: none;"></div>
        <div id="rtAiBubble" class="rt-bubble ai" style="display: none;"></div>
      </div>
    </div>

    <div class="rt-footer-controls">
      <!-- Tombol Sela Manual (Hanya muncul saat AI sedang berbicara) -->
      <button id="btnInterrupt" class="btn-rt-interrupt" onclick="interruptAiSpeaking()" style="display: none;">
        ✋ Sela AI (Potong Bicara)
      </button>

      <button class="btn-rt-exit" onclick="closeRealtimeVoiceModal()">
        ⏹ Tutup Mode Realtime
      </button>
    </div>
  </div>

  <!-- OPENAI API / AI AGENTS MODAL -->
  <div id="apiModal" class="api-modal-overlay" onclick="if(event.target === this) closeApiModal()">
    <div class="api-modal-content">
      <div class="api-modal-header">
        <h3>🔌 OpenAI-Compatible API & AI Agents Guide</h3>
        <button class="api-modal-close" onclick="closeApiModal()">✕ Tutup</button>
      </div>
      <div class="api-modal-body">
        <p style="font-size: 0.82rem; color: var(--text-muted); margin: 0; line-height: 1.5;">
          Server Local LLM ini menyediakan endpoint standar <b>OpenAI Chat Completions API</b> yang kompatibel langsung dengan framework AI agent seperti <b>LangChain, CrewAI, AutoGen, OpenAI Python/Node SDK, Cursor, Continue.dev, LibreChat</b>, dan lainnya.
        </p>

        <!-- Endpoint Info Cards -->
        <div class="api-endpoint-card">
          <div style="font-size: 0.74rem; font-weight: 700; color: #94a3b8;">BASE URL (OpenAI SDK):</div>
          <div class="api-endpoint-row">
            <span class="api-endpoint-badge">V1</span>
            <code class="api-endpoint-url" id="textBaseUrl">http://localhost:3000/v1</code>
            <button class="btn-copy-chip" onclick="copyApiSnippet(document.getElementById('textBaseUrl').textContent, this)">📋 Salin Base URL</button>
          </div>
        </div>

        <div class="api-endpoint-card">
          <div style="font-size: 0.74rem; font-weight: 700; color: #94a3b8;">CHAT COMPLETIONS ENDPOINT:</div>
          <div class="api-endpoint-row">
            <span class="api-endpoint-badge" style="background: #10b981;">POST</span>
            <code class="api-endpoint-url" id="textChatUrl">http://localhost:3000/v1/chat/completions</code>
            <button class="btn-copy-chip" onclick="copyApiSnippet(document.getElementById('textChatUrl').textContent, this)">📋 Salin</button>
          </div>
        </div>

        <div class="api-endpoint-card">
          <div style="font-size: 0.74rem; font-weight: 700; color: #94a3b8;">MODELS LIST ENDPOINT:</div>
          <div class="api-endpoint-row">
            <span class="api-endpoint-badge" style="background: #8b5cf6;">GET</span>
            <code class="api-endpoint-url" id="textModelsUrl">http://localhost:3000/v1/models</code>
            <button class="btn-copy-chip" onclick="copyApiSnippet(document.getElementById('textModelsUrl').textContent, this)">📋 Salin</button>
          </div>
        </div>

        <div style="display: flex; gap: 8px; flex-wrap: wrap; background: rgba(30, 41, 59, 0.4); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; font-size: 0.74rem; color: #94a3b8;">
          <div>🔑 <b>API Key:</b> <code style="color: #38bdf8;">sk-local</code> (Bebas / Dummy jika tidak diset di .env)</div>
          <div>⚡ <b>Auto-Start:</b> Server otomatis menyalakan model jika ada request masuk dari agent!</div>
          <div>🌊 <b>Streaming:</b> Mendukung SSE streaming (<code>stream: true</code>) & non-streaming.</div>
        </div>

        <!-- Tabs Nav -->
        <div class="api-tabs-nav">
          <button class="api-tab-btn active" id="tabBtnPython" onclick="switchApiTab('python')">🐍 Python (OpenAI SDK)</button>
          <button class="api-tab-btn" id="tabBtnLangchain" onclick="switchApiTab('langchain')">🦜 LangChain / CrewAI</button>
          <button class="api-tab-btn" id="tabBtnCurl" onclick="switchApiTab('curl')">💻 cURL / REST</button>
          <button class="api-tab-btn" id="tabBtnContinue" onclick="switchApiTab('continue')">⚙️ Continue.dev / Cursor</button>
        </div>

        <!-- Tab Contents -->
        <div id="tabContentPython" class="api-tab-content">
          <div class="api-code-block">
            <button class="api-code-copy-btn" onclick="copyCodeBlock('codePython', this)">📋 Salin</button>
            <pre id="codePython"><code>from openai import OpenAI

# Inisialisasi client dengan Base URL Local LLM
client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local"  # Bebas/dummy jika tidak diset di .env
)

# Chat completions dengan streaming
response = client.chat.completions.create(
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    messages=[
        {"role": "system", "content": "Kamu adalah asisten AI yang ramah."},
        {"role": "user", "content": "Halo! Siapa namamu?"}
    ],
    temperature=0.7,
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)</code></pre>
          </div>
        </div>

        <div id="tabContentLangchain" class="api-tab-content" style="display: none;">
          <div class="api-code-block">
            <button class="api-code-copy-btn" onclick="copyCodeBlock('codeLangchain', this)">📋 Salin</button>
            <pre id="codeLangchain"><code>from langchain_openai import ChatOpenAI

# LangChain Chat Model
llm = ChatOpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local",
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    temperature=0.7
)

res = llm.invoke("Jelaskan apa itu Multi-Agent System secara ringkas!")
print(res.content)

# Integrasi CrewAI Agent:
# from crewai import Agent
# researcher = Agent(
#     role="Researcher",
#     goal="Mencari insight teknologi",
#     backstory="Expert AI Specialist",
#     llm=llm
# )</code></pre>
          </div>
        </div>

        <div id="tabContentCurl" class="api-tab-content" style="display: none;">
          <div class="api-code-block">
            <button class="api-code-copy-btn" onclick="copyCodeBlock('codeCurl', this)">📋 Salin</button>
            <pre id="codeCurl"><code>curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
    "messages": [
      {"role": "system", "content": "Kamu adalah asisten AI yang membantu."},
      {"role": "user", "content": "Halo, sebutkan 3 tips produktivitas!"}
    ],
    "temperature": 0.7,
    "stream": false
  }'</code></pre>
          </div>
        </div>

        <div id="tabContentContinue" class="api-tab-content" style="display: none;">
          <div class="api-code-block">
            <button class="api-code-copy-btn" onclick="copyCodeBlock('codeContinue', this)">📋 Salin</button>
            <pre id="codeContinue"><code>// Masukkan konfigurasi ini ke file: ~/.continue/config.json
{
  "models": [
    {
      "title": "Local LLM Studio",
      "provider": "openai",
      "model": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
      "apiBase": "http://localhost:3000/v1",
      "apiKey": "sk-local"
    }
  ]
}</code></pre>
          </div>
        </div>

      </div>
    </div>
  </div>

  <!-- RAG KNOWLEDGE BASE MODAL (SQLite + NumPy) -->
  <div id="ragModal" class="rag-modal-overlay" onclick="if(event.target === this) closeRagModal()">
    <div class="rag-modal-content">
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--border-color); background: rgba(15, 23, 42, 0.8);">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 1.2rem;">📚</span>
          <div>
            <div style="font-weight: 700; color: #34d399; font-size: 0.95rem;">Basis Pengetahuan Dokumen (Edge RAG)</div>
            <div style="font-size: 0.72rem; color: var(--text-muted);">Embedded SQLite3 & Pure NumPy SIMD Cosine Vector Search</div>
          </div>
        </div>
        <button class="api-modal-close" onclick="closeRagModal()">✕ Tutup</button>
      </div>

      <div style="padding: 16px; display: flex; flex-direction: column; gap: 14px;">
        <!-- Stats & Switch Bar -->
        <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; background: rgba(15, 23, 42, 0.6); padding: 12px 14px; border-radius: 10px; border: 1px solid var(--border-color); gap: 10px;">
          <div style="display: flex; gap: 14px; flex-wrap: wrap;">
            <div>
              <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Total Dokumen</div>
              <div id="ragStatDocs" style="font-size: 1.05rem; font-weight: 700; color: #38bdf8;">0</div>
            </div>
            <div style="border-left: 1px solid #334155; padding-left: 14px;">
              <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Potongan (Chunks)</div>
              <div id="ragStatChunks" style="font-size: 1.05rem; font-weight: 700; color: #a78bfa;">0</div>
            </div>
            <div style="border-left: 1px solid #334155; padding-left: 14px;">
              <div style="font-size: 0.68rem; color: var(--text-muted); text-transform: uppercase;">Ukuran DB</div>
              <div id="ragStatSize" style="font-size: 1.05rem; font-weight: 700; color: #34d399;">0 KB</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 0.78rem; color: var(--text-muted); font-weight: 600;">Status RAG:</span>
            <button id="btnRagModalToggle" class="btn-rag-toggle active" onclick="toggleRagActiveChat()" style="height: 32px; font-size: 0.75rem;">
              ✓ Aktif
            </button>
          </div>
        </div>

        <!-- Upload File Dropzone -->
        <input type="file" id="ragFileInput" accept=".pdf,.docx,.txt,.md,.csv,.json,.log" style="display: none;" onchange="handleRagFileSelected(event)">
        <div class="rag-dropzone" onclick="document.getElementById('ragFileInput').click()" ondragover="event.preventDefault(); this.classList.add('dragover')" ondragleave="this.classList.remove('dragover')" ondrop="handleRagFileDrop(event)">
          <div style="font-size: 1.8rem; margin-bottom: 4px;">📥</div>
          <div style="font-weight: 700; font-size: 0.88rem; color: var(--text-main);">Klik atau Seret File ke Sini untuk Diindeks</div>
          <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 3px;">
            Mendukung: <b>PDF, Word (.docx), TXT, Markdown (.md), CSV, JSON</b>
          </div>
          <div id="ragUploadLoading" style="display: none; margin-top: 8px; font-size: 0.75rem; color: #38bdf8; font-weight: 600;">
            ⏳ Mengekstrak teks & menghitung vektor embedding...
          </div>
        </div>

        <!-- Real-time Test Query Search -->
        <div style="background: rgba(15, 23, 42, 0.4); border: 1px solid var(--border-color); border-radius: 10px; padding: 10px 12px;">
          <div style="font-size: 0.76rem; font-weight: 700; color: #94a3b8; margin-bottom: 6px;">🔍 Uji Penelusuran Semantik (Cek Kecocokan Konteks):</div>
          <div style="display: flex; gap: 6px;">
            <input type="text" id="ragSearchInput" placeholder="Ketik kalimat atau kata kunci untuk mencari relevansi..." style="flex: 1; background: #0f172a; border: 1px solid var(--border-color); border-radius: 6px; padding: 6px 10px; color: white; font-size: 0.78rem;" onkeydown="if(event.key === 'Enter') executeRagSearch()">
            <button onclick="executeRagSearch()" style="background: #2563eb; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 0.75rem; font-weight: 700; cursor: pointer;">Cari</button>
          </div>
          <div id="ragSearchResults" style="display: none; margin-top: 8px; max-height: 160px; overflow-y: auto; flex-direction: column; gap: 6px;"></div>
        </div>

        <!-- Document List -->
        <div>
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #94a3b8;">Daftar Dokumen Tersimpan:</div>
            <button onclick="fetchRagDocuments()" style="background: transparent; border: 1px solid #334155; color: #94a3b8; padding: 3px 8px; border-radius: 6px; font-size: 0.7rem; cursor: pointer;">🔄 Refresh</button>
          </div>
          <div id="ragDocList" style="display: flex; flex-direction: column; gap: 8px; max-height: 220px; overflow-y: auto;">
            <div style="text-align: center; color: var(--text-muted); font-size: 0.76rem; padding: 16px;">Memuat dokumen...</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function openApiModal() {
      const host = window.location.origin || 'http://localhost:3000';
      const baseUrl = `${host}/v1`;
      const el = document.getElementById('textBaseUrl');
      if (el) el.textContent = baseUrl;
      const elChat = document.getElementById('textChatUrl');
      if (elChat) elChat.textContent = `${host}/v1/chat/completions`;
      const elModels = document.getElementById('textModelsUrl');
      if (elModels) elModels.textContent = `${host}/v1/models`;
      document.getElementById('apiModal').style.display = 'flex';
    }

    function closeApiModal() {
      document.getElementById('apiModal').style.display = 'none';
    }

    function copyApiSnippet(text, btnElement) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
          const original = btnElement.innerHTML;
          btnElement.innerHTML = '✅ Tersalin!';
          setTimeout(() => { btnElement.innerHTML = original; }, 2000);
        });
      }
    }

    function copyCodeBlock(codeId, btnElement) {
      const codeEl = document.getElementById(codeId);
      if (codeEl && navigator.clipboard) {
        navigator.clipboard.writeText(codeEl.textContent).then(() => {
          const original = btnElement.innerHTML;
          btnElement.innerHTML = '✅ Tersalin!';
          setTimeout(() => { btnElement.innerHTML = original; }, 2000);
        });
      }
    }

    function switchApiTab(tabName) {
      const tabs = ['python', 'langchain', 'curl', 'continue'];
      tabs.forEach(t => {
        const btn = document.getElementById(`tabBtn${t.charAt(0).toUpperCase() + t.slice(1)}`);
        const content = document.getElementById(`tabContent${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (btn) btn.classList.toggle('active', t === tabName);
        if (content) content.style.display = (t === tabName) ? 'block' : 'none';
      });
    }

    /* RAG KNOWLEDGE BASE FUNCTIONS */
    let isRagActive = true;
    let ragDocuments = [];

    function openRagModal() {
      document.getElementById('ragModal').style.display = 'flex';
      fetchRagDocuments();
    }

    function closeRagModal() {
      document.getElementById('ragModal').style.display = 'none';
    }

    async function toggleRagActiveChat() {
      isRagActive = !isRagActive;
      updateRagToggleUI();
      try {
        await fetch('/api/rag/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: isRagActive })
        });
      } catch (e) {
        console.error("Gagal menyimpan status RAG:", e);
      }
    }

    function updateRagToggleUI() {
      const btnInput = document.getElementById('btnToggleRagChat');
      const btnModal = document.getElementById('btnRagModalToggle');
      const lbl = document.getElementById('lblRagChat');
      if (btnInput) {
        btnInput.classList.toggle('active', isRagActive);
        btnInput.title = isRagActive ? "Pencarian Cerdas Dokumen RAG (Aktif)" : "Pencarian Dokumen RAG (Nonaktif)";
      }
      if (lbl) {
        lbl.textContent = isRagActive ? "RAG" : "Off";
      }
      if (btnModal) {
        btnModal.classList.toggle('active', isRagActive);
        btnModal.textContent = isRagActive ? "✓ Aktif" : "✕ Nonaktif";
      }
    }

    async function fetchRagDocuments() {
      const listEl = document.getElementById('ragDocList');
      try {
        const res = await fetch('/api/rag/documents');
        const data = await res.json();
        if (data.status === 'ok') {
          ragDocuments = data.documents || [];
          if (data.rag_enabled !== undefined) {
            isRagActive = data.rag_enabled;
            updateRagToggleUI();
          }
          const stats = data.stats || {};
          const elDocs = document.getElementById('ragStatDocs');
          const elChunks = document.getElementById('ragStatChunks');
          const elSize = document.getElementById('ragStatSize');
          if (elDocs) elDocs.textContent = stats.total_documents || 0;
          if (elChunks) elChunks.textContent = stats.total_chunks || 0;
          if (elSize) elSize.textContent = `${stats.db_size_kb || 0} KB`;

          renderRagDocList(ragDocuments);
        }
      } catch (err) {
        if (listEl) listEl.innerHTML = `<div style="color: #ef4444; font-size: 0.75rem; text-align: center;">Gagal memuat dokumen: ${err.message}</div>`;
      }
    }

    function renderRagDocList(docs) {
      const listEl = document.getElementById('ragDocList');
      if (!listEl) return;
      if (!docs || docs.length === 0) {
        listEl.innerHTML = `
          <div style="text-align: center; color: var(--text-muted); font-size: 0.78rem; padding: 24px; border: 1px dashed #334155; border-radius: 8px;">
            Belum ada dokumen yang diunggah.<br>
            <span style="font-size: 0.7rem; color: #64748b;">Unggah file PDF, Word, atau teks untuk mengaktifkan RAG otomatis.</span>
          </div>`;
        return;
      }

      listEl.innerHTML = docs.map(d => `
        <div class="rag-doc-card">
          <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">
            <span class="rag-badge-ext">${d.file_type || 'TXT'}</span>
            <div style="min-width: 0;">
              <div style="font-size: 0.82rem; font-weight: 600; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px;" title="${d.filename}">
                ${d.filename}
              </div>
              <div style="font-size: 0.68rem; color: var(--text-muted);">
                ${d.chunk_count} chunk • ${d.char_count.toLocaleString()} karakter • ${d.created_at || ''}
              </div>
            </div>
          </div>
          <button onclick="deleteRagDoc(${d.id}, '${d.filename.replace(/'/g, "\\'")}')" style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); color: #f87171; padding: 4px 8px; border-radius: 6px; font-size: 0.7rem; cursor: pointer; white-space: nowrap;" title="Hapus Dokumen">
            🗑️ Hapus
          </button>
        </div>
      `).join('');
    }

    function handleRagFileSelected(event) {
      const file = event.target.files[0];
      if (file) uploadRagFile(file);
      event.target.value = '';
    }

    function handleRagFileDrop(event) {
      event.preventDefault();
      event.currentTarget.classList.remove('dragover');
      if (event.dataTransfer.files && event.dataTransfer.files[0]) {
        uploadRagFile(event.dataTransfer.files[0]);
      }
    }

    function uploadRagFile(file) {
      const loadingEl = document.getElementById('ragUploadLoading');
      if (loadingEl) loadingEl.style.display = 'block';

      const reader = new FileReader();
      reader.onload = async function(e) {
        const base64Data = e.target.result;
        try {
          const res = await fetch('/api/rag/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              filename: file.name,
              content_base64: base64Data
            })
          });
          const data = await res.json();
          if (data.success) {
            appendSystemMessage(`📚 Dokumen "${file.name}" berhasil diindeks (${data.data.chunk_count} chunk, ${data.data.char_count} karakter).`);
            fetchRagDocuments();
          } else {
            alert(`Gagal memproses dokumen: ${data.error || 'Unknown error'}`);
          }
        } catch (err) {
          alert(`Gagal mengunggah dokumen: ${err.message}`);
        } finally {
          if (loadingEl) loadingEl.style.display = 'none';
        }
      };
      reader.readAsDataURL(file);
    }

    async function deleteRagDoc(docId, filename) {
      if (!confirm(`Hapus dokumen "${filename}" dari basis pengetahuan RAG?`)) return;
      try {
        const res = await fetch('/api/rag/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ doc_id: docId })
        });
        const data = await res.json();
        if (data.success) {
          fetchRagDocuments();
        } else {
          alert(`Gagal menghapus dokumen: ${data.error || 'Unknown error'}`);
        }
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    }

    async function executeRagSearch() {
      const q = document.getElementById('ragSearchInput').value.trim();
      const resContainer = document.getElementById('ragSearchResults');
      if (!q) return;

      resContainer.style.display = 'flex';
      resContainer.innerHTML = '<div style="font-size: 0.72rem; color: #38bdf8;">Mencari kecocokan semantik...</div>';

      try {
        const res = await fetch('/api/rag/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: q, top_k: 3 })
        });
        const data = await res.json();
        if (data.success && data.hits && data.hits.length > 0) {
          resContainer.innerHTML = data.hits.map((h, idx) => {
            const pct = Math.round(h.score * 100);
            return `
              <div style="background: #0b1329; border: 1px solid #1e293b; border-radius: 6px; padding: 6px 8px; font-size: 0.72rem;">
                <div style="display: flex; justify-content: space-between; font-weight: 700; color: #34d399; margin-bottom: 2px;">
                  <span>#${idx+1} ${h.filename} (Bagian ${h.chunk_index+1})</span>
                  <span>Relevansi: ${pct}%</span>
                </div>
                <div style="color: #cbd5e1; line-height: 1.35; white-space: pre-wrap;">${h.content}</div>
              </div>
            `;
          }).join('');
        } else {
          resContainer.innerHTML = '<div style="font-size: 0.72rem; color: #94a3b8;">Tidak ditemukan potongan dokumen dengan skor kemiripan memadai.</div>';
        }
      } catch (err) {
        resContainer.innerHTML = `<div style="font-size: 0.72rem; color: #ef4444;">Pencarian gagal: ${err.message}</div>`;
      }
    }
    const SUPPORTED_LANGS = {
      "id": {
        name: "Bahasa Indonesia",
        flag: "🇮🇩",
        badge: "🇮🇩 ID",
        whisper: "id",
        preferred_prefix: "id_ID",
        test_text: "Halo, ini adalah pengujian suara lokal dengan setelan slider Anda.",
        placeholder: "Ketik atau bicara dalam bahasa Indonesia...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Indonesian (Bahasa Indonesia)."
      },
      "en": {
        name: "English",
        flag: "🇺🇸",
        badge: "🇺🇸 EN",
        whisper: "en",
        preferred_prefix: "en_US",
        test_text: "Hello! This is a test of my voice using your current slider settings.",
        placeholder: "Type or speak in English...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in clear English."
      },
      "ja": {
        name: "日本語 (Japanese)",
        flag: "🇯🇵",
        badge: "🇯🇵 JA",
        whisper: "ja",
        preferred_prefix: "ja_JP",
        test_text: "こんにちは！これはローカル音声合成のテストです。",
        placeholder: "日本語で入力または話しかけてください...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Japanese (日本語)."
      },
      "zh": {
        name: "中文 (Chinese / Mandarin)",
        flag: "🇨🇳",
        badge: "🇨🇳 ZH",
        whisper: "zh",
        preferred_prefix: "zh_CN",
        test_text: "你好！这是使用当前滑块设置的本地语音测试。",
        placeholder: "输入文字或用中文说话...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Simplified Chinese (中文)."
      },
      "ar": {
        name: "العربية (Arabic)",
        flag: "🇸🇦",
        badge: "🇸🇦 AR",
        whisper: "ar",
        preferred_prefix: "ar_JO",
        test_text: "مرحباً! هذا اختبار للصوت المحلي menggunakan إعداداتك الحالية.",
        placeholder: "اكتب atau تحدث باللغة العربية...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Modern Standard Arabic (العربية)."
      },
      "es": {
        name: "Español (Spanish)",
        flag: "🇪🇸",
        badge: "🇪🇸 ES",
        whisper: "es",
        preferred_prefix: "es_ES",
        test_text: "¡Hola! Esta es una prueba de voz local con la configuración de control.",
        placeholder: "Escribe o habla en español...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Spanish (Español)."
      },
      "fr": {
        name: "Français (French)",
        flag: "🇫🇷",
        badge: "🇫🇷 FR",
        whisper: "fr",
        preferred_prefix: "fr_FR",
        test_text: "Bonjour ! Ceci est un test de voix locale avec vos paramètres actuels.",
        placeholder: "Écrivez ou parlez en français...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in French (Français)."
      },
      "de": {
        name: "Deutsch (German)",
        flag: "🇩🇪",
        badge: "🇩🇪 DE",
        whisper: "de",
        preferred_prefix: "de_DE",
        test_text: "Hallo! Dies ist ein lokaler Sprachtest mit Ihren aktuellen Schieberegler-Einstellungen.",
        placeholder: "Tippen atau sprechen Sie auf Deutsch...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in German (Deutsch)."
      },
      "ko": {
        name: "한국어 (Korean)",
        flag: "🇰🇷",
        badge: "🇰🇷 KO",
        whisper: "ko",
        preferred_prefix: "ko_KR",
        test_text: "안녕하세요! 현재 설정으로 로컬 음성을 테스트하는 중입니다.",
        placeholder: "입력하거나 한국어로 말씀하세요...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Korean (한국어)."
      },
      "it": {
        name: "Italiano (Italian)",
        flag: "🇮🇹",
        badge: "🇮🇹 IT",
        whisper: "it",
        preferred_prefix: "it_IT",
        test_text: "Ciao! Questo è un test vocale locale con le tue impostazioni correnti.",
        placeholder: "Scrivi o parla in italiano...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Italian (Italiano)."
      },
      "ru": {
        name: "Русский (Russian)",
        flag: "🇷🇺",
        badge: "🇷🇺 RU",
        whisper: "ru",
        preferred_prefix: "ru_RU",
        test_text: "Здравствуйте! Это тест локального синтеза речи с вашими текущими настройками.",
        placeholder: "Введите текст atau говорите по-русски...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Russian (Русский)."
      },
      "pt": {
        name: "Português (Portuguese)",
        flag: "🇵🇹",
        badge: "🇵🇹 PT",
        whisper: "pt",
        preferred_prefix: "pt_BR",
        test_text: "Olá! Este é um teste de voz local com as configurações atuais.",
        placeholder: "Digite atau fale em português...",
        system_prompt: "You are a helpful AI assistant. Always respond fluently and naturally in Portuguese (Português)."
      }
    };

    let isRunning = false;
    let currentModel = null;
    let isGenerating = false;
    let chatHistory = [];
    let attachedImageBase64 = null;
    let modelMetadata = {};
    let voiceCatalog = [];
    let currentVoiceModel = "";
    let currentLang = "id";
    let currentTtsEngine = "edge";
    let currentEdgeVoice = "id-ID-GadisNeural";
    let currentKokoroVoice = "af_heart";
    let enginesCatalog = { edge: [], kokoro: [], melo: [] };
    let isAutoLangAdaptEnabled = true;

    // Push-to-Talk Manual State
    let audioContext = null;
    let mediaStream = null;
    let scriptProcessor = null;
    let audioChunks = [];
    let isRecording = false;

    // Realtime Hands-Free State
    let isRealtimeActive = false;
    let isRealtimeListening = false;
    let isAutoBargeIn = false; // Toggle Auto-Sela
    let rtAudioContext = null;
    let rtMediaStream = null;
    let rtScriptProcessor = null;
    let rtAudioChunks = [];
    let rtUserSpeaking = false;
    let rtSilenceStartTime = null;
    let rtSpeechStartTime = null;
    let rtCurrentAudioPlayer = null;
    let isAiSpeaking = false;

    const RT_VAD_THRESHOLD = 0.019; // Threshold energi saat mendengarkan
    const RT_BARGEIN_THRESHOLD = 0.034; // Threshold suara user untuk Auto-Sela AI
    const RT_SILENCE_DELAY_MS = 1300; // 1.3 detik hening untuk auto-kirim
    const RT_MIN_SPEECH_DURATION_MS = 600; // Minimal durasi bicara valid

    function toggleSettingsPanel() {
      const panel = document.getElementById('settingsPanel');
      panel.style.display = (panel.style.display === 'block') ? 'none' : 'block';
    }

    function toggleAutoLangAdapt() {
      isAutoLangAdaptEnabled = !isAutoLangAdaptEnabled;
      const btn = document.getElementById('btnAutoLangAdapt');
      if (btn) {
        if (isAutoLangAdaptEnabled) {
          btn.textContent = 'ON (Aktif)';
          btn.style.background = '#10b981';
          appendSystemMessage("🌐 Auto-Adapt Bahasa Balasan diaktifkan: Suara AI otomatis menyesuaikan bahasa balasan teks.");
        } else {
          btn.textContent = 'OFF (Terkunci)';
          btn.style.background = '#64748b';
          appendSystemMessage("🌐 Auto-Adapt Bahasa Balasan dinonaktifkan: Suara terkunci pada pilihan bahasa manual.");
        }
      }
    }

    function initLanguageUI() {
      const pillsContainer = document.getElementById('langPills');
      const langSelect = document.getElementById('langSelect');
      pillsContainer.innerHTML = '';
      langSelect.innerHTML = '';

      for (const [code, info] of Object.entries(SUPPORTED_LANGS)) {
        // Pill Button
        const btn = document.createElement('button');
        btn.id = `pill-lang-${code}`;
        btn.className = 'lang-pill-btn';
        btn.innerHTML = `${info.flag} ${info.name.split(' ')[0]}`;
        btn.onclick = () => switchLanguage(code);
        pillsContainer.appendChild(btn);

        // Select Option
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = `${info.flag} ${info.name}`;
        langSelect.appendChild(opt);
      }
    }

    async function switchLanguage(lang) {
      if (!SUPPORTED_LANGS[lang]) lang = "id";
      currentLang = lang;
      const info = SUPPORTED_LANGS[lang];

      // Update pills active state
      for (const code of Object.keys(SUPPORTED_LANGS)) {
        const pill = document.getElementById(`pill-lang-${code}`);
        if (pill) {
          if (code === lang) pill.classList.add('active');
          else pill.classList.remove('active');
        }
      }

      // Update select element
      document.getElementById('langSelect').value = lang;

      // Update Header badge & info
      document.getElementById('btnHeaderLang').textContent = info.badge;
      document.getElementById('infoWhisperLang').textContent = info.whisper;
      document.getElementById('infoLLMLang').textContent = info.name;
      document.getElementById('rtLangBadgeText').textContent = `${info.flag} ${info.name}`;

      // Update input placeholder & test box
      document.getElementById('testSentenceInput').value = info.test_text;
      document.getElementById('promptInput').placeholder = info.placeholder;

      // Persist to .env.local
      await updateConfig('APP_LANGUAGE', lang);
      await updateConfig('WHISPER_LANGUAGE', info.whisper);

      // Auto-select or suggest matching voice
      selectMatchingVoiceForLanguage(lang);
    }

    function selectMatchingVoiceForLanguage(lang) {
      const select = document.getElementById('voiceModelSelect');
      if (!select) return;

      if (currentTtsEngine === 'edge') {
        const edgeList = enginesCatalog.edge || [];
        const match = edgeList.find(v => v.lang === lang) || edgeList.find(v => v.lang === 'id') || edgeList[0];
        if (match) {
          select.value = match.key;
          onVoiceSelectionChange(match.key);
        }
        return;
      }

      if (currentTtsEngine === 'kokoro') {
        const kokoroList = enginesCatalog.kokoro || [];
        let match = kokoroList.find(v => v.lang === lang);
        if (!match) match = kokoroList.find(v => v.key === 'af_heart') || kokoroList[0];
        if (match) {
          select.value = match.key;
          onVoiceSelectionChange(match.key);
        }
        return;
      }

      const info = SUPPORTED_LANGS[lang];
      if (!info || !voiceCatalog.length) return;

      const prefix = info.preferred_prefix.toLowerCase();
      let match = voiceCatalog.find(v => v.key.toLowerCase().startsWith(prefix) && v.is_downloaded);
      if (!match) {
        match = voiceCatalog.find(v => (v.code.toLowerCase().startsWith(info.whisper) || v.language.toLowerCase().includes(info.name.toLowerCase().split(' ')[0])) && v.is_downloaded);
      }
      if (!match) {
        match = voiceCatalog.find(v => v.key.toLowerCase().startsWith(prefix));
      }
      if (!match) {
        match = voiceCatalog.find(v => v.code.toLowerCase().startsWith(info.whisper));
      }

      if (match) {
        select.value = match.key;
        onVoiceSelectionChange(match.key);
      }
    }

    function onSliderChange(key, val, labelId, labelVal) {
      document.getElementById(labelId).textContent = labelVal;
      updateConfig(key, val);
    }

    async function applyPreset(speed, expr, noisew, silence) {
      document.getElementById('sliderSpeed').value = speed;
      document.getElementById('valSpeed').textContent = speed + 'x';
      document.getElementById('sliderExpr').value = expr;
      document.getElementById('valExpr').textContent = expr;
      document.getElementById('sliderNoiseW').value = noisew;
      document.getElementById('valNoiseW').textContent = noisew;
      document.getElementById('sliderSilence').value = silence;
      document.getElementById('valSilence').textContent = silence + 's';

      await updateConfig('VOICE_LENGTH_SCALE', speed);
      await updateConfig('VOICE_NOISE_SCALE', expr);
      await updateConfig('VOICE_NOISE_W', noisew);
      await updateConfig('VOICE_SENTENCE_SILENCE', silence);
      testCurrentVoice();
    }

    async function onTtsEngineChange(engine, save=true) {
      currentTtsEngine = engine;
      const badge = document.getElementById('ttsEngineBadge');
      const actionNotice = document.getElementById('voiceDownloadNotice');
      const btnOnline = document.getElementById('btnOnlineSample');
      const btnDownload = document.getElementById('btnDownloadVoice');
      const infoTtsEngine = document.getElementById('infoTtsEngine');
      const statEngine = document.getElementById('statTtsEngineActive');

      if (infoTtsEngine) infoTtsEngine.textContent = engine.toUpperCase();

      if (engine === 'edge') {
        if (badge) {
          badge.textContent = '🌐 Sangat Alami (Cloud Hybrid)';
          badge.style.color = '#38bdf8';
        }
        if (actionNotice) actionNotice.textContent = 'Microsoft Azure Neural Voice ultra-natural (0 MB Disk)';
        if (btnOnline) btnOnline.style.display = 'none';
        if (btnDownload) btnDownload.style.display = 'none';
        if (statEngine) statEngine.textContent = '🌐 Edge-TTS (' + (currentEdgeVoice ? currentEdgeVoice.split('-').pop().replace('Neural','') : 'Gadis') + ')';
      } else if (engine === 'kokoro') {
        if (badge) {
          badge.textContent = '🌸 SOTA StyleTTS2 (100% Offline)';
          badge.style.color = '#ec4899';
        }
        if (actionNotice) actionNotice.textContent = 'Model ONNX CPU jernih manusiawi (~337MB)';
        if (btnOnline) btnOnline.style.display = 'none';
        if (btnDownload) btnDownload.style.display = 'none';
        if (statEngine) statEngine.textContent = '🌸 Kokoro-82M (' + currentKokoroVoice + ')';
      } else if (engine === 'piper') {
        if (badge) {
          badge.textContent = '⚡ Offline Cepat (180+ Karakter)';
          badge.style.color = '#10b981';
        }
        if (actionNotice) actionNotice.textContent = 'Piper offline fast edge engine';
        if (btnOnline) btnOnline.style.display = 'inline-flex';
        if (statEngine) statEngine.textContent = '⚡ Piper TTS (' + (currentVoiceModel ? currentVoiceModel.split('/').pop().split('.')[0] : 'Offline') + ')';
      } else if (engine === 'melo') {
        if (badge) {
          badge.textContent = '🎙️ MeloTTS Mode (Multilingual)';
          badge.style.color = '#f59e0b';
        }
        if (actionNotice) actionNotice.textContent = 'MeloTTS multilingual prosody profile';
        if (btnOnline) btnOnline.style.display = 'none';
        if (btnDownload) btnDownload.style.display = 'none';
        if (statEngine) statEngine.textContent = '🎙️ MeloTTS Mode';
      }

      populateVoiceDropdown();

      if (save) {
        await updateConfig('TTS_ENGINE', engine);
      }
    }

    function onVoiceSelectionChange(val) {
      const badge = document.getElementById('voiceStatusBadge');
      const statEngine = document.getElementById('statTtsEngineActive');

      if (currentTtsEngine === 'edge') {
        currentEdgeVoice = val;
        if (badge) {
          badge.textContent = '✓ Siap (Neural)';
          badge.style.color = '#38bdf8';
        }
        if (statEngine) statEngine.textContent = '🌐 Edge-TTS (' + val.split('-').pop().replace('Neural','') + ')';
        updateConfig('EDGE_VOICE', val);
      } else if (currentTtsEngine === 'kokoro') {
        currentKokoroVoice = val;
        if (badge) {
          badge.textContent = '✓ Siap (Offline 82M)';
          badge.style.color = '#ec4899';
        }
        if (statEngine) statEngine.textContent = '🌸 Kokoro-82M (' + val + ')';
        updateConfig('KOKORO_VOICE', val);
      } else if (currentTtsEngine === 'melo') {
        if (badge) {
          badge.textContent = '✓ Siap (Melo Mode)';
          badge.style.color = '#f59e0b';
        }
      } else if (currentTtsEngine === 'piper') {
        const selected = voiceCatalog.find(v => v.key === val);
        if (!selected) return;

        const downloadBtn = document.getElementById('btnDownloadVoice');
        const testLocalBtn = document.getElementById('btnTestLocal');

        if (selected.is_downloaded) {
          if (downloadBtn) downloadBtn.style.display = 'none';
          if (badge) {
            badge.textContent = '✓ Siap Pakai (Offline)';
            badge.style.color = 'var(--success)';
          }
          if (testLocalBtn) testLocalBtn.disabled = false;
          currentVoiceModel = selected.filename;
          if (statEngine) statEngine.textContent = '⚡ Piper (' + selected.name + ')';
          updateConfig('VOICE_MODEL', selected.filename);
        } else {
          if (downloadBtn) downloadBtn.style.display = 'inline-flex';
          if (badge) {
            badge.textContent = '☁ Belum Diunduh';
            badge.style.color = 'var(--primary)';
          }
          if (testLocalBtn) testLocalBtn.disabled = true;
        }
      }
    }

    function playOnlineSample() {
      const select = document.getElementById('voiceModelSelect');
      const selected = voiceCatalog.find(v => v.key === select.value);
      if (!selected || !selected.sample_url) {
        alert("Sample audio URL tidak ditemukan.");
        return;
      }

      const btn = document.getElementById('btnOnlineSample');
      btn.textContent = '⏳ Memutar Contoh...';
      const audio = new Audio(selected.sample_url);
      audio.play().then(() => {
        btn.textContent = '▶ Sedang Berbunyi...';
      }).catch(err => {
        alert("Gagal memutar audio preview online: " + err.message);
        btn.textContent = '🎧 Dengar Rekaman Contoh';
      });

      audio.onended = () => {
        btn.textContent = '🎧 Dengar Rekaman Contoh';
      };
      audio.onerror = () => {
        btn.textContent = '🎧 Dengar Rekaman Contoh';
      };
    }

    async function downloadSelectedVoice() {
      const select = document.getElementById('voiceModelSelect');
      const voiceKey = select.value;
      const btn = document.getElementById('btnDownloadVoice');
      btn.disabled = true;
      btn.textContent = '⏳ Mengunduh...';

      try {
        const res = await fetch('/api/voice/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ voice_key: voiceKey })
        });
        const data = await res.json();
        if (data.success) {
          const item = voiceCatalog.find(v => v.key === voiceKey);
          if (item) item.is_downloaded = true;
          currentVoiceModel = data.voice_model;
          populateVoiceDropdown();
          select.value = voiceKey;
          onVoiceSelectionChange(voiceKey);
          testCurrentVoice();
        } else {
          alert("Gagal mengunduh: " + (data.error || "Unknown error"));
        }
      } catch (err) {
        alert("Download error: " + err.message);
      } finally {
        btn.disabled = false;
        btn.textContent = '⬇️ Unduh 1-Klik (~60MB)';
      }
    }

    async function updateConfig(key, value) {
      const indicator = document.getElementById('savedIndicator');
      if (indicator) indicator.textContent = 'Menyimpan...';
      try {
        await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value })
        });
        if (indicator) indicator.textContent = '✓ Tersimpan di .env.local';
      } catch (err) {
        if (indicator) indicator.textContent = 'Gagal menyimpan!';
      }
    }

    async function testCurrentVoice() {
      const btn = document.getElementById('btnTestLocal');
      const text = document.getElementById('testSentenceInput').value.trim() || "Halo, ini pengujian suara.";
      const speed = parseFloat(document.getElementById('sliderSpeed').value);
      const expr = parseFloat(document.getElementById('sliderExpr').value);
      const noisew = parseFloat(document.getElementById('sliderNoiseW').value);
      const silence = parseFloat(document.getElementById('sliderSilence').value);

      btn.disabled = true;
      btn.textContent = '🔊 Mensintesis...';

      try {
        const res = await fetch('/api/voice/synthesize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            engine: currentTtsEngine,
            edge_voice: currentEdgeVoice,
            kokoro_voice: currentKokoroVoice,
            length_scale: speed,
            noise_scale: expr,
            noise_w: noisew,
            sentence_silence: silence,
            voice_model: currentVoiceModel
          })
        });
        const data = await res.json();
        if (data.audio) {
          playAudioBase64(data.audio, data.mime_type || data.format);
        } else {
          alert("Gagal sintesis: " + (data.error || "Error"));
        }
      } catch (e) {
        console.error("Test voice error:", e);
      } finally {
        btn.disabled = false;
        btn.textContent = '▶ Bunyikan Suara Sekarang';
      }
    }

    function populateVoiceDropdown() {
      const vSelect = document.getElementById('voiceModelSelect');
      if (!vSelect) return;
      vSelect.innerHTML = '';
      const badge = document.getElementById('voiceStatusBadge');
      const testLocalBtn = document.getElementById('btnTestLocal');
      const downloadBtn = document.getElementById('btnDownloadVoice');

      if (currentTtsEngine === 'edge') {
        const voices = enginesCatalog.edge || [];
        voices.forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.key;
          opt.textContent = `${v.name}`;
          if (v.key === currentEdgeVoice) opt.selected = true;
          vSelect.appendChild(opt);
        });
        if (badge) {
          badge.textContent = '✓ Siap (Neural)';
          badge.style.color = '#38bdf8';
        }
        if (testLocalBtn) testLocalBtn.disabled = false;
        if (downloadBtn) downloadBtn.style.display = 'none';
      } else if (currentTtsEngine === 'kokoro') {
        const voices = enginesCatalog.kokoro || [];
        voices.forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.key;
          opt.textContent = `${v.name}`;
          if (v.key === currentKokoroVoice) opt.selected = true;
          vSelect.appendChild(opt);
        });
        if (badge) {
          badge.textContent = '✓ Siap (Offline 82M)';
          badge.style.color = '#ec4899';
        }
        if (testLocalBtn) testLocalBtn.disabled = false;
        if (downloadBtn) downloadBtn.style.display = 'none';
      } else if (currentTtsEngine === 'melo') {
        const voices = enginesCatalog.melo || [];
        voices.forEach(v => {
          const opt = document.createElement('option');
          opt.value = v.key;
          opt.textContent = `${v.name}`;
          vSelect.appendChild(opt);
        });
        if (badge) {
          badge.textContent = '✓ Siap (Melo Mode)';
          badge.style.color = '#f59e0b';
        }
        if (testLocalBtn) testLocalBtn.disabled = false;
        if (downloadBtn) downloadBtn.style.display = 'none';
      } else {
        // Piper TTS
        const groups = {};
        voiceCatalog.forEach(v => {
          const grp = v.country ? `${v.language} (${v.country})` : v.language;
          if (!groups[grp]) groups[grp] = [];
          groups[grp].push(v);
        });

        for (const [groupName, voices] of Object.entries(groups)) {
          const optGroup = document.createElement('optgroup');
          optGroup.label = groupName;
          voices.forEach(v => {
            const opt = document.createElement('option');
            opt.value = v.key;
            const statusIcon = v.is_downloaded ? '✓' : '☁';
            opt.textContent = `${statusIcon} ${v.name} [${v.quality}]`;
            if (v.filename === currentVoiceModel) {
              opt.selected = true;
            }
            optGroup.appendChild(opt);
          });
          vSelect.appendChild(optGroup);
        }
        if (vSelect.value) onVoiceSelectionChange(vSelect.value);
      }
    }

    const HARDWARE_PRESETS = {
      "ultra_light": {
        name: "🪶 Ultra-Light",
        llm: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        whisper: "voice_models/ggml-base.bin",
        tts_engine: "piper",
        voice: "voice_models/id_ID-news_tts-medium.onnx",
        ram: "~1.15 GB",
        disk: "~780 MB",
        cardId: "cardPresetUltraLight",
        engineDesc: "⚡ Piper TTS"
      },
      "balanced": {
        name: "⚖️ Balanced Pro ⭐",
        llm: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        whisper: "voice_models/ggml-small.bin",
        tts_engine: "piper",
        voice: "voice_models/id_ID-news_tts-medium.onnx",
        ram: "~1.75 GB",
        disk: "~1.10 GB",
        cardId: "cardPresetBalanced",
        engineDesc: "⚡ Piper TTS"
      },
      "kokoro_studio": {
        name: "🌸 Kokoro SOTA Studio",
        llm: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        whisper: "voice_models/ggml-small.bin",
        tts_engine: "kokoro",
        voice: "af_heart",
        ram: "~1.95 GB",
        disk: "~1.45 GB",
        cardId: "cardPresetKokoro",
        engineDesc: "🌸 Kokoro-82M (Heart)"
      },
      "edge_natural": {
        name: "🌐 Edge Natural",
        llm: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        whisper: "voice_models/ggml-small.bin",
        tts_engine: "edge",
        voice: "id-ID-GadisNeural",
        ram: "~1.75 GB",
        disk: "~1.10 GB",
        cardId: "cardPresetEdge",
        engineDesc: "🌐 Edge-TTS (Gadis)"
      },
      "vision": {
        name: "👁️ Vision Studio",
        llm: "SmolVLM-500M-Instruct-Q8_0.gguf",
        whisper: "voice_models/ggml-small.bin",
        tts_engine: "edge",
        voice: "id-ID-GadisNeural",
        ram: "~2.00 GB",
        disk: "~1.35 GB",
        cardId: "cardPresetVision",
        engineDesc: "🌐 Edge-TTS"
      },
      "max": {
        name: "🧠 Max Omni 2B",
        llm: "LFM3-Omni-2B-Q4_K_M.gguf",
        whisper: "voice_models/ggml-small.bin",
        tts_engine: "kokoro",
        voice: "af_heart",
        ram: "~3.45 GB",
        disk: "~2.55 GB",
        cardId: "cardPresetMax",
        engineDesc: "🌸 Kokoro-82M"
      },
      "agentic_fast": {
        name: "🤖 Agentic Fast (3B) ⭐",
        llm: "qwen2.5-3b-instruct-q4_k_m.gguf",
        whisper: "voice_models/ggml-small.bin",
        tts_engine: "edge",
        voice: "id-ID-GadisNeural",
        ram: "~3.80 GB",
        disk: "~2.60 GB",
        cardId: "cardPresetAgenticFast",
        engineDesc: "🌐 Edge-TTS (Qwen 3B Agent)",
        modelKey: "qwen2.5-3b"
      },
      "agentic_pro": {
        name: "👑 Agentic Pro (7B)",
        llm: "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        whisper: "voice_models/ggml-small.bin",
        tts_engine: "edge",
        voice: "id-ID-GadisNeural",
        ram: "~6.80 GB",
        disk: "~5.20 GB",
        cardId: "cardPresetAgenticPro",
        engineDesc: "🌐 Edge-TTS (Qwen 7B Agent)",
        modelKey: "qwen2.5-7b"
      }
    };

    let downloadPollTimer = null;
    async function startModelDownload(modelKey, modelName) {
      const box = document.getElementById('modelDownloadProgressBox');
      const title = document.getElementById('dlModelTitle');
      const pctEl = document.getElementById('dlModelPercent');
      const bar = document.getElementById('dlModelProgressBar');
      const mbEl = document.getElementById('dlModelMb');

      if (box) box.style.display = 'block';
      if (title) title.textContent = `Mengunduh ${modelName}...`;
      if (pctEl) pctEl.textContent = '0%';
      if (bar) bar.style.width = '0%';
      if (mbEl) mbEl.textContent = 'Memulai koneksi ke Hugging Face Hub...';

      try {
        const res = await fetch('/api/models/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model_key: modelKey })
        });
        const d = await res.json();
        if (!d.success) {
          alert("Gagal memulai unduhan: " + (d.error || "Error"));
          if (box) box.style.display = 'none';
          return;
        }

        if (downloadPollTimer) clearInterval(downloadPollTimer);
        downloadPollTimer = setInterval(pollDownloadProgress, 1000);
      } catch (err) {
        alert("Gagal mengunduh: " + err.message);
        if (box) box.style.display = 'none';
      }
    }

    async function pollDownloadProgress() {
      try {
        const res = await fetch('/api/models/download/progress');
        const d = await res.json();
        const box = document.getElementById('modelDownloadProgressBox');
        const title = document.getElementById('dlModelTitle');
        const pctEl = document.getElementById('dlModelPercent');
        const bar = document.getElementById('dlModelProgressBar');
        const mbEl = document.getElementById('dlModelMb');

        if (d.status === 'downloading') {
          if (box) box.style.display = 'block';
          if (title) title.textContent = `Mengunduh ${d.model_name || 'Model'}...`;
          if (pctEl) pctEl.textContent = `${d.pct}%`;
          if (bar) bar.style.width = `${d.pct}%`;
          if (mbEl) mbEl.textContent = `${d.mb_done} / ${d.mb_total} MB`;
        } else if (d.status === 'done') {
          clearInterval(downloadPollTimer);
          downloadPollTimer = null;
          if (pctEl) pctEl.textContent = '100%';
          if (bar) bar.style.width = '100%';
          if (mbEl) mbEl.textContent = '✓ Unduhan Berhasil!';
          setTimeout(() => {
            if (box) box.style.display = 'none';
          }, 3500);
          appendSystemMessage(`Model ${d.model_name} berhasil diunduh dan siap dijalankan!`);
          await fetchStatus();
        } else if (d.status === 'error') {
          clearInterval(downloadPollTimer);
          downloadPollTimer = null;
          alert("Gagal mengunduh model: " + d.error);
          if (box) box.style.display = 'none';
        }
      } catch (e) {
        console.error("Poll error:", e);
      }
    }

    async function applyHardwarePreset(presetKey, shouldNotify=true) {
      const p = HARDWARE_PRESETS[presetKey];
      if (!p) return;

      // Cek apakah file model sudah terpasang di komputer
      const mSelect = document.getElementById('modelSelect');
      let modelFound = false;
      if (mSelect) {
        for (let i = 0; i < mSelect.options.length; i++) {
          if (mSelect.options[i].value === p.llm) {
            modelFound = true;
            break;
          }
        }
      }

      if (!modelFound && p.modelKey) {
        if (confirm(`Model '${p.llm}' (${p.disk}) belum ada di komputer Anda.\n\nApakah Anda ingin mengunduhnya sekarang langsung dari Hugging Face Hub?`)) {
          startModelDownload(p.modelKey, p.name);
          return;
        }
      }

      // Update active cards
      for (const [k, v] of Object.entries(HARDWARE_PRESETS)) {
        const card = document.getElementById(v.cardId);
        if (card) {
          if (k === presetKey) card.classList.add('active');
          else card.classList.remove('active');
        }
      }

      document.getElementById('activePresetBadge').textContent = p.name;
      document.getElementById('statRamActive').textContent = p.ram;
      document.getElementById('statDiskActive').textContent = p.disk;
      const statEngine = document.getElementById('statTtsEngineActive');
      if (statEngine) statEngine.textContent = p.engineDesc || p.tts_engine;

      // Update select model LLM
      if (mSelect) mSelect.value = p.llm;

      // Update Whisper model select
      const wSelect = document.getElementById('whisperModelSelect');
      if (wSelect) {
        wSelect.value = p.whisper;
        onWhisperModelChange(p.whisper, true);
      }

      // Update TTS engine
      if (p.tts_engine) {
        currentTtsEngine = p.tts_engine;
        const eSelect = document.getElementById('ttsEngineSelect');
        if (eSelect) eSelect.value = p.tts_engine;
        await onTtsEngineChange(p.tts_engine, true);
        if (p.voice) {
          if (p.tts_engine === 'edge') currentEdgeVoice = p.voice;
          else if (p.tts_engine === 'kokoro') currentKokoroVoice = p.voice;
          else currentVoiceModel = p.voice;
          const vSelect = document.getElementById('voiceModelSelect');
          if (vSelect) vSelect.value = p.voice;
        }
      }

      // Save to config
      await updateConfig('DEFAULT_MODEL', p.llm);
      await updateConfig('WHISPER_MODEL', p.whisper);

      if (shouldNotify) {
        appendSystemMessage(`Preset diaktifkan: ${p.name} (Total RAM: ${p.ram} | Penyimpanan: ${p.disk}). Klik "▶ Jalankan" untuk mulai/ganti model.`);
      }
    }

    async function onWhisperModelChange(val, save=true) {
      const badge = document.getElementById('whisperBadge');
      if (val.includes('small')) {
        badge.textContent = '⭐ Akurasi Tinggi';
        badge.style.color = '#10b981';
      } else {
        badge.textContent = '⚡ Cepat / Ringan';
        badge.style.color = '#60a5fa';
      }
      if (save) {
        await updateConfig('WHISPER_MODEL', val);
      }
    }

    async function fetchCatalogAndConfig() {
      try {
        initLanguageUI();
        const [catRes, cfgRes, engRes] = await Promise.all([
          fetch('/api/voice/catalog'),
          fetch('/api/config'),
          fetch('/api/voice/engines')
        ]);
        voiceCatalog = await catRes.json();
        const cfg = await cfgRes.json();
        enginesCatalog = await engRes.json();

        currentVoiceModel = cfg.VOICE_MODEL || "";
        currentLang = cfg.APP_LANGUAGE || "id";
        currentTtsEngine = cfg.TTS_ENGINE || "edge";
        currentEdgeVoice = cfg.EDGE_VOICE || "id-ID-GadisNeural";
        currentKokoroVoice = cfg.KOKORO_VOICE || "af_heart";

        const eSelect = document.getElementById('ttsEngineSelect');
        if (eSelect) eSelect.value = currentTtsEngine;
        await onTtsEngineChange(currentTtsEngine, false);

        if (cfg.WHISPER_MODEL) {
          const wSelect = document.getElementById('whisperModelSelect');
          if (wSelect) {
            wSelect.value = cfg.WHISPER_MODEL;
            onWhisperModelChange(cfg.WHISPER_MODEL, false);
          }
        }

        // Match initial hardware preset visual
        const defLlm = cfg.DEFAULT_MODEL || "qwen2.5-0.5b-instruct-q4_k_m.gguf";
        const curWhisper = cfg.WHISPER_MODEL || "voice_models/ggml-small.bin";
        let matchedPreset = "edge_natural";
        if (defLlm.includes("LFM3")) matchedPreset = "max";
        else if (defLlm.includes("Smol")) matchedPreset = "vision";
        else if (currentTtsEngine === "kokoro") matchedPreset = "kokoro_studio";
        else if (currentTtsEngine === "edge") matchedPreset = "edge_natural";
        else if (curWhisper.includes("base")) matchedPreset = "ultra_light";
        else matchedPreset = "balanced";
        applyHardwarePreset(matchedPreset, false);

        // Switch to configured language
        await switchLanguage(currentLang);

        if (currentVoiceModel) {
          const matchItem = voiceCatalog.find(v => v.filename === currentVoiceModel);
          if (matchItem) {
            document.getElementById('voiceModelSelect').value = matchItem.key;
            onVoiceSelectionChange(matchItem.key);
          }
        }

        if (cfg.VOICE_LENGTH_SCALE) {
          document.getElementById('sliderSpeed').value = cfg.VOICE_LENGTH_SCALE;
          document.getElementById('valSpeed').textContent = cfg.VOICE_LENGTH_SCALE + 'x';
        }
        if (cfg.VOICE_NOISE_SCALE) {
          document.getElementById('sliderExpr').value = cfg.VOICE_NOISE_SCALE;
          document.getElementById('valExpr').textContent = cfg.VOICE_NOISE_SCALE;
        }
        if (cfg.VOICE_NOISE_W) {
          document.getElementById('sliderNoiseW').value = cfg.VOICE_NOISE_W;
          document.getElementById('valNoiseW').textContent = cfg.VOICE_NOISE_W;
        }
        if (cfg.VOICE_SENTENCE_SILENCE) {
          document.getElementById('sliderSilence').value = cfg.VOICE_SENTENCE_SILENCE;
          document.getElementById('valSilence').textContent = cfg.VOICE_SENTENCE_SILENCE + 's';
        }
      } catch (e) {
        console.log("Catalog load err:", e);
      }
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        isRunning = data.running;
        currentModel = data.current_model;
        modelMetadata = data.model_meta || {};
        
        const badge = document.getElementById('statusBadge');
        const statusText = document.getElementById('statusText');
        const btnStart = document.getElementById('btnStart');
        const btnStop = document.getElementById('btnStop');
        const btnSend = document.getElementById('btnSend');
        const select = document.getElementById('modelSelect');

        if (select.options.length === 0) {
          data.models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            const isVLM = modelMetadata[m] ? ' [Vision]' : ' [Text]';
            opt.textContent = m + isVLM;
            select.appendChild(opt);
          });
          if (currentModel) {
            select.value = currentModel;
          } else if (data.default_model) {
            select.value = data.default_model;
          }
        }

        if (isRunning) {
          badge.className = 'status-badge online';
          statusText.textContent = 'AKTIF: ' + (currentModel ? currentModel.split('-')[0] : 'LLM');
          btnStart.textContent = '🔄 Ganti Model';
          btnStop.disabled = false;
          btnSend.disabled = isGenerating;
        } else {
          badge.className = 'status-badge';
          statusText.textContent = 'STOPPED';
          btnStart.textContent = '▶ Jalankan';
          btnStop.disabled = true;
          btnSend.disabled = true;
        }
      } catch (err) {
        console.error("Status fetch error:", err);
      }
    }

    async function handleStart() {
      const select = document.getElementById('modelSelect');
      const model = select.value;
      if (!model) return;

      appendSystemMessage(`Memuat ${model}...`);
      document.getElementById('btnStart').disabled = true;
      document.getElementById('btnStop').disabled = true;

      try {
        const res = await fetch('/api/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model })
        });
        const data = await res.json();
        if (data.success) {
          appendSystemMessage(`Model ${model} siap digunakan!`);
        } else {
          appendSystemMessage(`Gagal memuat: ${data.error}`);
        }
      } catch (err) {
        appendSystemMessage(`Error: ${err.message}`);
      } finally {
        document.getElementById('btnStart').disabled = false;
        fetchStatus();
      }
    }

    async function handleStop() {
      document.getElementById('btnStart').disabled = true;
      document.getElementById('btnStop').disabled = true;
      try {
        await fetch('/api/stop', { method: 'POST' });
        appendSystemMessage("Server dihentikan.");
      } catch (err) {
        appendSystemMessage(`Error: ${err.message}`);
      } finally {
        document.getElementById('btnStart').disabled = false;
        fetchStatus();
      }
    }

    function triggerFileInput() {
      const select = document.getElementById('modelSelect');
      const isVLM = modelMetadata[select.value];
      if (!isVLM) {
        alert("Model yang dipilih (" + select.value + ") adalah Text-Only. Silakan pilih SmolVLM atau LFM3 untuk gambar.");
        return;
      }
      document.getElementById('fileInput').click();
    }

    function handleFileSelect(e) {
      const file = e.target.files[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = function(evt) {
        attachedImageBase64 = evt.target.result;
        document.getElementById('previewImg').src = attachedImageBase64;
        document.getElementById('previewBar').style.display = 'flex';
      };
      reader.readAsDataURL(file);
      e.target.value = '';
    }

    function clearAttachedImage() {
      attachedImageBase64 = null;
      document.getElementById('previewBar').style.display = 'none';
      document.getElementById('previewImg').src = '';
    }

    /* ==============================================================
       1. MODE PUSH-TO-TALK MANUAL (TETAP ADA SEPERTI SEMULA)
       ============================================================== */
    async function toggleVoiceRecording() {
      if (isRecording) {
        stopVoiceRecording();
      } else {
        startVoiceRecording();
      }
    }

    async function startVoiceRecording() {
      if (!isRunning) {
        alert("Jalankan model LLM terlebih dahulu sebelum berbicara.");
        return;
      }
      try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(mediaStream);
        
        scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        audioChunks = [];

        scriptProcessor.onaudioprocess = function(e) {
          if (!isRecording) return;
          const inputData = e.inputBuffer.getChannelData(0);
          audioChunks.push(new Float32Array(inputData));
        };

        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        isRecording = true;
        document.getElementById('btnMic').classList.add('recording');
        document.getElementById('recordingBar').style.display = 'flex';
        const langObj = SUPPORTED_LANGS[currentLang] || SUPPORTED_LANGS['id'];
        document.getElementById('recordingStatus').textContent = `Mendengarkan (${langObj.name})... Silakan berbicara.`;
      } catch (err) {
        alert("Gagal mengakses mikrofon: " + err.message);
      }
    }

    async function stopVoiceRecording() {
      if (!isRecording) return;
      isRecording = false;
      document.getElementById('btnMic').classList.remove('recording');
      document.getElementById('recordingStatus').textContent = 'Mentranskripsi suara (Whisper)...';

      if (scriptProcessor) scriptProcessor.disconnect();
      if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());

      const wavBlob = encodeWav(audioChunks, 16000);
      document.getElementById('recordingBar').style.display = 'none';

      if (audioContext) audioContext.close();

      try {
        appendSystemMessage(`Mentranskripsi rekaman suara (Whisper [${currentLang}])...`);
        const reader = new FileReader();
        reader.onload = async function() {
          const base64Audio = reader.result.split(',')[1];
          const res = await fetch('/api/voice/transcribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio: base64Audio })
          });
          const data = await res.json();
          if (data.text && data.text.trim()) {
            document.getElementById('promptInput').value = data.text.trim();
            sendMessage();
          } else {
            appendSystemMessage("Suara tidak terdengar jelas, silakan coba lagi.");
          }
        };
        reader.readAsDataURL(wavBlob);
      } catch (err) {
        appendSystemMessage("Gagal transkrip: " + err.message);
      }
    }

    /* ==============================================================
       2. MODE REALTIME VOICE (DENGAN TOMBOL SELA & AUTO-SELA BARGE-IN)
       ============================================================== */
    function toggleAutoBargeIn(checked) {
      isAutoBargeIn = checked;
      const badge = document.getElementById('badgeAutoBargeIn');
      if (checked) {
        badge.textContent = 'ON';
        badge.style.color = '#10b981';
      } else {
        badge.textContent = 'OFF';
        badge.style.color = '#94a3b8';
      }
    }

    function onOrbClick() {
      if (isAiSpeaking) {
        // Klik Orb saat AI bicara -> Berfungsi sebagai Sela!
        interruptAiSpeaking();
      }
    }

    function interruptAiSpeaking() {
      if (rtCurrentAudioPlayer) {
        rtCurrentAudioPlayer.pause();
        rtCurrentAudioPlayer = null;
      }
      isAiSpeaking = false;
      document.getElementById('btnInterrupt').style.display = 'none';
      setRealtimeOrbState('listening', 'Menyela AI...', 'Silakan berbicara langsung');
      resumeRealtimeListening();
    }

    async function openRealtimeVoiceModal() {
      if (!isRunning) {
        alert("Jalankan model LLM terlebih dahulu sebelum memulai Realtime Voice.");
        return;
      }
      isRealtimeActive = true;
      document.getElementById('realtimeModal').style.display = 'flex';
      setRealtimeOrbState('listening', 'Mendengarkan...', 'Silakan berbicara langsung santai');
      await startRealtimeAudioLoop();
    }

    function closeRealtimeVoiceModal() {
      isRealtimeActive = false;
      isRealtimeListening = false;
      isAiSpeaking = false;
      if (rtCurrentAudioPlayer) {
        rtCurrentAudioPlayer.pause();
        rtCurrentAudioPlayer = null;
      }
      stopRealtimeAudioStream();
      document.getElementById('realtimeModal').style.display = 'none';
      document.getElementById('btnInterrupt').style.display = 'none';
      appendSystemMessage("Mode Realtime Voice selesai. Anda dapat melanjutkan via chat biasa.");
    }

    function setRealtimeOrbState(state, mainText, subText) {
      const orb = document.getElementById('voiceOrb');
      orb.className = 'voice-orb ' + state;
      if (state === 'listening') {
        orb.textContent = '🎙️';
        document.getElementById('btnInterrupt').style.display = 'none';
      } else if (state === 'processing') {
        orb.textContent = '⏳';
        document.getElementById('btnInterrupt').style.display = 'none';
      } else if (state === 'speaking') {
        orb.textContent = '🔊';
        document.getElementById('btnInterrupt').style.display = 'inline-flex';
      }
      document.getElementById('rtStatusMain').textContent = mainText;
      document.getElementById('rtStatusSub').textContent = subText;
    }

    async function startRealtimeAudioLoop() {
      try {
        rtMediaStream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
          }
        });
        rtAudioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = rtAudioContext.createMediaStreamSource(rtMediaStream);
        rtScriptProcessor = rtAudioContext.createScriptProcessor(4096, 1, 1);

        rtAudioChunks = [];
        rtUserSpeaking = false;
        rtSilenceStartTime = null;
        rtSpeechStartTime = null;
        isRealtimeListening = true;
        isAiSpeaking = false;

        const orb = document.getElementById('voiceOrb');

        rtScriptProcessor.onaudioprocess = function(e) {
          if (!isRealtimeActive) return;

          const inputData = e.inputBuffer.getChannelData(0);

          // Hitung RMS (Energy level) secara real-time
          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i];
          }
          const rms = Math.sqrt(sum / inputData.length);

          // Animasi denyut orb mengikuti volume suara
          if (rms > 0.005) {
            const scale = Math.min(1.4, 1.0 + rms * 3.5);
            orb.style.transform = `scale(${scale})`;
          } else {
            orb.style.transform = 'scale(1.0)';
          }

          // FITUR AUTO-SELA (VOICE BARGE-IN)
          // Jika AI sedang berbicara dan pengguna mulai berbicara kuat
          if (isAiSpeaking && isAutoBargeIn && rms > RT_BARGEIN_THRESHOLD) {
            console.log("Auto-Barge-in triggered! User spoke while AI was speaking.");
            interruptAiSpeaking();
            rtUserSpeaking = true;
            rtSpeechStartTime = Date.now();
            rtSilenceStartTime = null;
            rtAudioChunks = [new Float32Array(inputData)];
            setRealtimeOrbState('listening', 'Menyela AI...', 'Mendengarkan ucapan baru Anda');
            return;
          }

          // Jika AI sedang berbicara atau sedang memproses LLM, lewati deteksi VAD normal
          if (!isRealtimeListening) return;

          // Voice Activity Detection (VAD) Biasa
          const now = Date.now();
          if (rms > RT_VAD_THRESHOLD) {
            if (!rtUserSpeaking) {
              rtUserSpeaking = true;
              rtSpeechStartTime = now;
              rtSilenceStartTime = null;
              setRealtimeOrbState('listening', 'Mendengarkan...', 'Suara terdeteksi');
            }
            rtAudioChunks.push(new Float32Array(inputData));
            rtSilenceStartTime = null;
          } else {
            if (rtUserSpeaking) {
              rtAudioChunks.push(new Float32Array(inputData));
              if (rtSilenceStartTime === null) {
                rtSilenceStartTime = now;
              } else if (now - rtSilenceStartTime >= RT_SILENCE_DELAY_MS) {
                // Keheningan terdeteksi setelah bicara!
                const speechDuration = now - rtSpeechStartTime;
                rtUserSpeaking = false;
                rtSilenceStartTime = null;

                if (speechDuration >= RT_MIN_SPEECH_DURATION_MS && rtAudioChunks.length > 3) {
                  // Kirim otomatis ke Whisper dan LLM!
                  const chunksToProcess = rtAudioChunks.slice();
                  rtAudioChunks = [];
                  processRealtimeUtterance(chunksToProcess);
                } else {
                  // Bunyi terlalu singkat (batuk / noise), abaikan
                  rtAudioChunks = [];
                }
              }
            }
          }
        };

        source.connect(rtScriptProcessor);
        rtScriptProcessor.connect(rtAudioContext.destination);
      } catch (err) {
        alert("Gagal mengakses mikrofon untuk Realtime Voice: " + err.message);
        closeRealtimeVoiceModal();
      }
    }

    function stopRealtimeAudioStream() {
      if (rtScriptProcessor) {
        try { rtScriptProcessor.disconnect(); } catch (e) {}
        rtScriptProcessor = null;
      }
      if (rtMediaStream) {
        try { rtMediaStream.getTracks().forEach(t => t.stop()); } catch (e) {}
        rtMediaStream = null;
      }
      if (rtAudioContext) {
        try { rtAudioContext.close(); } catch (e) {}
        rtAudioContext = null;
      }
    }

    async function processRealtimeUtterance(chunks) {
      isRealtimeListening = false;
      setRealtimeOrbState('processing', 'Memproses...', 'Mentranskripsi & memikirkan jawaban');

      try {
        const wavBlob = encodeWav(chunks, 16000);
        const reader = new FileReader();

        reader.onload = async function() {
          const base64Audio = reader.result.split(',')[1];
          // 1. STT Whisper
          const res = await fetch('/api/voice/transcribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ audio: base64Audio })
          });
          const data = await res.json();
          const userText = data.text ? data.text.trim() : '';

          if (!userText) {
            resumeRealtimeListening();
            return;
          }

          // Tampilkan teks pengguna di Bubble Realtime dan append ke chat log
          const uBubble = document.getElementById('rtUserBubble');
          uBubble.textContent = "👤 " + userText;
          uBubble.style.display = 'block';
          appendMessage('user', userText);

          // 2. Chat LLM
          const langObj = SUPPORTED_LANGS[currentLang] || SUPPORTED_LANGS['id'];
          let messagesToSend = [];
          if (langObj && langObj.system_prompt) {
            messagesToSend.push({ role: "system", content: langObj.system_prompt });
          }
          messagesToSend = messagesToSend.concat(chatHistory);
          messagesToSend.push({ role: "user", content: userText });
          chatHistory.push({ role: "user", content: userText });

          setRealtimeOrbState('processing', 'AI Berpikir...', 'Menyiapkan respon suara');

          const chatRes = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: messagesToSend, rag_enabled: isRagActive })
          });
          const chatData = await chatRes.json();
          const reply = (chatData.choices && chatData.choices[0]) ? chatData.choices[0].message.content : '';

          if (!reply) {
            resumeRealtimeListening();
            return;
          }

          chatHistory.push({ role: "assistant", content: reply });
          const aBubble = document.getElementById('rtAiBubble');
          aBubble.textContent = "🤖 " + reply;
          aBubble.style.display = 'block';

          // 3. Sintesis Suara Piper TTS
          setRealtimeOrbState('speaking', 'AI Berbicara...', 'Memutar suara respon');
          isAiSpeaking = true;

          const speed = parseFloat(document.getElementById('sliderSpeed').value);
          const expr = parseFloat(document.getElementById('sliderExpr').value);
          const noisew = parseFloat(document.getElementById('sliderNoiseW').value);
          const silence = parseFloat(document.getElementById('sliderSilence').value);

          const ttsRes = await fetch('/api/voice/synthesize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: reply,
              engine: currentTtsEngine,
              edge_voice: currentEdgeVoice,
              kokoro_voice: currentKokoroVoice,
              auto_adapt_lang: isAutoLangAdaptEnabled,
              length_scale: speed,
              noise_scale: expr,
              noise_w: noisew,
              sentence_silence: silence,
              voice_model: currentVoiceModel
            })
          });
          const ttsData = await ttsRes.json();
          let langTag = null;
          if (ttsData.detected_lang && ttsData.voice_used) {
            const flag = (SUPPORTED_LANGS[ttsData.detected_lang] || {}).flag || '🌐';
            const vShort = ttsData.voice_used.split('-').pop().replace('Neural', '').replace('.onnx', '');
            langTag = `${flag} ${ttsData.detected_lang.toUpperCase()} • ${vShort}`;
            const rtBadge = document.getElementById('rtLangBadgeText');
            if (rtBadge) {
              rtBadge.textContent = `${flag} ${ttsData.detected_lang.toUpperCase()} • ${vShort}`;
            }
          }

          appendMessage('assistant', reply, null, 'Realtime Hands-Free', ttsData.audio, langTag);

          if (ttsData.audio && isRealtimeActive && isAiSpeaking) {
            const mime = ttsData.mime_type || (ttsData.format || (ttsData.audio.startsWith('//O') || ttsData.audio.startsWith('SUQz') ? 'audio/mp3' : 'audio/wav'));
            rtCurrentAudioPlayer = new Audio(`data:${mime};base64,${ttsData.audio}`);
            rtCurrentAudioPlayer.onended = () => {
              rtCurrentAudioPlayer = null;
              isAiSpeaking = false;
              if (isRealtimeActive) resumeRealtimeListening();
            };
            rtCurrentAudioPlayer.onerror = () => {
              rtCurrentAudioPlayer = null;
              isAiSpeaking = false;
              if (isRealtimeActive) resumeRealtimeListening();
            };
            await rtCurrentAudioPlayer.play();
          } else {
            isAiSpeaking = false;
            resumeRealtimeListening();
          }
        };

        reader.readAsDataURL(wavBlob);
      } catch (err) {
        console.error("Realtime utterance error:", err);
        isAiSpeaking = false;
        resumeRealtimeListening();
      }
    }

    function resumeRealtimeListening() {
      if (!isRealtimeActive) return;
      rtAudioChunks = [];
      rtUserSpeaking = false;
      rtSilenceStartTime = null;
      rtSpeechStartTime = null;
      isRealtimeListening = true;
      isAiSpeaking = false;
      setRealtimeOrbState('listening', 'Mendengarkan...', 'Silakan berbicara langsung santai');
    }

    /* ==============================================================
       3. FUNGSI ENCODE AUDIO, CHAT DAN HELPER
       ============================================================== */
    function encodeWav(chunks, sampleRate) {
      let totalLength = 0;
      for (let i = 0; i < chunks.length; i++) {
        totalLength += chunks[i].length;
      }
      const pcmData = new Float32Array(totalLength);
      let offset = 0;
      for (let i = 0; i < chunks.length; i++) {
        pcmData.set(chunks[i], offset);
        offset += chunks[i].length;
      }

      // 1. Peak Normalization: Deteksi puncak amplitudo audio pengguna
      let maxPeak = 0;
      for (let i = 0; i < pcmData.length; i++) {
        const absVal = Math.abs(pcmData[i]);
        if (absVal > maxPeak) maxPeak = absVal;
      }

      // 2. Dynamic Gain: Tingkatkan volume audio lemah secara proporsional
      // Target peak level ~0.88 agar Whisper menangkap konsonan & vokal dengan sangat jelas
      let gain = 1.0;
      if (maxPeak > 0.015 && maxPeak < 0.70) {
        gain = Math.min(4.5, 0.88 / maxPeak);
      }

      const buffer = new ArrayBuffer(44 + pcmData.length * 2);
      const view = new DataView(buffer);

      function writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
          view.setUint8(offset + i, string.charCodeAt(i));
        }
      }

      writeString(view, 0, 'RIFF');
      view.setUint32(4, 36 + pcmData.length * 2, true);
      writeString(view, 8, 'WAVE');
      writeString(view, 12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeString(view, 36, 'data');
      view.setUint32(40, pcmData.length * 2, true);

      let pcmOffset = 44;
      for (let i = 0; i < pcmData.length; i++) {
        let s = Math.max(-1, Math.min(1, pcmData[i] * gain));
        view.setInt16(pcmOffset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        pcmOffset += 2;
      }
      return new Blob([buffer], { type: 'audio/wav' });
    }

    function playAudioBase64(base64Data, mime) {
      if (!base64Data) return;
      if (base64Data.startsWith('data:')) {
        const audio = new Audio(base64Data);
        audio.play().catch(e => console.log("Audio play error:", e));
        return;
      }
      const format = mime || (base64Data.startsWith('//O') || base64Data.startsWith('SUQz') ? 'audio/mp3' : 'audio/wav');
      const audio = new Audio(`data:${format};base64,${base64Data}`);
      audio.play().catch(e => console.log("Audio play error:", e));
    }

    function appendMessage(role, text, imgSrc, speed, audioBase64, langTag, ragSources) {
      const container = document.getElementById('chatContainer');
      const div = document.createElement('div');
      div.className = `message ${role}`;

      if (imgSrc) {
        const img = document.createElement('img');
        img.className = 'message-img';
        img.src = imgSrc;
        div.appendChild(img);
      }

      if (text) {
        const span = document.createElement('div');
        span.textContent = text;
        div.appendChild(span);
      }

      if (speed || audioBase64 || langTag || (ragSources && ragSources.length > 0)) {
        const footer = document.createElement('div');
        footer.className = 'msg-footer';
        if (ragSources && ragSources.length > 0) {
          const ragSpan = document.createElement('span');
          ragSpan.className = 'speed-tag';
          ragSpan.style.background = 'rgba(16, 185, 129, 0.18)';
          ragSpan.style.color = '#34d399';
          ragSpan.style.border = '1px solid rgba(16, 185, 129, 0.4)';
          const srcTitles = ragSources.map(s => `${s.filename} (${s.percent}%)`).join(', ');
          ragSpan.textContent = `📚 RAG: ${srcTitles}`;
          ragSpan.title = "Konteks diambil otomatis dari basis pengetahuan dokumen internal";
          footer.appendChild(ragSpan);
        }
        if (speed) {
          const speedSpan = document.createElement('span');
          speedSpan.className = 'speed-tag';
          speedSpan.textContent = speed;
          footer.appendChild(speedSpan);
        }
        if (langTag) {
          const lTag = document.createElement('span');
          lTag.className = 'speed-tag';
          lTag.style.background = 'rgba(56, 189, 248, 0.15)';
          lTag.style.color = '#38bdf8';
          lTag.textContent = langTag;
          footer.appendChild(lTag);
        }
        if (audioBase64) {
          const btn = document.createElement('button');
          btn.className = 'btn-audio-replay';
          btn.textContent = '🔊 Putar Suara';
          btn.onclick = () => playAudioBase64(audioBase64);
          footer.appendChild(btn);
        }
        div.appendChild(footer);
      }

      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }

    function appendSystemMessage(text) {
      appendMessage('system', text);
    }

    function handleKey(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    }

    async function sendMessage() {
      const input = document.getElementById('promptInput');
      const text = input.value.trim();
      const currentImg = attachedImageBase64;

      if ((!text && !currentImg) || isGenerating || !isRunning) return;

      input.value = '';
      input.style.height = '40px';
      clearAttachedImage();

      appendMessage('user', text, currentImg);

      let contentPayload;
      if (currentImg) {
        const langObj = SUPPORTED_LANGS[currentLang] || SUPPORTED_LANGS['id'];
        contentPayload = [
          { type: "text", text: text || (currentLang === 'en' ? "Describe this image in detail." : "Jelaskan gambar ini secara detail.") },
          { type: "image_url", image_url: { url: currentImg } }
        ];
      } else {
        contentPayload = text;
      }

      // Add system prompt dynamically based on selected language
      const langObj = SUPPORTED_LANGS[currentLang] || SUPPORTED_LANGS['id'];
      let messagesToSend = [];
      if (langObj && langObj.system_prompt) {
        messagesToSend.push({ role: "system", content: langObj.system_prompt });
      }
      messagesToSend = messagesToSend.concat(chatHistory);
      messagesToSend.push({ role: "user", content: contentPayload });

      chatHistory.push({ role: "user", content: contentPayload });

      isGenerating = true;
      document.getElementById('btnSend').disabled = true;
      const startTime = performance.now();

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: messagesToSend, rag_enabled: isRagActive })
        });

        const data = await res.json();
        const durationSec = ((performance.now() - startTime) / 1000).toFixed(1);

        if (data.choices && data.choices[0]) {
          const reply = data.choices[0].message.content;
          chatHistory.push({ role: "assistant", content: reply });

          let audioBase64 = null;
          let langTag = null;
          if (reply) {
            try {
              const speed = parseFloat(document.getElementById('sliderSpeed').value);
              const expr = parseFloat(document.getElementById('sliderExpr').value);
              const noisew = parseFloat(document.getElementById('sliderNoiseW').value);
              const silence = parseFloat(document.getElementById('sliderSilence').value);

              const ttsRes = await fetch('/api/voice/synthesize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  text: reply,
                  engine: currentTtsEngine,
                  edge_voice: currentEdgeVoice,
                  kokoro_voice: currentKokoroVoice,
                  auto_adapt_lang: isAutoLangAdaptEnabled,
                  length_scale: speed,
                  noise_scale: expr,
                  noise_w: noisew,
                  sentence_silence: silence,
                  voice_model: currentVoiceModel
                })
              });
              const ttsData = await ttsRes.json();
              if (ttsData.detected_lang && ttsData.voice_used) {
                const flag = (SUPPORTED_LANGS[ttsData.detected_lang] || {}).flag || '🌐';
                const vShort = ttsData.voice_used.split('-').pop().replace('Neural', '').replace('.onnx', '');
                langTag = `${flag} ${ttsData.detected_lang.toUpperCase()} • ${vShort}`;
              }
              if (ttsData.audio) {
                audioBase64 = ttsData.audio;
                playAudioBase64(audioBase64, ttsData.mime_type || ttsData.format);
              }
            } catch (err) {
              console.log("TTS error:", err);
            }
          }

          appendMessage('assistant', reply, null, `Generated in ${durationSec}s`, audioBase64, langTag, data.rag_sources);
        } else if (data.error) {
          appendSystemMessage(`Error: ${data.error}`);
        }
      } catch (err) {
        appendSystemMessage(`Gagal menghubungi server: ${err.message}`);
      } finally {
        isGenerating = false;
        document.getElementById('btnSend').disabled = false;
      }
    }

    setInterval(fetchStatus, 3000);
    fetchStatus();
    fetchCatalogAndConfig();
    fetchRagDocuments();
  </script>
</body>
</html>
"""

class RequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, X-Api-Key')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, X-Api-Key')
        self.send_header('Access-Control-Max-Age', '86400')
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip('/')

        if path == '' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif path in ('/v1/models', '/models'):
            if not check_api_auth(self.headers):
                self._send_json({"error": {"message": "Invalid API key.", "type": "invalid_request_error", "code": "invalid_api_key"}}, 401)
                return
            models = get_available_models()
            model_data = []
            for m in models:
                model_data.append({
                    "id": m,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "local-llm",
                    "permission": [{
                        "id": f"modelperm-{m}",
                        "object": "model_permission",
                        "created": int(time.time()),
                        "allow_create_engine": False,
                        "allow_sampling": True,
                        "allow_logprobs": True,
                        "allow_search_indices": False,
                        "allow_view": True,
                        "allow_fine_tuning": False,
                        "organization": "*",
                        "group": None,
                        "is_blocking": False
                    }],
                    "root": m,
                    "parent": None
                })
            self._send_json({"object": "list", "data": model_data})
        elif path.startswith('/v1/models/') or path.startswith('/models/'):
            if not check_api_auth(self.headers):
                self._send_json({"error": {"message": "Invalid API key.", "type": "invalid_request_error", "code": "invalid_api_key"}}, 401)
                return
            model_id = path.split('/')[-1]
            models = get_available_models()
            if model_id in models:
                self._send_json({
                    "id": model_id,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "local-llm",
                    "permission": [],
                    "root": model_id,
                    "parent": None
                })
            else:
                self._send_json({"error": {"message": f"Model '{model_id}' does not exist.", "type": "invalid_request_error", "code": "model_not_found"}}, 404)
        elif path == '/api/status':
            running = (current_process is not None and current_process.poll() is None)
            models = get_available_models()
            meta = {m: is_multimodal(m) for m in models}
            cfg = load_env()
            self._send_json({
                "running": running,
                "current_model": current_model_name,
                "models": models,
                "model_meta": meta,
                "default_model": cfg.get("DEFAULT_MODEL")
            })
        elif path == '/api/config':
            cfg = load_env()
            # Sanitasi agar credential API_KEY/TOKEN tidak bocor ke client-side
            sanitized = {k: v for k, v in cfg.items() if not any(secret in k.upper() for secret in ('KEY', 'SECRET', 'TOKEN', 'PASSWORD'))}
            self._send_json(sanitized)
        elif path == '/api/voice/catalog':
            cat = get_voice_catalog()
            self._send_json(cat)
        elif path == '/api/voice/engines':
            self._send_json({
                "edge": EDGE_VOICES_CATALOG,
                "kokoro": KOKORO_VOICES_CATALOG,
                "melo": MELO_VOICES_CATALOG
            })
        elif path == '/api/models/download/progress':
            with model_download_lock:
                self._send_json(dict(model_download_state))
        elif path == '/api/rag/documents':
            docs = rag_engine.list_documents()
            stats = rag_engine.get_stats()
            cfg = load_env()
            rag_enabled = str(cfg.get("RAG_ENABLED", "1")).lower() in ("1", "true", "yes")
            self._send_json({"status": "ok", "documents": docs, "stats": stats, "rag_enabled": rag_enabled})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'
        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = {}

        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip('/')

        # 1. OPENAI CHAT COMPLETIONS API (Untuk AI Agents: LangChain, CrewAI, AutoGen, Cursor, dll.)
        if path in ('/v1/chat/completions', '/chat/completions'):
            if not check_api_auth(self.headers):
                self._send_json({"error": {"message": "Invalid API key provided.", "type": "invalid_request_error", "code": "invalid_api_key"}}, 401)
                return

            req_model = data.get('model')
            ok, model_or_err = ensure_model_running(req_model)
            if not ok:
                self._send_json({"error": {"message": f"Could not start model: {model_or_err}", "type": "server_error", "code": 500}}, 500)
                return

            if not data.get('model') and current_model_name:
                data['model'] = current_model_name

            # Seamless RAG injection untuk OpenAI API (AI Agents: LangChain, CrewAI, AutoGen, dll.)
            if 'messages' in data and isinstance(data['messages'], list):
                rag_override = data.get('rag_enabled', None)
                augmented_msgs, _ = augment_messages_with_rag(data['messages'], top_k=3, enabled_override=rag_override)
                data['messages'] = augmented_msgs

            is_stream = bool(data.get('stream', False))
            fwd_payload = json.dumps(data).encode('utf-8')

            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{LLAMA_PORT}/v1/chat/completions",
                    data=fwd_payload,
                    headers={'Content-Type': 'application/json'}
                )
                if is_stream:
                    try:
                        resp = urllib.request.urlopen(req, timeout=300)
                    except urllib.error.HTTPError as he:
                        err_bytes = he.read()
                        try:
                            err_json = json.loads(err_bytes.decode('utf-8', errors='ignore'))
                            self._send_json(err_json, he.code)
                        except Exception:
                            self._send_json({"error": {"message": f"HTTP {he.code}", "code": he.code}}, he.code)
                        return

                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache, no-transform')
                    self.send_header('Connection', 'keep-alive')
                    self.send_header('X-Accel-Buffering', 'no')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, X-Api-Key')
                    self.end_headers()

                    try:
                        while True:
                            line = resp.readline()
                            if not line:
                                break
                            self.wfile.write(line)
                            self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError):
                        pass
                    finally:
                        resp.close()
                else:
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        res_data = json.loads(resp.read().decode('utf-8'))
                        self._send_json(res_data)
            except urllib.error.HTTPError as he:
                err_bytes = he.read()
                try:
                    err_json = json.loads(err_bytes.decode('utf-8', errors='ignore'))
                    self._send_json(err_json, he.code)
                except Exception:
                    self._send_json({"error": {"message": f"HTTP {he.code}", "code": he.code}}, he.code)
            except Exception as e:
                self._send_json({"error": {"message": f"Backend LLM error: {str(e)}", "type": "server_error", "code": 500}}, 500)
            return

        # 2. OPENAI TEXT COMPLETIONS API
        elif path in ('/v1/completions', '/completions'):
            if not check_api_auth(self.headers):
                self._send_json({"error": {"message": "Invalid API key provided.", "type": "invalid_request_error", "code": "invalid_api_key"}}, 401)
                return

            req_model = data.get('model')
            ok, model_or_err = ensure_model_running(req_model)
            if not ok:
                self._send_json({"error": {"message": f"Could not start model: {model_or_err}", "type": "server_error", "code": 500}}, 500)
                return

            is_stream = bool(data.get('stream', False))
            fwd_payload = json.dumps(data).encode('utf-8')
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{LLAMA_PORT}/v1/completions",
                    data=fwd_payload,
                    headers={'Content-Type': 'application/json'}
                )
                if is_stream:
                    resp = urllib.request.urlopen(req, timeout=300)
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache, no-transform')
                    self.send_header('Connection', 'keep-alive')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    try:
                        while True:
                            line = resp.readline()
                            if not line:
                                break
                            self.wfile.write(line)
                            self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError):
                        pass
                    finally:
                        resp.close()
                else:
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        res_data = json.loads(resp.read().decode('utf-8'))
                        self._send_json(res_data)
            except Exception as e:
                self._send_json({"error": {"message": str(e), "type": "server_error", "code": 500}}, 500)
            return

        elif path == '/api/config':
            key = data.get('key')
            val = data.get('value')
            if key and val is not None:
                save_env_value(key, val)
                self._send_json({"success": True})
            else:
                self._send_json({"error": "Invalid config payload"}, 400)

        elif path == '/api/voice/download':
            voice_key = data.get('voice_key')
            if not voice_key:
                self._send_json({"error": "No voice_key specified"}, 400)
                return
            try:
                model_rel = download_voice_from_catalog(voice_key)
                self._send_json({"success": True, "voice_model": model_rel})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == '/api/models/download':
            model_key = data.get('model_key')
            if not model_key:
                self._send_json({"error": "No model_key specified"}, 400)
                return
            with model_download_lock:
                if model_download_state["status"] == "downloading":
                    self._send_json({"error": "Pengunduhan model lain sedang berjalan."}, 400)
                    return
            t = threading.Thread(target=_bg_download_model, args=(model_key,), daemon=True)
            t.start()
            self._send_json({"success": True, "message": f"Mulai mengunduh {model_key}"})

        elif path == '/api/start':
            model = data.get('model')
            if not model:
                self._send_json({"success": False, "error": "No model specified"}, 400)
                return
            try:
                start_llama_server(model)
                self._send_json({"success": True, "model": model})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == '/api/stop':
            stop_llama_server()
            self._send_json({"success": True})

        elif path == '/api/chat':
            if current_process is None or current_process.poll() is not None:
                ok, err = ensure_model_running()
                if not ok:
                    self._send_json({"error": f"LLM Server is not running: {err}"}, 400)
                    return

            messages = data.get('messages', [])
            rag_override = data.get('rag_enabled', None)
            augmented_messages, rag_sources = augment_messages_with_rag(messages, top_k=3, enabled_override=rag_override)

            payload = json.dumps({
                "messages": augmented_messages,
                "stream": False
            }).encode('utf-8')

            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{LLAMA_PORT}/v1/chat/completions",
                    data=payload,
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    res_data = json.loads(resp.read().decode('utf-8'))
                    if rag_sources:
                        res_data['rag_sources'] = rag_sources
                    self._send_json(res_data)
            except Exception as e:
                self._send_json({"error": f"Llama-server error: {str(e)}"}, 500)

        elif path == '/api/rag/upload':
            filename = data.get('filename') or data.get('name')
            b64_content = data.get('content_base64') or data.get('content')
            text_content = data.get('text')
            if not filename:
                self._send_json({"success": False, "error": "Nama file wajib diisi."}, 400)
                return
            try:
                if b64_content:
                    if ',' in b64_content:
                        b64_content = b64_content.split(',', 1)[1]
                    file_bytes = base64.b64decode(b64_content)
                elif text_content is not None:
                    file_bytes = text_content.encode('utf-8')
                else:
                    self._send_json({"success": False, "error": "Konten file kosong."}, 400)
                    return
                res = rag_engine.add_document(filename, file_bytes)
                self._send_json({"success": True, "data": res})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == '/api/rag/delete':
            doc_id = data.get('doc_id')
            if not doc_id:
                self._send_json({"success": False, "error": "ID dokumen tidak ditemukan."}, 400)
                return
            try:
                ok = rag_engine.delete_document(int(doc_id))
                self._send_json({"success": ok})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == '/api/rag/search':
            query = data.get('query', '').strip()
            top_k = int(data.get('top_k', 3))
            if not query:
                self._send_json({"success": False, "error": "Query pencarian kosong."}, 400)
                return
            try:
                hits = rag_engine.search(query, top_k=top_k)
                self._send_json({"success": True, "hits": hits})
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == '/api/rag/toggle':
            enabled = data.get('enabled')
            val = "1" if enabled else "0"
            save_env_value("RAG_ENABLED", val)
            self._send_json({"success": True, "rag_enabled": (val == "1")})

        elif path == '/api/voice/transcribe':
            audio_b64 = data.get('audio')
            if not audio_b64:
                self._send_json({"error": "No audio data provided"}, 400)
                return
            try:
                audio_bytes = base64.b64decode(audio_b64)
                text = transcribe_audio(audio_bytes)
                self._send_json({"text": text or ""})
            except Exception as e:
                self._send_json({"error": f"Whisper error: {str(e)}"}, 500)

        elif path == '/api/voice/synthesize':
            text = data.get('text', '')
            if not text:
                self._send_json({"error": "No text provided"}, 400)
                return
            clean_text = text[:400]
            
            custom_params = {}
            if "length_scale" in data: custom_params["VOICE_LENGTH_SCALE"] = data["length_scale"]
            if "noise_scale" in data: custom_params["VOICE_NOISE_SCALE"] = data["noise_scale"]
            if "noise_w" in data: custom_params["VOICE_NOISE_W"] = data["noise_w"]
            if "sentence_silence" in data: custom_params["VOICE_SENTENCE_SILENCE"] = data["sentence_silence"]
            if "voice_model" in data and data["voice_model"]: custom_params["VOICE_MODEL"] = data["voice_model"]
            if "engine" in data and data["engine"]: custom_params["TTS_ENGINE"] = data["engine"]
            if "edge_voice" in data and data["edge_voice"]: custom_params["EDGE_VOICE"] = data["edge_voice"]
            if "kokoro_voice" in data and data["kokoro_voice"]: custom_params["KOKORO_VOICE"] = data["kokoro_voice"]
            if "auto_adapt_lang" in data: custom_params["auto_adapt_lang"] = data["auto_adapt_lang"]

            try:
                res = synthesize_speech(clean_text, custom_params=custom_params)
                det_lang, used_v = "id", ""
                if isinstance(res, tuple):
                    if len(res) == 4:
                        audio_bytes, mime_type, det_lang, used_v = res
                    elif len(res) == 2:
                        audio_bytes, mime_type = res
                else:
                    audio_bytes, mime_type = res, "audio/wav"

                if audio_bytes:
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                    self._send_json({
                        "audio": audio_b64,
                        "mime_type": mime_type,
                        "format": mime_type,
                        "detected_lang": det_lang,
                        "voice_used": used_v
                    })
                else:
                    self._send_json({"error": "TTS synthesis failed"}, 500)
            except Exception as e:
                self._send_json({"error": f"TTS error: {str(e)}"}, 500)
        else:
            self.send_response(404)
            self.end_headers()

def main():
    cfg = load_env()
    port = cfg.get("APP_PORT", 3000)
    print(f"==================================================")
    print(f" Edge Studio aktif di: http://127.0.0.1:{port}")
    print(f" OpenAI-Compatible API Base: http://127.0.0.1:{port}/v1")
    print(f" Chat Completions: http://127.0.0.1:{port}/v1/chat/completions")
    print(f" Mode Realtime Voice (Barge-in / Sela) & Multilingual Studio")
    print(f" Tekan Ctrl+C untuk keluar.")
    print(f"==================================================")
    server = HTTPServer(('127.0.0.1', port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_llama_server()
        server.server_close()

if __name__ == '__main__':
    main()
