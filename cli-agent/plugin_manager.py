"""
Plugin Manager for Lensetek Agent Harness
Handles on-demand plugin discovery, pagination, installation, uninstallation,
scaffolding, and runtime hook loading.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config
from i18n import t

MANIFEST_REL_PATH = Path("plugins") / "manifest.json"
TEMPLATE_REL_PATH = Path("plugins") / "_template"

def get_plugins_dir() -> Path:
    """Mengembalikan direktori penyimpanan plugin lokal."""
    # Prioritaskan folder plugins/ di REPO_ROOT jika dapat ditulis
    repo_plugins = config.REPO_ROOT / "plugins"
    if repo_plugins.exists() and os.access(repo_plugins, os.W_OK):
        return repo_plugins

    # Fallback ke direktori home ~/.lensetek-agent/plugins
    home_plugins = Path.home() / ".lensetek-agent" / "plugins"
    home_plugins.mkdir(parents=True, exist_ok=True)
    return home_plugins

def load_manifest() -> Dict[str, Any]:
    """Membaca katalog manifest.json lokal atau fallback ke remote GitHub."""
    local_manifest = config.REPO_ROOT / MANIFEST_REL_PATH
    if local_manifest.exists():
        try:
            with open(local_manifest, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Cek di folder home plugins
    home_manifest = get_plugins_dir() / "manifest.json"
    if home_manifest.exists():
        try:
            with open(home_manifest, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Remote fetch fallback
    remote_url = "https://raw.githubusercontent.com/lensetek-int/local-agent-harness/main/plugins/manifest.json"
    try:
        req = urllib.request.Request(remote_url, headers={"User-Agent": "LensetekAgent/2.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception:
        pass

    return {"version": "1.0.0", "plugins": []}

def list_installed_plugin_ids() -> List[str]:
    """Mengembalikan list ID plugin yang terpasang."""
    st = config.load_user_settings()
    recorded = set(st.get("installed_plugins", []))

    # Cek juga keberadaan fisik folder dengan plugin.json
    plugins_dir = get_plugins_dir()
    if plugins_dir.exists():
        for d in plugins_dir.iterdir():
            if d.is_dir() and not d.name.startswith("_") and (d / "plugin.json").exists():
                recorded.add(d.name)

    # Cek di repo_root/plugins jika berbeda
    if config.REPO_ROOT != plugins_dir.parent:
        repo_p = config.REPO_ROOT / "plugins"
        if repo_p.exists():
            for d in repo_p.iterdir():
                if d.is_dir() and not d.name.startswith("_") and (d / "plugin.json").exists():
                    recorded.add(d.name)

    return sorted(list(recorded))

def get_all_catalog_plugins() -> List[Dict[str, Any]]:
    """Mengambil daftar seluruh plugin dari manifest dan mendeteksi status terpasangnya."""
    manifest = load_manifest()
    plugins = manifest.get("plugins", [])
    installed_ids = set(list_installed_plugin_ids())

    results = []
    for p in plugins:
        item = dict(p)
        item["is_installed"] = item.get("id") in installed_ids
        results.append(item)
    return results

def get_paginated_plugins(
    page: int = 1,
    page_size: int = 5,
    category: str = "",
    search_query: str = "",
    lang: str = "en"
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Mengembalikan: (list_item_halaman_ini, total_item, total_halaman)
    Mendukung penyaringan berdasarkan kategori dan pencarian kata kunci.
    """
    all_plugins = get_all_catalog_plugins()

    # Filter pencarian
    filtered = []
    cat_filter = category.strip().lower()
    q_filter = search_query.strip().lower()

    for item in all_plugins:
        p_id = item.get("id", "").lower()
        p_name = item.get("name", "").lower()
        p_cat = item.get("category", "").lower()
        p_desc = item.get(f"description_{lang}", item.get("description", "")).lower()

        if cat_filter and cat_filter != "all" and p_cat != cat_filter:
            continue

        if q_filter:
            if q_filter not in p_id and q_filter not in p_name and q_filter not in p_desc and q_filter not in p_cat:
                continue

        filtered.append(item)

    total_items = len(filtered)
    total_pages = max(1, math.ceil(total_items / page_size))
    current_page = max(1, min(page, total_pages))

    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = filtered[start_idx:end_idx]

    return page_items, total_items, total_pages

