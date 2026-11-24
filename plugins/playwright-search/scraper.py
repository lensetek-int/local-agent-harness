"""
Playwright Dynamic Web Research Tool for Lensetek
Headless Chromium scraper with Smart Text Cleaner specifically tuned for 3B SLM context windows.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

def clean_html_to_markdown(html_text: str) -> str:
    """Membersihkan raw HTML menjadi teks Markdown ringkas & padat."""
    if not html_text:
        return ""

    # Buang tag script, style, svg, iframe, noscript
    cleaned = re.sub(r"<(script|style|svg|iframe|noscript)[^>]*>.*?</\1>", " ", html_text, flags=re.DOTALL | re.IGNORECASE)
    # Buang komentar HTML
    cleaned = re.sub(r"<!--.*?-->", " ", cleaned, flags=re.DOTALL)
    # Konversi heading
    cleaned = re.sub(r"<h[1-2][^>]*>(.*?)</h[1-2]>", r"\n\n## \1\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<h[3-6][^>]*>(.*?)</h[3-6]>", r"\n\n### \1\n", cleaned, flags=re.IGNORECASE)
    # Konversi link
    cleaned = re.sub(r"<a\s+(?:[^>]*?\s+)?href=[\"'](.*?)[\"'][^>]*>(.*?)</a>", r"[\2](\1)", cleaned, flags=re.IGNORECASE)
    # Konversi paragraf & baris baru
    cleaned = re.sub(r"</p>", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<li[^>]*>(.*?)</li>", r"\n* \1", cleaned, flags=re.IGNORECASE)
    # Buang seluruh tag HTML yang tersisa
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Normalisasi spasi dan baris kosong
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()

def fetch_dynamic_webpage(url: str, max_chars: int = 4000) -> str:
    """Membuka halaman web dinamis dengan Playwright headless dan mengembalikan teks bersih."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (
            "Error: Pustaka 'playwright' belum terpasang.\n"
            "Silakan instal dengan: pip install playwright && playwright install chromium"
        )

    url_clean = url.strip()
    if not url_clean.startswith(("http://", "https://")):
        url_clean = "https://" + url_clean

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page.goto(url_clean, timeout=25000, wait_until="domcontentloaded")
            # Tunggu rendering konten utama maksimal 2 detik
            try:
                page.wait_for_timeout(2000)
            except Exception:
                pass

            title = page.title()
            html_content = page.content()
            browser.close()

            text_md = clean_html_to_markdown(html_content)
            if len(text_md) > max_chars:
                text_md = text_md[:max_chars] + f"\n\n... [Konten dipotong agar hemat context window model 3B - Total: {len(text_md)} karakter]"

            return f"# {title}\nURL: {url_clean}\n\n{text_md}"
    except Exception as e:
        return f"Gagal mengekstrak web '{url_clean}' dengan Playwright: {e}"

def handle_browser_research(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Handler tool untuk LLM agent."""
    url = args.get("url", "")
    max_c = args.get("max_chars", 4000)
    if not url:
        return "Error: Argumen 'url' wajib diisi."
    return fetch_dynamic_webpage(url, max_chars=int(max_c))

def register_tools() -> List[Dict[str, Any]]:
    """Mendaftarkan tool browser_research ke sistem agen."""
    return [
        {
            "name": "browser_research",
            "description": "Buka URL website dinamis (JavaScript/React/SPA) menggunakan headless Chromium Playwright dan ambil konten artikel bersih dalam format Markdown terkompresi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL halaman web yang ingin diekstrak (contoh: 'https://news.ycombinator.com')"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Batas maksimal karakter teks hasil ekstrak (default: 4000, hemat token 3B)"
                    }
                },
                "required": ["url"]
            },
            "handler": handle_browser_research
        }
    ]

def on_load(context: Dict[str, Any]) -> bool:
    return True

def on_unload(context: Dict[str, Any]) -> None:
    pass
