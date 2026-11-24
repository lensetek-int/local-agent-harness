"""
Official llama.cpp Built-in WebUI Plugin for Lensetek Agent
Launches and opens the native Web GUI served directly by llama-server (Llama Chat).
"""

from __future__ import annotations
import webbrowser
from typing import Any, Dict

def open_llama_webui(port: int = 8081) -> str:
    """Membuka antarmuka Web GUI bawaan resmi llama.cpp di peramban web."""
    url = f"http://127.0.0.1:{port}"
    try:
        webbrowser.open(url)
        return f"Web GUI resmi llama.cpp berhasil dibuka di browser: {url}"
    except Exception as e:
        return f"Gagal membuka browser otomatis ({e}). Silakan akses manual di: {url}"

def register_tools(ctx: Dict[str, Any]) -> list:
    """Mendaftarkan tool pembuka llama-server Web GUI ke ekosistem agen."""
    def open_webui() -> str:
        """Buka antarmuka Web GUI bawaan resmi llama-server (Llama Chat) di browser default."""
        cfg = ctx.get("config")
        port = getattr(cfg, "DEFAULT_PORT", 8081)
        return open_llama_webui(port=port)

    return [
        {
            "name": "open_webui",
            "description": "Buka antarmuka Web GUI bawaan resmi dari runtime llama.cpp / llama-server di browser lokal.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            },
            "handler": open_webui
        }
    ]