def resolve_plugin_target(target: str, page_items: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """
    Mencari plugin dari nomor urut halaman, nama pendek, alias, atau ID unik.
    """
    target_clean = target.strip().lower()
    if not target_clean:
        return None

    # 1. Jika nomor urut (1..N) pada page_items
    if page_items and target_clean.isdigit():
        idx = int(target_clean) - 1
        if 0 <= idx < len(page_items):
            return page_items[idx]

    # 2. Cari di seluruh katalog manifest
    all_plugins = get_all_catalog_plugins()
    if target_clean.isdigit():
        idx = int(target_clean) - 1
        if 0 <= idx < len(all_plugins):
            return all_plugins[idx]

    for p in all_plugins:
        p_id = p.get("id", "").lower()
        p_name = p.get("name", "").lower()
        if target_clean == p_id or target_clean in p_id or target_clean in p_name:
            return p

    return None

def install_plugin(target: str, lang: str = "en") -> Tuple[bool, str]:
    """
    Memasang plugin berdasarkan nomor urut atau ID/nama.
    Menyalin dari folder template/repo atau mengunduh dan memasang dependensi python.
    """
    plugin = resolve_plugin_target(target)
    if not plugin:
        return False, t("plugin_not_found", lang, query=target)

    plugin_id = plugin.get("id")
    plugin_name = plugin.get("name", plugin_id)
    folder_rel = plugin.get("folder", f"plugins/{plugin_id}")

    target_dir = get_plugins_dir() / plugin_id
    src_dir = config.REPO_ROOT / folder_rel

    try:
        # Jika folder lokal sudah ada di REPO_ROOT (misal di clone repo)
        if src_dir.exists() and src_dir != target_dir:
            shutil.copytree(src_dir, target_dir, dirs_exist_ok=True)
        elif not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            # Salin manifest / plugin.json minimal jika baru
            meta = {
                "id": plugin_id,
                "name": plugin_name,
                "version": plugin.get("version", "1.0.0"),
                "category": plugin.get("category", "tools"),
                "entry_point": plugin.get("entry_point", "main.py")
            }
            with open(target_dir / "plugin.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

        # Pasang dependensi python jika ada requirements.txt
        req_file = target_dir / "requirements.txt"
        if not req_file.exists() and src_dir.exists() and (src_dir / "requirements.txt").exists():
            req_file = src_dir / "requirements.txt"

        if req_file.exists() and req_file.stat().st_size > 0:
            print(f"\n[i] Memasang dependensi plugin '{plugin_name}' ({req_file.name})...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", "-r", str(req_file)],
                check=False
            )

        # Update user settings
        st = config.load_user_settings()
        installed = st.get("installed_plugins", [])
        if plugin_id not in installed:
            installed.append(plugin_id)
            st["installed_plugins"] = installed
            config.save_user_settings(st)

        return True, t("plugin_install_success", lang, name=plugin_name)
    except Exception as e:
        return False, f"Gagal memasang plugin: {e}"

def uninstall_plugin(target: str, lang: str = "en") -> Tuple[bool, str]:
    """Menghapus plugin dari daftar aktif dan membersihkan direktori lokalnya."""
    plugin = resolve_plugin_target(target)
    if not plugin:
        # Coba cari dari folder lokal langsung
        p_id = target.strip().lower()
    else:
        p_id = plugin.get("id")

    p_name = plugin.get("name", p_id) if plugin else p_id

    st = config.load_user_settings()
    installed = st.get("installed_plugins", [])
    if p_id in installed:
        installed.remove(p_id)
        st["installed_plugins"] = installed
        config.save_user_settings(st)

    target_dir = get_plugins_dir() / p_id
    if target_dir.exists() and target_dir.is_dir():
        try:
            shutil.rmtree(target_dir)
        except Exception:
            pass

    return True, t("plugin_uninstall_success", lang, name=p_name)

def create_plugin_scaffold(
    plugin_id: str,
    name: str = "",
    category: str = "tools",
    author: str = "Community",
    lang: str = "en"
) -> Tuple[bool, str, Optional[Path]]:
    """
    Membuat kerangka kerja plugin baru dari plugins/_template/.
    Digunakan oleh perintah '/plugins create' dan Skill Plugin Maker.
    """
    clean_id = plugin_id.strip().lower().replace(" ", "-")
    if not clean_id:
        return False, "Plugin ID tidak boleh kosong.", None

    dest_dir = (config.REPO_ROOT / "plugins" / clean_id).resolve()
    if dest_dir.exists():
        return False, f"Direktori plugin '{clean_id}' sudah ada di {dest_dir}.", dest_dir

    template_dir = config.REPO_ROOT / TEMPLATE_REL_PATH
    if not template_dir.exists():
        return False, f"Template blueprint tidak ditemukan di {template_dir}.", None

    try:
        shutil.copytree(template_dir, dest_dir)

        # Update metadata di plugin.json
        meta_path = dest_dir / "plugin.json"
        meta = {
            "id": clean_id,
            "name": name or clean_id.replace("-", " ").title(),
            "version": "1.0.0",
            "category": category or "tools",
            "author": author or "Lensetek Contributor",
            "description": f"Custom plugin {clean_id} for Lensetek Harness.",
            "description_id": f"Plugin kustom {clean_id} untuk Lensetek Harness.",
            "description_cn": f"Lensetek Harness 的自定义插件 {clean_id}。",
            "entry_point": "main.py",
            "dependencies": [],
            "permissions": ["workspace_read"]
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # Daftarkan ke manifest.json lokal jika ada
        manifest_path = config.REPO_ROOT / MANIFEST_REL_PATH
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                plugins_list = manifest_data.get("plugins", [])
                if not any(p.get("id") == clean_id for p in plugins_list):
                    plugins_list.append({
                        "id": clean_id,
                        "name": meta["name"],
                        "version": meta["version"],
                        "category": meta["category"],
                        "author": meta["author"],
                        "description": meta["description"],
                        "description_id": meta["description_id"],
                        "description_cn": meta["description_cn"],
                        "entry_point": meta["entry_point"],
                        "folder": f"plugins/{clean_id}",
                        "dependencies": meta["dependencies"],
                        "permissions": meta["permissions"]
                    })
                    manifest_data["plugins"] = plugins_list
                    with open(manifest_path, "w", encoding="utf-8") as f:
                        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        return True, t("plugin_created_success", lang, id=clean_id, path=str(dest_dir)), dest_dir
    except Exception as e:
        return False, f"Gagal membuat kerangka plugin: {e}", None

def load_installed_tools(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Memuat dan mendaftarkan tools dari seluruh plugin yang terpasang dan aktif.
    """
    installed_ids = list_installed_plugin_ids()
    all_tools = []

    plugins_dir = get_plugins_dir()
    for p_id in installed_ids:
        p_path = plugins_dir / p_id
        if not p_path.exists():
            p_path = config.REPO_ROOT / "plugins" / p_id
        if not p_path.exists():
            continue

        meta_file = p_path / "plugin.json"
        entry_file = "main.py"
        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    m = json.load(f)
                    entry_file = m.get("entry_point", "main.py")
            except Exception:
                pass

        target_module = p_path / entry_file
        if not target_module.exists():
            continue

        try:
            mod_name = f"lensetek_plugin_{p_id.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(mod_name, str(target_module))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                spec.loader.exec_module(module)

                # Jalankan hook on_load jika ada
                if hasattr(module, "on_load"):
                    try:
                        module.on_load(context)
                    except Exception:
                        pass

                # Daftarkan tools jika ada
                if hasattr(module, "register_tools"):
                    tools = module.register_tools()
                    if isinstance(tools, list):
                        all_tools.extend(tools)
        except Exception as e:
            # Skip plugin yang error agar base harness tetap aman
            continue

    return all_tools
