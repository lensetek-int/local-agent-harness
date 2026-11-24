import os
import re
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def clean_bing_url(raw_url: str) -> str:
    """Mendekode URL target langsung dari redirect Bing jika ada parameter base64 'u'."""
    try:
        parsed = urllib.parse.urlparse(raw_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "u" in qs:
            u_val = qs["u"][0]
            if u_val.startswith("a1"):
                u_val = u_val[2:]
            rem = len(u_val) % 4
            if rem > 0:
                u_val += "=" * (4 - rem)
            decoded = base64.urlsafe_b64decode(u_val).decode("utf-8", errors="ignore")
            if decoded.startswith("http://") or decoded.startswith("https://"):
                return decoded
    except Exception:
        pass
    return raw_url

def search_bing(query: str, num_results: int = 4) -> list[dict]:
    """Pencarian web headless cepat via Bing (bebas blokir ISP Indonesia)."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.bing.com/search?q={encoded_query}&setlang=en-US"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8"
        }
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        if HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")
            for li in soup.find_all("li", class_="b_algo"):
                h2 = li.find("h2")
                if not h2:
                    continue
                a = h2.find("a")
                if not a or not a.get("href"):
                    continue
                title = a.get_text(strip=True)
                raw_href = a.get("href")
                direct_url = clean_bing_url(raw_href)

                snippet_el = li.find("p") or li.find("div", class_="b_caption")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                if direct_url and title:
                    results.append({
                        "title": title,
                        "url": direct_url,
                        "snippet": snippet[:250]
                    })
                    if len(results) >= num_results:
                        break
        else:
            # Fallback regex sederhana
            matches = re.findall(r'<li class="b_algo".*?<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>', html, re.DOTALL)
            for raw_href, raw_title in matches[:num_results]:
                clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
                direct_url = clean_bing_url(raw_href)
                results.append({
                    "title": clean_title,
                    "url": direct_url,
                    "snippet": ""
                })
    except Exception as e:
        print(f"[DEBUG search_bing] {e}")

    return results

def search_google(query: str, num_results: int = 4) -> list[dict]:
    """Pencarian web headless cadangan via Google Search."""
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded_query}&hl=en&num={num_results}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9"
        }
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        if HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")
            for g in soup.find_all("div", class_="tF2Cxc"):
                a = g.find("a")
                h3 = g.find("h3")
                if not a or not h3:
                    continue
                link = a.get("href", "")
                title = h3.get_text(strip=True)
                snippet_el = g.find("div", class_="VwiC3b")
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                if link.startswith("http") and title:
                    results.append({
                        "title": title,
                        "url": link,
                        "snippet": snippet[:250]
                    })
                    if len(results) >= num_results:
                        break
    except Exception as e:
        print(f"[DEBUG search_google] {e}")

    return results

def headless_web_search(query: str, num_results: int = 4) -> list[dict]:
    """Melakukan pencarian web multi-provider headless (Bing -> Google fallback)."""
    num_results = min(max(1, int(num_results)), 8)
    query = query.strip()
    if not query:
        return []

    # 1. Coba Bing (sangat cepat & stabil)
    res = search_bing(query, num_results=num_results)
    if res:
        return res

    # 2. Fallback Google
    res_google = search_google(query, num_results=num_results)
    if res_google:
        return res_google

    return []

def format_search_results(results: list[dict], query: str = "") -> str:
    """Memformat hasil pencarian menjadi teks ringkas hemat token untuk LLM (~250 token)."""
    if not results:
        return f"Tidak ditemukan hasil pencarian web untuk: '{query}'."

    lines = [f"Hasil pencarian web untuk '{query}':\n"]
    for idx, item in enumerate(results, start=1):
        lines.append(f"[{idx}] {item['title']}")
        lines.append(f"    URL: {item['url']}")
        if item.get("snippet"):
            lines.append(f"    Snippet: {item['snippet']}")
        lines.append("")

    lines.append("Tips: Untuk membaca isi lengkap dari salah satu URL di atas, gunakan MCP fetch (`mcp_call` dengan server='fetch').")
    return "\n".join(lines).strip()


class WebSearchTool:
    def __init__(self):
        pass

    def get_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Mencari informasi terkini dari internet, dokumentasi teknis, atau solusi error secara headless (tanpa membuka browser GUI).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Kata kunci pencarian web"},
                        "num_results": {"type": "integer", "description": "Jumlah hasil (default: 4, maksimal: 8)"}
                    },
                    "required": ["query"]
                }
            }
        }

    def execute(self, args: dict) -> str:
        q = args.get("query", "").strip()
        num = args.get("num_results", 4)
        if not q:
            return "Error: Parameter 'query' tidak boleh kosong."
        results = headless_web_search(q, num_results=num)
        return format_search_results(results, query=q)
