import os
import sys
import argparse
import threading
from pathlib import Path

# Aktifkan dukungan ANSI escape sequences di Windows terminal
os.system("")

import config
try:
    import version
except ImportError:
    try:
        from cli_agent import version
    except ImportError:
        version = None
from server_manager import LlamaServerManager
from tools_fs import LocalWorkspaceTools
from mcp_client import MCPManager
from skills_manager import SkillManager
from scheduler import TaskScheduler
from web_search import headless_web_search, format_search_results
from session_manager import SessionManager
from agent import LeanAgent
try:
    import plugin_manager
except ImportError:
    try:
        from cli_agent import plugin_manager
    except ImportError:
        plugin_manager = None
try:
    from i18n import t, get_localized_slash_items
except ImportError:
    try:
        from cli_agent.i18n import t, get_localized_slash_items
    except ImportError:
        def t(key, lang="en", **kwargs):
            return key
        def get_localized_slash_items(lang="en"):
            return []

# Integrasi prompt_toolkit untuk interactive autocomplete / suggestions saat mengetik '/'
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.shortcuts import CompleteStyle
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

# Kode warna ANSI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"

def get_slash_items(skills_mgr: SkillManager, lang: str = "en") -> list[tuple[str, str, str]]:
    """Mengembalikan daftar semua slash commands dan skills untuk autocomplete sesuai bahasa aktif."""
    items = get_localized_slash_items(lang)

    try:
        all_skills = skills_mgr.scan_skills()
        for slug, s_data in all_skills.items():
            cmd = f"/{slug}"
            desc = s_data.get("description", "Activate skill" if lang == "en" else "Aktivasi skill")
            src = s_data.get("source", "skill").upper()
            items.append((cmd, desc, src))
    except Exception:
        pass

    return items

if HAS_PROMPT_TOOLKIT:
    class SlashCommandCompleter(Completer):
        def __init__(self, get_items_fn, get_lang_fn=None, get_files_fn=None):
            self.get_items_fn = get_items_fn
            self.get_lang_fn = get_lang_fn or (lambda: "en")
            self.get_files_fn = get_files_fn

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor

            # Handle '@' file mention anywhere in the input
            import re as _re
            at_match = _re.search(r'(?:^|\s)(@[^\s]*)$', text)
            if at_match and self.get_files_fn:
                token = at_match.group(1)
                query = token[1:].lower()
                files = self.get_files_fn()
                count = 0
                for f in files:
                    fpath = f.get("path", "")
                    if not query or query in fpath.lower():
                        ins_text = f'@"{fpath}"' if " " in fpath else f"@{fpath}"
                        yield Completion(
                            ins_text,
                            start_position=-len(token),
                            display=f"@{fpath}",
                            display_meta=f"FILE • {f.get('size', '')}",
                        )
                        count += 1
                        if count >= 20:
                            break
                return

            if not text.startswith("/"):
                return

            cur_lang = self.get_lang_fn()

            if " " in text:
                tokens = text.split()
                first_word = tokens[0].lower()
                trailing_space = text.endswith(" ")

                if first_word == "/model":
                    sub = "" if trailing_space else (tokens[1].lower() if len(tokens) >= 2 else "")
                    model_subs = [
                        ("search", t("model_sub_search", cur_lang)),
                        ("download", t("model_sub_download", cur_lang)),
                        ("add", t("model_sub_add", cur_lang)),
                        ("remove", t("model_sub_remove", cur_lang))
                    ]
                    for sc, desc in model_subs:
                        if not sub or sc.startswith(sub):
                            start_pos = 0 if trailing_space or len(tokens) < 2 else -len(tokens[1])
                            yield Completion(sc, start_position=start_pos, display=sc, display_meta=desc)
                    return

                elif first_word == "/effort":
                    sub = "" if trailing_space else (tokens[1].lower() if len(tokens) >= 2 else "")
                    effort_subs = [
                        ("off", t("effort_sub_off", cur_lang)),
                        ("low", t("effort_sub_low", cur_lang)),
                        ("medium", t("effort_sub_medium", cur_lang)),
                        ("high", t("effort_sub_high", cur_lang))
                    ]
                    for sc, desc in effort_subs:
                        if not sub or sc.startswith(sub):
                            start_pos = 0 if trailing_space or len(tokens) < 2 else -len(tokens[1])
                            yield Completion(sc, start_position=start_pos, display=sc, display_meta=desc)
                    return

                elif first_word == "/mcp":
                    sub = "" if trailing_space else (tokens[1].lower() if len(tokens) >= 2 else "")
                    mcp_subs = [
                        ("install", t("mcp_sub_install", cur_lang)),
                        ("test", t("mcp_sub_test", cur_lang)),
                        ("remove", t("mcp_sub_remove", cur_lang)),
                        ("enable", t("mcp_sub_enable", cur_lang)),
                        ("disable", t("mcp_sub_disable", cur_lang))
                    ]
                    for sc, desc in mcp_subs:
                        if not sub or sc.startswith(sub):
                            start_pos = 0 if trailing_space or len(tokens) < 2 else -len(tokens[1])
                            yield Completion(sc, start_position=start_pos, display=sc, display_meta=desc)
                    return

                elif first_word == "/language":
                    sub = "" if trailing_space else (tokens[1].lower() if len(tokens) >= 2 else "")
                    lang_opts = [
                        ("en", "English (Default)"),
                        ("id", "Bahasa Indonesia"),
                        ("cn", "简体中文 (Chinese)")
                    ]
                    for lc, ldesc in lang_opts:
                        if not sub or lc.startswith(sub):
                            start_pos = 0 if trailing_space or len(tokens) < 2 else -len(tokens[1])
                            yield Completion(lc, start_position=start_pos, display=lc, display_meta=ldesc)
                    return

                elif first_word == "/session":
                    sub = "" if trailing_space else (tokens[1].lower() if len(tokens) >= 2 else "")
                    session_subs = [
                        ("list", t("session_sub_list", cur_lang)),
                        ("new", t("session_sub_new", cur_lang)),
                        ("switch", t("session_sub_switch", cur_lang)),
                        ("rename", t("session_sub_rename", cur_lang)),
                        ("delete", t("session_sub_delete", cur_lang))
                    ]
                    for sc, desc in session_subs:
                        if not sub or sc.startswith(sub):
                            start_pos = 0 if trailing_space or len(tokens) < 2 else -len(tokens[1])
                            yield Completion(sc, start_position=start_pos, display=sc, display_meta=desc)
                    return
                return

            query = text.lower()
            items = self.get_items_fn()

            prefix_matches = []
            sub_matches = []
            for cmd, desc, cat in items:
                cmd_lower = cmd.lower()
                if cmd_lower.startswith(query):
                    prefix_matches.append((cmd, desc, cat))
                elif query in cmd_lower:
                    sub_matches.append((cmd, desc, cat))

            for cmd, desc, cat in prefix_matches + sub_matches:
                yield Completion(
                    text=cmd + " ",
                    start_position=-len(text),
                    display=cmd,
                    display_meta=f"[{cat}] {desc[:55]}"
                )

def print_banner(workspace: Path, model_name: str, ctx_size: int, port: int, mcp_names: list[str], safety_mode: str, skills_count: int, language: str, effort: str = "medium", update_info: dict | None = None, session_name: str = "Default Session"):
    lang_name = config.SUPPORTED_LANGUAGES.get(language, language.upper())
    skills_lbl = t("banner_skills_detected", language)
    tip_lbl = t("banner_tip", language)
    ver_str = f"v{version.APP_VERSION}" if version else ""
    print(f"{C_CYAN}{C_BOLD}===================================================================={C_RESET}")
    print(f"{C_CYAN}{C_BOLD}        ⚡ LENSETEK LEAN AGENT HARNESS {ver_str:<10}                  {C_RESET}")
    print(f"{C_CYAN}{C_BOLD}===================================================================={C_RESET}")
    if update_info and update_info.get("update_available"):
        lat_v = update_info.get("latest_version")
        notice = t("update_notice_banner", language, ver=lat_v)
        print(f" {C_BOLD}{C_YELLOW}{notice}{C_RESET}")
        print(f"{C_CYAN}--------------------------------------------------------------------{C_RESET}")
    print(f" {C_BOLD}Session:{C_RESET}   {session_name} {C_DIM}(/session){C_RESET}")
    print(f" {C_BOLD}Workspace:{C_RESET} {workspace}")
    print(f" {C_BOLD}Model:{C_RESET}     {model_name} {C_DIM}(port: {port}, ctx: {ctx_size}){C_RESET}")
    print(f" {C_BOLD}Effort:{C_RESET}    [{effort.upper()}] {C_DIM}(/effort off|low|medium|high){C_RESET}")
    print(f" {C_BOLD}Language:{C_RESET}  [{language.upper()}] {lang_name} {C_DIM}(/language en|id|cn){C_RESET}")
    print(f" {C_BOLD}Safety:{C_RESET}    [{safety_mode.upper()}] {C_DIM}(/strict, /auto-approve, /yolo){C_RESET}")
    print(f" {C_BOLD}Web Search:{C_RESET}{C_GREEN} Headless Active {C_DIM}(web_search tool & /search <q>){C_RESET}")
    print(f" {C_BOLD}MCP:{C_RESET}       {', '.join(mcp_names) if mcp_names else 'None'}")
    print(f" {C_BOLD}Skills:{C_RESET}    {skills_count} {skills_lbl} {C_DIM}(type '/' and press Tab to autocomplete){C_RESET}")
    print(f" {C_DIM}{tip_lbl}{C_RESET}")
    print(f"{C_CYAN}--------------------------------------------------------------------{C_RESET}\n")

def print_help(lang: str = "en"):
    items = get_localized_slash_items(lang)
    title = t("help_title", lang)
    print(f"\n{C_BOLD}{title}{C_RESET}")
    for cmd, desc, cat in items:
        spacing = 38 - len(cmd)
        sp = " " * max(1, spacing)
        print(f"  {C_YELLOW}{cmd}{C_RESET}{sp}- {desc}")
    print()

def handle_update_cli(active_language: str, started_by_us: bool = False, server_mgr = None, mcp_mgr = None):
    """Mengecek dan mengeksekusi update aplikasi baik dari CLI flag maupun interactive /update."""
    if not version:
        print(f"{C_RED}[ERROR] Version & Update module not loaded.{C_RESET}\n")
        return

    print(f"\n{C_CYAN}⏳ {t('update_checking', active_language)}{C_RESET}")
    u_info = version.check_for_updates(timeout_sec=5.0, force_refresh=True)
    cur_v = u_info.get("current_version", version.APP_VERSION)
    latest_v = u_info.get("latest_version", cur_v)
    whats_new = u_info.get("whats_new", [])
    has_update = u_info.get("update_available", False)

    print(f"\n{C_BOLD}=== {t('update_header', active_language)} ==={C_RESET}")
    print(f"  • {C_BOLD}{t('update_current_ver', active_language)}:{C_RESET} {C_CYAN}v{cur_v}{C_RESET}")
    print(f"  • {C_BOLD}{t('update_latest_ver', active_language)}:{C_RESET} {C_GREEN}v{latest_v}{C_RESET}")

    if has_update:
        wn_title = t("update_whats_new_title", active_language, ver=latest_v)
        print(f"\n{C_BOLD}{C_YELLOW}★ {wn_title}{C_RESET}")
        for item in whats_new:
            print(f"  • {item}")

        confirm_lbl = t("update_confirm_prompt", active_language)
        try:
            ask_up = input(f"\n{C_BOLD}{confirm_lbl}{C_RESET}").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            ask_up = "n"

        if ask_up in ("", "y", "yes"):
            print(f"\n{C_CYAN}{t('update_in_progress', active_language)}{C_RESET}")
            ok, msg = version.perform_update()
            if ok:
                print(f"{C_GREEN}✓ {t('update_success', active_language)}{C_RESET}\n")
                if mcp_mgr:
                    mcp_mgr.close_all()
                if started_by_us and server_mgr:
                    server_mgr.stop()
                version.restart_application()
            else:
                err_msg = t("update_failed", active_language, error=msg)
                print(f"{C_RED}[ERROR] {err_msg}{C_RESET}\n")
        else:
            print(f"{C_DIM}{t('update_cancelled', active_language)}{C_RESET}\n")
    else:
        latest_msg = t("update_already_latest", active_language, ver=cur_v)
        print(f"\n{C_GREEN}✓ {latest_msg}{C_RESET}")
        wn_title = t("update_whats_new_title", active_language, ver=cur_v)
        print(f"\n{C_BOLD}{wn_title}{C_RESET}")
        for item in version.get_whats_new(cur_v):
            print(f"  • {item}")
        print()

def handle_uninstall_cli():
    """Hentikan proses llama-server/WebUI yang berjalan lalu hapus ~/.lensetek-agent dengan aman."""
    import shutil
    import subprocess
    import urllib.request

    install_dir = Path.home() / ".lensetek-agent"
    if not install_dir.exists():
        print(f"{C_YELLOW}[i] Direktori instalasi tidak ditemukan: {install_dir}{C_RESET}")
        return

    ans = input(f"{C_YELLOW}Hapus instalasi Lensetek di {install_dir}? [y/N]: {C_RESET}").strip().lower()
    if ans not in ("y", "yes"):
        print(f"{C_DIM}Uninstall dibatalkan.{C_RESET}")
        return

    # 1. Gracefully shutdown WebUI if running
    for port in range(3001, 3006):
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/shutdown",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=0.6)
        except Exception:
            pass

    # 2. Stop any llama-server processes before removing bin/
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/IM", "llama-server.exe"],
            capture_output=True,
            text=True,
        )
    else:
        subprocess.run(
            ["pkill", "-f", str(install_dir / "bin" / "llama-server")],
            capture_output=True,
            text=True,
        )

    # 3. Remove installation directory
    try:
        shutil.rmtree(install_dir)
        print(f"{C_GREEN}✓ Lensetek berhasil dihapus dari {install_dir}.{C_RESET}")
    except Exception as exc:
        if sys.platform == "win32":
            # Deferred cleanup after Python/cmd exits
            ps_cmd = f"Start-Sleep -Seconds 1; Remove-Item -LiteralPath '{install_dir}' -Recurse -Force -ErrorAction SilentlyContinue"
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            print(f"{C_GREEN}✓ Proses dihentikan. Pembersihan sisa file di {install_dir} akan selesai otomatis.{C_RESET}")
        else:
            print(f"{C_RED}[ERROR] Gagal menghapus {install_dir}: {exc}{C_RESET}")

def handle_plugins_cli(plugins_args: list[str], active_language: str):
    """Mengelola plugin langsung dari baris perintah (CLI flags)."""
    if not plugin_manager:
        print(f"{C_RED}[ERROR] Plugin manager module not loaded.{C_RESET}")
        return

    sub_cmd = plugins_args[0].lower() if plugins_args else "list"
    sub_val = plugins_args[1].strip() if len(plugins_args) > 1 else ""

    if sub_cmd in ("list", "ls"):
        items = plugin_manager.get_all_catalog_plugins()
        print(f"\n{C_BOLD}=== LENSETEK PLUGIN CATALOG ==={C_RESET}")
        print(f"  {'#':<3} {'ID':<20} {'Category':<10} {'Status':<12} {'Description'}")
        print(f"  {'-'*3} {'-'*20} {'-'*10} {'-'*12} {'-'*35}")
        for idx, itm in enumerate(items, start=1):
            p_id = itm.get("id", "")
            cat = f"[{itm.get('category', 'tools')}]"
            is_inst = itm.get("is_installed", False)
            stat = f"{C_GREEN}{t('plugin_status_installed', active_language)}{C_RESET}" if is_inst else f"{C_DIM}{t('plugin_status_available', active_language)}{C_RESET}"
            desc = itm.get(f"description_{active_language}", itm.get("description", ""))
            if len(desc) > 40:
                desc = desc[:37] + "..."
            print(f"  [{idx}] {C_BOLD}{p_id:<20}{C_RESET} {cat:<10} {stat:<20} {desc}")
        if active_language == "id":
            tip = "Gunakan: lensetek --plugins install <id> atau remove <id>"
        elif active_language == "cn":
            tip = "用法: lensetek --plugins install <id> 或 remove <id>"
        else:
            tip = "Usage: lensetek --plugins install <id> or remove <id>"
        print(f"\n{C_DIM}{tip}{C_RESET}\n")

    elif sub_cmd in ("install", "i", "add"):
        if not sub_val:
            msg = {
                "id": "Masukkan ID plugin yang ingin diinstal. Contoh: lensetek --plugins install webui",
                "cn": "请输入要安装的插件 ID。示例: lensetek --plugins install webui",
            }.get(active_language, "Specify a plugin ID to install. Example: lensetek --plugins install webui")
            print(f"{C_YELLOW}{msg}{C_RESET}")
            return
        ok, msg = plugin_manager.install_plugin(sub_val, lang=active_language)
        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")

    elif sub_cmd in ("remove", "rm", "uninstall", "delete"):
        if not sub_val:
            msg = {
                "id": "Masukkan ID plugin yang ingin dihapus. Contoh: lensetek --plugins remove webui",
                "cn": "请输入要卸载的插件 ID。示例: lensetek --plugins remove webui",
            }.get(active_language, "Specify a plugin ID to remove. Example: lensetek --plugins remove webui")
            print(f"{C_YELLOW}{msg}{C_RESET}")
            return
        ok, msg = plugin_manager.uninstall_plugin(sub_val, lang=active_language)
        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")

    elif sub_cmd in ("search", "find", "s"):
        if not sub_val:
            msg = {
                "id": "Masukkan kata kunci pencarian. Contoh: lensetek --plugins search web",
                "cn": "请输入搜索关键词。示例: lensetek --plugins search web",
            }.get(active_language, "Specify a search keyword. Example: lensetek --plugins search web")
            print(f"{C_YELLOW}{msg}{C_RESET}")
            return
        items = plugin_manager.get_all_catalog_plugins()
        q = sub_val.lower()
        matches = [p for p in items if q in p.get("id", "").lower() or q in p.get("name", "").lower() or q in p.get(f"description_{active_language}", p.get("description", "")).lower()]
        hdr = {
            "id": f"Hasil pencarian plugin untuk '{sub_val}':",
            "cn": f"'{sub_val}' 的插件搜索结果:",
        }.get(active_language, f"Plugin search results for '{sub_val}':")
        print(f"\n{C_BOLD}{hdr}{C_RESET}")
        for idx, itm in enumerate(matches, start=1):
            p_id = itm.get("id")
            is_inst = itm.get("is_installed", False)
            stat = f"{C_GREEN}{t('plugin_status_installed', active_language)}{C_RESET}" if is_inst else f"{C_DIM}{t('plugin_status_available', active_language)}{C_RESET}"
            desc = itm.get(f"description_{active_language}", itm.get("description", ""))
            print(f"  [{idx}] {C_BOLD}{p_id}{C_RESET} ({stat}) - {desc}")
        if not matches:
            empty_msg = {
                "id": "Tidak ditemukan plugin yang cocok.",
                "cn": "未找到匹配的插件。",
            }.get(active_language, "No matching plugins found.")
            print(f"  {C_DIM}{empty_msg}{C_RESET}")
        print()

    elif sub_cmd in ("create", "new"):
        if not sub_val:
            msg = {
                "id": "Masukkan nama/id plugin yang ingin dibuat. Contoh: lensetek --plugins create my-tool",
                "cn": "请输入要创建的插件名称。示例: lensetek --plugins create my-tool",
            }.get(active_language, "Specify a plugin name to create. Example: lensetek --plugins create my-tool")
            print(f"{C_YELLOW}{msg}{C_RESET}")
            return
        ok, msg, p_res = plugin_manager.create_plugin_scaffold(sub_val, lang=active_language)
        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")
    else:
        msg = {
            "id": f"Subperintah plugins tidak dikenal: '{sub_cmd}'. Pilihan: list, install <id>, remove <id>, search <q>, create <name>",
            "cn": f"未知的插件子命令: '{sub_cmd}'。可用选项: list, install <id>, remove <id>, search <q>, create <name>",
        }.get(active_language, f"Unknown plugins subcommand: '{sub_cmd}'. Options: list, install <id>, remove <id>, search <q>, create <name>")
        print(f"{C_YELLOW}{msg}{C_RESET}")

def _load_webui_module():
    p_dir = plugin_manager.get_plugins_dir() if plugin_manager else config.REPO_ROOT / "plugins"
    server_script = p_dir / "webui" / "server.py"
    if not server_script.exists():
        server_script = config.REPO_ROOT / "plugins" / "webui" / "server.py"
    if not server_script.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("lensetek_webui_server", str(server_script))
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return None

def start_webui_cli(workspace_path: Path, port: int, model_name: str | None = None, no_server: bool = False, active_language: str = "en"):
    """Menjalankan Lensetek Agent Web Workspace (Antigravity/Codex style) & membuka browser."""
    installed = plugin_manager.list_installed_plugin_ids() if plugin_manager else []
    if "webui" not in installed and plugin_manager:
        print(f"{C_YELLOW}[i] Mengaktifkan plugin 'webui'...{C_RESET}")
        plugin_manager.install_plugin("webui", lang=active_language)

    server_mgr = None
    started_by_us = False
    actual_model = model_name or config.pick_default_model()

    if not actual_model and not no_server:
        print(f"\n{C_YELLOW}{t('no_model_detected', active_language)}{C_RESET}")
        ok, msg, path_res = config.download_model_from_catalog(lang=active_language)
        if ok and path_res:
            actual_model = path_res
        else:
            print(f"{C_RED}{t('download_failed', active_language)} {msg}{C_RESET}")
            sys.exit(1)

    if not no_server and actual_model:
        server_mgr = LlamaServerManager(port=port)
        if not server_mgr.is_healthy():
            print(f"{C_DIM}Memulai runtime llama-server untuk model '{Path(actual_model).name}' pada port {port}...{C_RESET}")
            try:
                server_mgr.start(actual_model)
                started_by_us = True
                print(f"{C_GREEN}✓ llama-server aktif di http://127.0.0.1:{port}{C_RESET}")
            except Exception as e:
                print(f"{C_YELLOW}[!] Catatan llama-server: {e}. Web Workspace tetap dijalankan.{C_RESET}")

    mod = _load_webui_module()
    if not mod or not hasattr(mod, "start_webui_server"):
        print(f"{C_RED}[ERROR] Plugin WebUI server.py tidak ditemukan.{C_RESET}")
        sys.exit(1)

    web_port = 3001
    httpd = mod.start_webui_server(
        workspace=workspace_path,
        llama_port=port,
        web_port=web_port,
        model_name=actual_model,
        server_mgr=server_mgr,
    )
    actual_web_port = getattr(httpd, "server_port", web_port)

    webui_url = f"http://127.0.0.1:{actual_web_port}"
    import webbrowser
    webbrowser.open(webui_url)

    model_disp = Path(actual_model).name if actual_model else "external/running"
    print(f"\n{C_GREEN}{'='*64}{C_RESET}")
    print(f"  {C_BOLD}🌐 Lensetek Agent Web Workspace Active{C_RESET}")
    print(f"  • Web URL:    {C_CYAN}{webui_url}{C_RESET}")
    print(f"  • Workspace:  {workspace_path}")
    print(f"  • Model:      {model_disp}")
    print(f"  • Engine:     http://127.0.0.1:{port}")
    print(f"  {C_DIM}Tekan Ctrl+C untuk menghentikan server.{C_RESET}")
    print(f"{C_GREEN}{'='*64}{C_RESET}\n")

    try:
        import signal
        import time

        def _sig_stop(_signum, _frame):
            raise KeyboardInterrupt()

        signal.signal(signal.SIGTERM, _sig_stop)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _sig_stop)

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Menghentikan Lensetek Web Workspace...{C_RESET}")
    finally:
        if started_by_us and server_mgr:
            server_mgr.stop()
        print(f"{C_GREEN}Web Workspace dihentikan.{C_RESET}")

def main():
    parser = argparse.ArgumentParser(
        description="LENSETEK LEAN AGENT HARNESS - Autonomous Local AI Agent Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples / Contoh Penggunaan:
  lensetek                                        Mulai sesi interaktif (REPL)
  lensetek --prompt "Analisis file README.md"     Jalankan satu tugas langsung & keluar
  lensetek "Jelaskan fungsi skrip ini"            Prompt langsung tanpa flag
  lensetek --prompt "Ringkas kode" --model qwen   Jalankan prompt dengan model tertentu
  lensetek --update                               Periksa & instal pembaruan aplikasi
  lensetek --gui                                  Jalankan server WebUI dan buka di browser
  lensetek --plugins list                         Daftar semua plugin & statusnya
  lensetek --plugins install webui                Instal plugin WebUI
  lensetek --plugins remove webui                 Hapus plugin WebUI
  lensetek --version                              Tampilkan versi aktif & What's New
        """
    )
    parser.add_argument("direct_prompt", nargs="*", default=[], help="Teks prompt langsung tanpa flag (opsional)")
    parser.add_argument("--prompt", "-P", dest="prompt", type=str, default=None, help="Jalankan prompt/tugas langsung (headless) lalu keluar")
    parser.add_argument("--once", type=str, default=None, help="Alias untuk --prompt (backward compatibility)")
    parser.add_argument("--model", "-m", default=None, help="Nama atau path model GGUF (default: auto pick)")
    parser.add_argument("--update", "-u", action="store_true", help="Periksa dan terapkan pembaruan aplikasi langsung dari CLI")
    parser.add_argument("--plugins", nargs="*", default=None, help="Kelola plugin: list, install <id>, remove <id>, search <q>, create <name>")
    parser.add_argument("--gui", "--webui", action="store_true", help="Jalankan server WebUI dan buka di browser")
    parser.add_argument("--uninstall", action="store_true", help="Hentikan server dan hapus instalasi ~/.lensetek-agent dengan aman")
    parser.add_argument("--version", "-v", action="store_true", help="Tampilkan versi saat ini dan catatan rilis (What's New)")
    parser.add_argument("--workspace", "-w", default=".", help="Folder kerja awal (default: '.')")
    parser.add_argument("--ctx", "-c", type=int, default=config.DEFAULT_CTX, help="Ukuran context window (default: 8192)")
    parser.add_argument("--port", "-p", type=int, default=config.DEFAULT_PORT, help="Port llama-server (default: 8081)")
    parser.add_argument("--no-server", action="store_true", help="Jangan otomatis jalankan llama-server internal")
    parser.add_argument("--auto-approve", action="store_true", help="Mode auto-approve aksi di dalam workspace")
    parser.add_argument("--yolo", action="store_true", help="Mode tanpa konfirmasi (kecuali fatal command)")
    args = parser.parse_args()

    # Baca preferensi bahasa pengguna terlebih dahulu (default: en)
    active_language = config.get_active_language()
    active_effort = config.get_active_effort()
    workspace_path = Path(args.workspace).resolve()

    # --- CLI ACTION 1: --version ---
    if args.version:
        cur_v = version.get_current_version() if version else "0.3.0"
        print(f"\n{C_BOLD}LENSETEK LEAN AGENT HARNESS{C_RESET} {C_CYAN}v{cur_v}{C_RESET}")
        if version:
            wn = version.get_whats_new(cur_v)
            if wn:
                wn_title = t("update_whats_new_title", active_language, ver=cur_v)
                print(f"\n{C_BOLD}{wn_title}{C_RESET}")
                for item in wn:
                    print(f"  • {item}")
        print()
        sys.exit(0)

    # --- CLI ACTION 2: --update ---
    if args.update:
        handle_update_cli(active_language)
        sys.exit(0)

    # --- CLI ACTION 2b: --uninstall ---
    if args.uninstall:
        handle_uninstall_cli()
        sys.exit(0)

    # --- CLI ACTION 3: --plugins ---
    if args.plugins is not None:
        handle_plugins_cli(args.plugins, active_language)
        sys.exit(0)

    # --- CLI ACTION 4: --gui / --webui ---
    if args.gui:
        start_webui_cli(workspace_path, args.port, model_name=args.model, no_server=args.no_server, active_language=active_language)
        sys.exit(0)

    # Tentukan apakah ada target prompt langsung (headless execution)
    target_prompt = args.prompt or args.once
    if not target_prompt and args.direct_prompt:
        target_prompt = " ".join(args.direct_prompt).strip()
    model_name = args.model or config.pick_default_model()
    if not model_name:
        print(f"\n{C_YELLOW}{t('no_model_detected', active_language)}{C_RESET}")
        print(f"{C_CYAN}{t('auto_downloading_default', active_language)}{C_RESET}")
        ok, msg, path_res = config.download_model_from_catalog(lang=active_language)
        if ok and path_res:
            model_name = path_res
            print(f"{C_GREEN}{t('download_complete', active_language)} {Path(model_name).name}{C_RESET}\n")
        else:
            print(f"{C_RED}{t('download_failed', active_language)} {msg}{C_RESET}")
            print(f"{C_DIM}{t('download_manual_hint', active_language)}{C_RESET}\n")
            sys.exit(1)

    if args.yolo:
        safety_mode = "yolo"
    elif args.auto_approve:
        safety_mode = "auto-approve"
    else:
        safety_mode = "strict"

    server_mgr = None
    started_by_us = False
    if not args.no_server:
        server_mgr = LlamaServerManager(port=args.port, ctx_size=args.ctx)
        if server_mgr.is_healthy():
            started_by_us = False
        else:
            if not target_prompt:
                print(f"{C_DIM}Starting llama-server for model '{model_name}' on port {args.port}...{C_RESET}")
            try:
                server_mgr.start(model_name)
                started_by_us = True
                if not target_prompt:
                    print(f"{C_GREEN}✓ llama-server active at http://127.0.0.1:{args.port} (ctx: {args.ctx}){C_RESET}\n")
            except Exception as e:
                print(f"{C_RED}[ERROR] Failed to start llama-server: {e}{C_RESET}")
                sys.exit(1)

    fs_tools = LocalWorkspaceTools(workspace_root=str(workspace_path), safety_mode=safety_mode)
    mcp_config = config.load_mcp_config()
    mcp_mgr = MCPManager(config_dict=mcp_config, safety_mode=safety_mode)
    skills_mgr = SkillManager(local_skills_dir=config.CLI_DIR / "skills", workspace_root=workspace_path, safety_mode=safety_mode)
    scheduler = TaskScheduler()
    session_mgr = SessionManager()
    active_session_data = session_mgr.get_active_session()

    plugin_ctx = {"workspace": str(workspace_path), "lang": active_language, "config": config}
    installed_plugin_tools = plugin_manager.load_installed_tools(plugin_ctx) if plugin_manager else []

    agent = LeanAgent(
        base_url=f"http://127.0.0.1:{args.port}",
        fs_tools=fs_tools,
        mcp_manager=mcp_mgr,
        skills_manager=skills_mgr,
        session_manager=session_mgr,
        ctx_size=args.ctx,
        model_name=model_name,
        language=active_language,
        effort_level=active_effort,
        plugin_tools=installed_plugin_tools
    )
    if active_session_data:
        agent.load_session(active_session_data)

    def on_status(msg):
        if not target_prompt:
            print(f"{C_DIM}⏳ {msg}{C_RESET}")

    def on_tool(t_name, t_args, t_result):
        if target_prompt:
            return
        if t_result is None:
            args_summary = str(t_args)[:80]
            print(f"{C_MAGENTA}⚙️  [TOOL CALL] {t_name}({args_summary}){C_RESET}")
        else:
            res_lines = t_result.strip().splitlines()
            first_line = res_lines[0][:100] if res_lines else "OK"
            print(f"{C_DIM}   └─ Result: {first_line}{C_RESET}")

    # --- JIKA RUN DALAM MODE HEADLESS (Direct Prompt / --prompt / --once) ---
    if target_prompt:
        try:
            res = agent.run_turn(target_prompt, on_status=None, on_tool=None)
            print(res)
        finally:
            mcp_mgr.close_all()
            if started_by_us and server_mgr:
                server_mgr.stop()
        sys.exit(0)

    # Inisialisasi PromptSession untuk live autocomplete dengan tombol Tab auto-complete & dismiss
    prompt_session = None
    if HAS_PROMPT_TOOLKIT:
        try:
            pt_style = Style.from_dict({
                'prompt': '#00ff88 bold',
                'completion-menu.completion': 'bg:#1e2430 #d0d7de',
                'completion-menu.completion.current': 'bg:#00ffff #000000 bold',
                'completion-menu.meta': 'bg:#2a324b #e0af68',
                'completion-menu.multi-column-meta': 'bg:#2a324b #e0af68',
                'scrollbar.background': 'bg:#1e2430',
                'scrollbar.button': 'bg:#00ffff',
            })
            completer = SlashCommandCompleter(
                lambda: get_slash_items(skills_mgr, active_language),
                lambda: active_language,
                lambda: fs_tools.list_mentionable_files(),
            )

            kb = KeyBindings()

            @kb.add('tab')
            def _on_tab(event):
                b = event.current_buffer
                if b.complete_state:
                    comp = b.complete_state.current_completion
                    if not comp and b.complete_state.completions:
                        comp = b.complete_state.completions[0]
                    if comp:
                        b.apply_completion(comp)
                    b.cancel_completion()
                else:
                    if b.text.startswith('/') or '@' in b.document.current_line_before_cursor:
                        b.start_completion(select_first=True)
                    else:
                        b.insert_text('    ')

            prompt_session = PromptSession(
                completer=completer,
                complete_while_typing=True,
                complete_style=CompleteStyle.COLUMN,
                reserve_space_for_menu=8,
                key_bindings=kb,
                style=pt_style
            )
        except Exception:
            prompt_session = None

    # Cek update secara non-blocking di latar belakang saat startup
    startup_update_info = None
    if version:
        def _bg_check_update():
            nonlocal startup_update_info
            try:
                startup_update_info = version.check_for_updates(timeout_sec=2.5)
            except Exception:
                pass

        up_thread = threading.Thread(target=_bg_check_update, daemon=True)
        up_thread.start()
        up_thread.join(timeout=0.9)  # beri jeda hingga 0.9s untuk fetch cepat

    # --- INTERACTIVE CLI UI ---
    all_skills = skills_mgr.scan_skills()
    curr_sess_info = session_mgr.get_active_session()
    print_banner(workspace_path, model_name, args.ctx, args.port, mcp_mgr.get_server_names(), safety_mode, len(all_skills), active_language, active_effort, startup_update_info, session_name=curr_sess_info.get("name", "Default Session"))

    try:
        while True:
            cur_sess = session_mgr.get_active_session()
            sess_name_disp = cur_sess.get("name", "Default")[:20]
            user_turns = len([m for m in cur_sess.get("messages", []) if m.get("role") == "user"])
            total_tok = agent.last_usage.get("total_tokens", 0)
            pct = (total_tok / args.ctx) * 100.0 if args.ctx else 0.0
            print(f"{C_DIM}~ [{workspace_path.name}] [Sess: {sess_name_disp} ({user_turns} msgs)] {pct:.1f}%/{args.ctx // 1024}k tok [{safety_mode.upper()}|{active_language.upper()}|EFFORT:{active_effort.upper()}] ({model_name}){C_RESET}")

            try:
                if prompt_session:
                    try:
                        user_input = prompt_session.prompt(ANSI(f"{C_BOLD}{C_GREEN}> {C_RESET}")).strip()
                    except KeyboardInterrupt:
                        print(f"{C_DIM}\n(Type /exit to quit){C_RESET}\n")
                        continue
                    except Exception:
                        user_input = input(f"{C_BOLD}{C_GREEN}> {C_RESET}").strip()
                else:
                    try:
                        user_input = input(f"{C_BOLD}{C_GREEN}> {C_RESET}").strip()
                    except KeyboardInterrupt:
                        print(f"{C_DIM}\n(Type /exit to quit){C_RESET}\n")
                        continue
            except EOFError:
                break

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                cmd_parts = user_input.split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

                if cmd in ("/exit", "/quit"):
                    break
                elif cmd == "/help":
                    print_help(active_language)
                    continue
                elif cmd == "/clear":
                    agent.reset_session()
                    print(f"{C_CYAN}{t('chat_cleared', active_language)}{C_RESET}\n")
                    continue

                # --- SESSION COMMAND (MENAMPILKAN HISTORY LANGSUNG) ---
                elif cmd == "/session":
                    sub_parts = arg.split(maxsplit=1) if arg else []
                    s_action = sub_parts[0].lower() if sub_parts else ""
                    s_param = sub_parts[1].strip() if len(sub_parts) > 1 else ""

                    if s_action in ("new", "create"):
                        new_s = session_mgr.create_session(s_param or "", model_name=model_name or "")
                        agent.load_session(new_s)
                        print(f"{C_GREEN}✓ {t('session_created', active_language)} '{new_s['name']}' ({new_s['id']}){C_RESET}\n")
                        continue

                    if s_action in ("switch", "use"):
                        if not s_param:
                            print(f"{C_YELLOW}Usage: /session switch <id|number>{C_RESET}\n")
                        else:
                            ok, msg, s_data = session_mgr.switch_session(s_param)
                            if ok and s_data:
                                agent.load_session(s_data)
                                print(f"{C_GREEN}✓ {t('session_switched', active_language)} '{s_data['name']}' ({s_data['id']}){C_RESET}\n")
                                print(f"{session_mgr.format_session_history(s_data['id'], lang=active_language)}\n")
                            else:
                                print(f"{C_RED}{msg}{C_RESET}\n")
                        continue

                    if s_action in ("rename", "mv"):
                        target_id = None
                        new_name = ""
                        if not s_param:
                            act_session = session_mgr.get_active_session()
                            cur_name = act_session.get("name", "Session")
                            print(f"{C_CYAN}Mengubah nama sesi aktif: {C_BOLD}{cur_name}{C_RESET}")
                            new_name = input("Masukkan nama sesi baru (Enter new name): ").strip()
                        else:
                            parts = s_param.split(maxsplit=1)
                            all_s = session_mgr.list_sessions()
                            if parts[0].isdigit() and int(parts[0]) <= len(all_s) and len(parts) > 1:
                                target_id = parts[0]
                                new_name = parts[1].strip()
                            elif any(s["id"] == parts[0] for s in all_s) and len(parts) > 1:
                                target_id = parts[0]
                                new_name = parts[1].strip()
                            else:
                                target_id = None
                                new_name = s_param.strip()

                        if not new_name:
                            print(f"{C_YELLOW}Perubahan nama dibatalkan (nama kosong).{C_RESET}\n")
                        else:
                            ok, msg = session_mgr.rename_session(target_id, new_name)
                            if ok:
                                cur_s = session_mgr.get_active_session()
                                agent.load_session(cur_s)
                                print(f"{C_GREEN}✓ {msg}{C_RESET}\n")
                            else:
                                print(f"{C_RED}{msg}{C_RESET}\n")
                        continue

                    if s_action in ("delete", "rm", "remove"):
                        if not s_param:
                            print(f"{C_YELLOW}Usage: /session delete <id|number>{C_RESET}\n")
                        else:
                            ok, msg = session_mgr.delete_session(s_param)
                            if ok:
                                cur_s = session_mgr.get_active_session()
                                agent.load_session(cur_s)
                                print(f"{C_GREEN}✓ {msg}{C_RESET}\n")
                            else:
                                print(f"{C_RED}{msg}{C_RESET}\n")
                        continue

                    # Menampilkan riwayat percakapan sesi aktif secara langsung
                    act_id = session_mgr.get_active_session_id()
                    print(f"\n{session_mgr.format_session_history(act_id, lang=active_language)}\n")

                    # Menampilkan daftar session dan menu aksi interaktif
                    all_sessions = session_mgr.list_sessions()
                    sess_title = t("session_title", active_language)
                    print(f"{C_BOLD}{sess_title}{C_RESET}")
                    for idx, s in enumerate(all_sessions, start=1):
                        is_active = (s["id"] == act_id)
                        marker = f" {C_GREEN}* {t('session_active_marker', active_language)}{C_RESET}" if is_active else ""
                        up_time = s.get("updated_at", "")[:16].replace("T", " ")
                        print(f"  [{idx}] {C_BOLD}{s['name']}{C_RESET} {C_DIM}(ID: {s['id']} | {s['total_messages']} msgs | {up_time}){C_RESET}{marker}")

                    print(f"\n{C_BOLD}Session Actions / Pilihan Aksi Sesi:{C_RESET}")
                    print(f"  [{C_CYAN}1-{len(all_sessions)}{C_RESET}] {t('session_sub_switch', active_language)}")
                    print(f"  [{C_CYAN}n{C_RESET}] {t('session_sub_new', active_language)} (/session new [nama])")
                    print(f"  [{C_CYAN}r{C_RESET}] {t('session_sub_rename', active_language)} (/session rename <nama>)")
                    print(f"  [{C_CYAN}d{C_RESET}] {t('session_sub_delete', active_language)} (/session delete <id>)")

                    prompt_str = t("session_prompt", active_language, count=len(all_sessions))
                    choice = input(f"\n{prompt_str}").strip()
                    if not choice:
                        continue

                    if choice.lower() in ("n", "new"):
                        name_in = input("Enter new session name (or press enter for default): ").strip()
                        new_s = session_mgr.create_session(name_in, model_name=model_name or "")
                        agent.load_session(new_s)
                        print(f"{C_GREEN}✓ {t('session_created', active_language)} '{new_s['name']}' ({new_s['id']}){C_RESET}\n")
                    elif choice.lower().startswith("r ") or choice.lower() == "r":
                        r_param = choice[2:].strip() if choice.lower().startswith("r ") else ""
                        target_id = None
                        new_name = ""
                        if not r_param:
                            act_session = session_mgr.get_active_session()
                            cur_name = act_session.get("name", "Session")
                            print(f"{C_CYAN}Mengubah nama sesi aktif: {C_BOLD}{cur_name}{C_RESET}")
                            new_name = input("Masukkan nama sesi baru (Enter new name): ").strip()
                        else:
                            parts = r_param.split(maxsplit=1)
                            if parts[0].isdigit() and int(parts[0]) <= len(all_sessions) and len(parts) > 1:
                                target_id = parts[0]
                                new_name = parts[1].strip()
                            else:
                                target_id = None
                                new_name = r_param.strip()

                        if new_name:
                            ok, msg = session_mgr.rename_session(target_id, new_name)
                            if ok:
                                cur_s = session_mgr.get_active_session()
                                agent.load_session(cur_s)
                                print(f"{C_GREEN}✓ {msg}{C_RESET}\n")
                            else:
                                print(f"{C_RED}{msg}{C_RESET}\n")
                    elif choice.lower().startswith("d ") or choice.lower() == "d":
                        d_target = choice[2:].strip() if choice.lower().startswith("d ") else input("Enter session number or ID to delete: ").strip()
                        if d_target:
                            ok, msg = session_mgr.delete_session(d_target)
                            if ok:
                                cur_s = session_mgr.get_active_session()
                                agent.load_session(cur_s)
                            print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}\n")
                    elif choice.isdigit():
                        ok, msg, s_data = session_mgr.switch_session(choice)
                        if ok and s_data:
                            agent.load_session(s_data)
                            print(f"{C_GREEN}✓ {t('session_switched', active_language)} '{s_data['name']}' ({s_data['id']}){C_RESET}\n")
                            print(f"{session_mgr.format_session_history(s_data['id'], lang=active_language)}\n")
                        else:
                            print(f"{C_RED}{msg}{C_RESET}\n")
                    continue

                # --- UPDATE COMMAND ---
                elif cmd == "/update":
                    handle_update_cli(active_language, started_by_us=started_by_us, server_mgr=server_mgr, mcp_mgr=mcp_mgr)
                    continue

                # --- LANGUAGE COMMAND ---
                elif cmd == "/language":
                    if not arg:
                        cur_name = config.SUPPORTED_LANGUAGES.get(active_language, active_language)
                        print(f"\n{C_BOLD}{t('lang_active', active_language)}{C_RESET} {cur_name} ({active_language})")
                        print(f"{t('lang_supported', active_language)} {', '.join(f'/language {k} ({v})' for k, v in config.SUPPORTED_LANGUAGES.items())}")
                        print(f"{C_DIM}{t('lang_saved_hint', active_language)}{C_RESET}\n")
                    else:
                        ok, msg = config.set_active_language(arg)
                        if ok:
                            active_language = config.get_active_language()
                            agent.set_language(active_language)
                            print(f"{C_GREEN}✓ {msg}{C_RESET}\n")
                        else:
                            print(f"{C_RED}{msg}{C_RESET}\n")
                    continue

                # --- EFFORT (REASONING / THINKING DEPTH) COMMAND ---
                elif cmd == "/effort":
                    if not arg:
                        has_thinking, reason_str = config.check_model_thinking_support(model_name)
                        eff_title = t("effort_title", active_language)
                        print(f"\n{C_BOLD}{eff_title}{C_RESET}")
                        print(f"  • {C_BOLD}{t('effort_active_model', active_language)}{C_RESET} {model_name or 'None'}")
                        support_badge = f"{C_GREEN}YES ({reason_str}){C_RESET}" if has_thinking else f"{C_YELLOW}NO ({reason_str}){C_RESET}"
                        print(f"  • {C_BOLD}{t('effort_support_status', active_language)}{C_RESET} {support_badge}")
                        curr_eff = config.get_active_effort()
                        print(f"  • {C_BOLD}{t('effort_current_level', active_language)}{C_RESET} {C_CYAN}[{curr_eff.upper()}]{C_RESET}")
                        print(f"\n{C_BOLD}{t('effort_options_title', active_language)}{C_RESET}")
                        levels_list = list(config.SUPPORTED_EFFORT_LEVELS.keys())
                        for idx, (lvl, desc) in enumerate(config.SUPPORTED_EFFORT_LEVELS.items(), start=1):
                            marker = f" {C_GREEN}* active{C_RESET}" if lvl == curr_eff else ""
                            print(f"  [{C_CYAN}{idx}{C_RESET}] {C_BOLD}{lvl:<8}{C_RESET}: {desc}{marker}")

                        if active_language == "id":
                            eff_prompt = f"\nPilih nomor (1-{len(levels_list)}) atau nama (off|low|medium|high), atau enter untuk batal: "
                        elif active_language == "cn":
                            eff_prompt = f"\n选择序号 (1-{len(levels_list)}) 或输入强度 (off|low|medium|high), 或按回车取消: "
                        else:
                            eff_prompt = f"\nSelect number (1-{len(levels_list)}) or level name (off|low|medium|high), or press enter to cancel: "

                        user_choice = input(eff_prompt).strip().lower()
                        if user_choice:
                            ok, msg = config.set_active_effort(user_choice)
                            if ok:
                                active_effort = config.get_active_effort()
                                agent.set_effort(active_effort)
                                print(f"{C_GREEN}{t('effort_updated', active_language)} {active_effort.upper()}{C_RESET}\n")
                            else:
                                print(f"{C_RED}{msg}{C_RESET}\n")
                        else:
                            print(f"{C_DIM}{t('effort_tip', active_language)}{C_RESET}\n")
                    else:
                        lvl_arg = arg.strip().lower()
                        ok, msg = config.set_active_effort(lvl_arg)
                        if ok:
                            active_effort = config.get_active_effort()
                            agent.set_effort(active_effort)
                            print(f"{C_GREEN}{t('effort_updated', active_language)} {active_effort.upper()}{C_RESET}\n")
                        else:
                            print(f"{C_RED}{msg}{C_RESET}\n")
                    continue

                # --- WEB SEARCH COMMAND ---
                elif cmd == "/search":
                    if not arg:
                        print(f"{C_YELLOW}{t('search_usage', active_language)}{C_RESET}\n")
                    else:
                        print(f"{C_DIM}{t('search_searching', active_language)}{C_RESET}")
                        s_results = headless_web_search(arg, num_results=5)
                        formatted = format_search_results(s_results, query=arg)
                        print(f"\n{formatted}\n")
                    continue

                elif cmd == "/strict":
                    safety_mode = "strict"
                    fs_tools.set_safety_mode("strict")
                    mcp_mgr.set_safety_mode("strict")
                    skills_mgr.set_safety_mode("strict")
                    print(f"{C_GREEN}{t('safety_strict_set', active_language)}{C_RESET}\n")
                    continue
                elif cmd == "/auto-approve":
                    safety_mode = "auto-approve"
                    fs_tools.set_safety_mode("auto-approve")
                    mcp_mgr.set_safety_mode("auto-approve")
                    skills_mgr.set_safety_mode("auto-approve")
                    print(f"{C_GREEN}{t('safety_auto_set', active_language)}{C_RESET}\n")
                    continue
                elif cmd == "/yolo":
                    safety_mode = "yolo"
                    fs_tools.set_safety_mode("yolo")
                    mcp_mgr.set_safety_mode("yolo")
                    skills_mgr.set_safety_mode("yolo")
                    print(f"{C_YELLOW}{t('safety_yolo_set', active_language)}{C_RESET}\n")
                    continue
                elif cmd == "/workspace":
                    if not arg:
                        print(f"{t('workspace_current', active_language)} {workspace_path}")
                    else:
                        new_p = Path(arg).resolve()
                        if new_p.exists() and new_p.is_dir():
                            workspace_path = new_p
                            fs_tools.set_workspace(str(workspace_path))
                            skills_mgr.workspace_root = workspace_path
                            print(f"{C_GREEN}{t('workspace_changed', active_language)} {workspace_path}{C_RESET}\n")
                        else:
                            print(f"{C_RED}{t('workspace_not_found', active_language)} {arg}{C_RESET}\n")
                    continue

                # --- SKILLS COMMANDS ---
                elif cmd == "/skills":
                    matched = skills_mgr.search_skills(arg)
                    print(f"\n{C_BOLD}Available Skills ({len(matched)}):{C_RESET}")
                    for s in matched[:30]:
                        src_badge = f"{C_CYAN}[{s['source']}]{C_RESET}"
                        print(f"  - {C_BOLD}/{s['slug']}{C_RESET} {src_badge}: {s['description'][:85]}")
                    if len(matched) > 30:
                        print(f"  {C_DIM}... and {len(matched) - 30} more skills. Use `/skills <keyword>` to filter.{C_RESET}")
                    print(f"{C_DIM}Invoke directly with: /<skill-name> <task instruction>{C_RESET}\n")
                    continue

                elif cmd == "/skill" and arg.startswith("create"):
                    body = arg[len("create"):].strip()
                    parts = [p.strip() for p in body.split("|")]
                    if len(parts) >= 2:
                        s_name = parts[0]
                        s_desc = parts[1]
                        s_inst = parts[2] if len(parts) > 2 else f"Instructions for skill {s_name}."
                        res = skills_mgr.create_skill(s_name, s_desc, s_inst)
                        print(f"{C_GREEN}{res}{C_RESET}\n")
                    else:
                        print(f"{C_YELLOW}Usage: /skill create <name> | <description> | <instructions>{C_RESET}\n")
                    continue

                # --- MCP COMMANDS ---
                elif cmd == "/mcp":
                    if not arg:
                        print(f"\n{C_BOLD}Registered MCP Servers:{C_RESET}")
                        for k, v in mcp_mgr.config.items():
                            status = f"{C_GREEN}ENABLED{C_RESET}" if v.get("enabled", True) else f"{C_DIM}DISABLED{C_RESET}"
                            print(f"  - {C_BOLD}{k}{C_RESET} [{status}]: {v.get('description', '')}")
                        print(f"\n{C_DIM}Popular presets: {list(config.MCP_PRESETS.keys())}{C_RESET}")
                        print(f"{C_DIM}Commands: /mcp install <name>, /mcp test <name>, /mcp enable <name>, /mcp disable <name>, /mcp remove <name>{C_RESET}\n")
                    else:
                        sub_parts = arg.split(maxsplit=2)
                        sub_cmd = sub_parts[0].lower()
                        s_target = sub_parts[1] if len(sub_parts) > 1 else ""
                        s_rest = sub_parts[2] if len(sub_parts) > 2 else ""

                        if sub_cmd == "install":
                            if not s_target:
                                print(f"{C_YELLOW}Usage: /mcp install <name|preset> [command args...]{C_RESET}\n")
                            else:
                                if s_rest:
                                    cmd_tokens = s_rest.split()
                                    res = mcp_mgr.install_server(s_target, command=cmd_tokens[0], args=cmd_tokens[1:])
                                else:
                                    res = mcp_mgr.install_server(s_target)
                                print(f"{C_CYAN}{res}{C_RESET}\n")
                        elif sub_cmd == "test":
                            print(mcp_mgr.test_server(s_target))
                        elif sub_cmd == "remove":
                            print(mcp_mgr.remove_server(s_target))
                        elif sub_cmd == "enable":
                            print(mcp_mgr.toggle_server(s_target, True))
                        elif sub_cmd == "disable":
                            print(mcp_mgr.toggle_server(s_target, False))
                        else:
                            print(f"{C_YELLOW}Unknown MCP sub-command: {sub_cmd}{C_RESET}\n")
                    continue

                # --- GOAL & LOOP & SCHEDULE ---
                elif cmd == "/goal":
                    if not arg:
                        print(f"{C_YELLOW}Usage: /goal <autonomous goal description>{C_RESET}\n")
                    else:
                        print(f"{C_CYAN}Starting autonomous /goal mode... (Press Ctrl+C to cancel){C_RESET}")
                        try:
                            res = agent.run_goal(arg, on_status=on_status, on_tool=on_tool)
                            print(f"\n{C_BOLD}{res}{C_RESET}\n")
                        except KeyboardInterrupt:
                            print(f"\n{C_YELLOW}⚠️  /goal mode cancelled by user.{C_RESET}\n")
                    continue

                elif cmd == "/loop":
                    loop_parts = arg.split(maxsplit=1)
                    if len(loop_parts) < 2:
                        print(f"{C_YELLOW}Usage: /loop <3x|30s|5m> <task to repeat>{C_RESET}\n")
                    else:
                        count_spec = loop_parts[0]
                        loop_task = loop_parts[1]
                        def on_iter(cur, total):
                            t_str = f"/{total}" if total else ""
                            print(f"\n{C_BOLD}{C_CYAN}--- [LOOP ITERATION {cur}{t_str}] ---{C_RESET}")
                        try:
                            res = agent.run_loop(count_spec, loop_task, on_status=on_status, on_tool=on_tool, on_iteration=on_iter)
                            print(f"\n{C_BOLD}{res}{C_RESET}\n")
                        except KeyboardInterrupt:
                            print(f"\n{C_YELLOW}⚠️  /loop mode stopped by user.{C_RESET}\n")
                    continue

                elif cmd == "/schedule":
                    sch_parts = arg.split(maxsplit=4)
                    sch_action = sch_parts[0].lower() if sch_parts else ""

                    if sch_action == "add" and len(sch_parts) >= 5:
                        sch_type = sch_parts[1].lower()
                        sch_name = sch_parts[2]
                        sch_spec = sch_parts[3]
                        sch_prompt = sch_parts[4]

                        if sch_type == "in-app":
                            res = scheduler.add_in_app(
                                sch_name, sch_spec, sch_prompt,
                                callback=lambda p: print(f"\n[SCHEDULE IN-APP: {sch_name}]\n{agent.run_turn(p)}")
                            )
                            print(f"{C_GREEN}{res}{C_RESET}\n")
                        elif sch_type == "os":
                            s_flag = "--auto-approve" if safety_mode == "auto-approve" else ("--yolo" if safety_mode == "yolo" else "")
                            res = scheduler.register_os_task(sch_name, sch_spec, sch_prompt, str(workspace_path), safety_flag=s_flag)
                            print(f"{C_GREEN}{res}{C_RESET}\n")
                        else:
                            print(f"{C_YELLOW}Schedule type must be 'in-app' or 'os'.{C_RESET}\n")

                    elif sch_action == "list":
                        print(f"\n{C_BOLD}In-App Schedules:{C_RESET}")
                        for item in scheduler.list_in_app():
                            print(f"  - {item['name']} ({item['spec']}): {item['prompt'][:60]}")
                        print(f"\n{C_BOLD}OS Schedules:{C_RESET}")
                        print(scheduler.list_os_tasks())
                        print()

                    elif sch_action == "remove" and len(sch_parts) >= 2:
                        rem_name = sch_parts[1]
                        if scheduler.remove_in_app(rem_name):
                            print(f"{C_GREEN}In-app task '{rem_name}' removed.{C_RESET}")
                        os_res = scheduler.remove_os_task(rem_name)
                        print(f"{C_GREEN}{os_res}{C_RESET}\n")
                    else:
                        print(f"{C_YELLOW}Usage: /schedule add <in-app|os> <name> <5m|1h|daily 08:00> <prompt>{C_RESET}")
                        print(f"{C_YELLOW}       /schedule list{C_RESET}")
                        print(f"{C_YELLOW}       /schedule remove <name>{C_RESET}\n")
                    continue

                # --- PLUGINS COMMAND ---
                elif cmd == "/plugins":
                    if not plugin_manager:
                        print(f"{C_RED}Plugin manager is not available.{C_RESET}\n")
                        continue

                    parts = arg.split(maxsplit=1)
                    p_action = parts[0].lower() if parts else ""
                    p_val = parts[1].strip() if len(parts) > 1 else ""

                    if p_action in ("install", "add", "i") and p_val:
                        ok, msg = plugin_manager.install_plugin(p_val, lang=active_language)
                        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}\n")
                        continue

                    if p_action in ("remove", "delete", "rm", "uninstall", "u") and p_val:
                        ok, msg = plugin_manager.uninstall_plugin(p_val, lang=active_language)
                        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}\n")
                        continue

                    if p_action in ("create", "new") and p_val:
                        ok, msg, path_res = plugin_manager.create_plugin_scaffold(p_val, lang=active_language)
                        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}\n")
                        continue

                    # Interactive / List mode with pagination and search
                    p_search = p_val if p_action in ("search", "find", "s") else ""
                    p_cat = p_val if p_action in ("list", "ls", "category", "c") and p_val not in ("", "all") else ""
                    cur_page = 1

                    while True:
                        items, total_count, total_pages = plugin_manager.get_paginated_plugins(
                            page=cur_page,
                            page_size=5,
                            category=p_cat,
                            search_query=p_search,
                            lang=active_language
                        )

                        p_title = t("plugin_title", active_language)
                        p_info = t("plugin_page_info", active_language, current=cur_page, total=total_pages, count=total_count)
                        print(f"\n{C_BOLD}{p_title} ({p_info}){C_RESET}")
                        if p_search:
                            print(f"{C_CYAN}Search filter: '{p_search}'{C_RESET}")
                        if p_cat:
                            print(f"{C_CYAN}Category filter: '[{p_cat}]'{C_RESET}")

                        print(f"  {'#':<3} {'Plugin Name':<28} {'Category':<10} {'Status':<12} {'Description'}")
                        print(f"  {'-'*3} {'-'*28} {'-'*10} {'-'*12} {'-'*35}")

                        if not items:
                            print(f"  {C_DIM}No plugins found matching criteria.{C_RESET}")
                        else:
                            for idx, itm in enumerate(items, start=1):
                                p_id = itm.get("id")
                                p_name = itm.get("name", p_id)
                                if len(p_name) > 27:
                                    p_name = p_name[:24] + "..."
                                p_cat_disp = f"[{itm.get('category', 'tools')}]"
                                is_inst = itm.get("is_installed", False)
                                stat_str = f"{C_GREEN}{t('plugin_status_installed', active_language)}{C_RESET}" if is_inst else f"{C_DIM}{t('plugin_status_available', active_language)}{C_RESET}"
                                desc_field = f"description_{active_language}"
                                p_desc = itm.get(desc_field, itm.get("description", ""))
                                if len(p_desc) > 38:
                                    p_desc = p_desc[:35] + "..."
                                print(f"  [{idx}] {C_BOLD}{p_name:<26}{C_RESET} {p_cat_disp:<10} {stat_str:<20} {p_desc}")

                        p_hint = t("plugin_commands_hint", active_language, max=len(items))
                        print(f"\n{C_DIM}{p_hint}{C_RESET}")
                        try:
                            choice = input(f"{C_CYAN}>{C_RESET} ").strip()
                        except (KeyboardInterrupt, EOFError):
                            print()
                            break

                        if not choice or choice.lower() in ("q", "quit", "exit"):
                            print()
                            break
                        elif choice.lower() == "n":
                            if cur_page < total_pages:
                                cur_page += 1
                            else:
                                print(f"{C_YELLOW}Already on the last page.{C_RESET}")
                        elif choice.lower() == "p":
                            if cur_page > 1:
                                cur_page -= 1
                            else:
                                print(f"{C_YELLOW}Already on the first page.{C_RESET}")
                        elif choice.lower().startswith("s ") or choice.lower() == "s":
                            if choice.lower().startswith("s "):
                                p_search = choice[2:].strip()
                            else:
                                p_search = input("Enter keyword to search (or empty to clear): ").strip()
                            cur_page = 1
                        elif choice.isdigit() and 1 <= int(choice) <= len(items):
                            selected_itm = items[int(choice) - 1]
                            sel_name = selected_itm.get("name", selected_itm.get("id"))
                            sel_id = selected_itm.get("id")

                            act_prompt = t("plugin_action_prompt", active_language, name=sel_name)
                            p_act = input(act_prompt).strip().lower()
                            if p_act in ("i", "install"):
                                ok, msg = plugin_manager.install_plugin(sel_id, lang=active_language)
                                print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")
                            elif p_act in ("u", "uninstall", "r", "remove"):
                                ok, msg = plugin_manager.uninstall_plugin(sel_id, lang=active_language)
                                print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}")
                        else:
                            print(f"{C_YELLOW}Invalid choice: '{choice}'. Enter 1-{len(items)}, n, p, s, or q.{C_RESET}")
                    continue

                # --- WEBUI LAUNCHER COMMAND ---
                elif cmd in ("/gui", "/webui"):
                    installed = plugin_manager.list_installed_plugin_ids() if plugin_manager else []
                    if "webui" not in installed and plugin_manager:
                        print(f"{C_YELLOW}[i] Mengaktifkan plugin 'webui'...{C_RESET}")
                        plugin_manager.install_plugin("webui", lang=active_language)

                    mod = _load_webui_module()
                    if not mod or not hasattr(mod, "start_webui_server"):
                        print(f"{C_RED}[ERROR] Plugin WebUI server.py tidak ditemukan.{C_RESET}\n")
                        continue

                    web_port = 3001
                    httpd = mod.start_webui_server(
                        workspace=workspace_path,
                        llama_port=args.port,
                        web_port=web_port,
                        model_name=model_name,
                        server_mgr=server_mgr,
                        agent=agent,
                    )
                    actual_web_port = getattr(httpd, "server_port", web_port)

                    webui_url = f"http://127.0.0.1:{actual_web_port}"
                    import webbrowser
                    try:
                        webbrowser.open(webui_url)
                    except Exception:
                        pass
                    print(f"\n{C_GREEN}✓ Lensetek Agent Web Workspace: {C_CYAN}{webui_url}{C_RESET}")
                    print(f"{C_DIM}  (Workspace: {workspace_path} • Model: {model_name} • Port: {actual_web_port}){C_RESET}\n")
                    continue

                # --- MODEL & CTX COMMANDS ---
                elif cmd == "/model":
                    arg_parts = arg.split(maxsplit=1)
                    sub_cmd = arg_parts[0].lower() if arg_parts else ""
                    sub_val = arg_parts[1].strip() if len(arg_parts) > 1 else ""

                    if sub_cmd == "add" and sub_val:
                        ok, msg, p_res = config.add_custom_model_path(sub_val, lang=active_language)
                        if ok:
                            print(f"{C_GREEN}{msg}{C_RESET}\n")
                            if p_res and p_res.is_file():
                                ask_sw = input(t("model_switch_ask", active_language)).strip().lower()
                                if ask_sw in ("", "y", "yes") and server_mgr:
                                    server_mgr.start(str(p_res))
                                    model_name = p_res.name
                                    agent.model_name = p_res.name
                                    agent.reset_session()
                                    print(f"{C_GREEN}{t('model_switch_success', active_language)} {model_name}{C_RESET}\n")
                        else:
                            print(f"{C_RED}{msg}{C_RESET}\n")
                        continue

                    def do_model_delete(target_str: str = ""):
                        nonlocal model_name
                        available_models = config.list_gguf_models()
                        if not available_models:
                            print(f"{C_YELLOW}{t('model_remove_none_left', active_language)}{C_RESET}\n")
                            return

                        target_to_del = target_str.strip()
                        if not target_to_del:
                            loc_title = t("local_models_title", active_language)
                            print(f"\n{C_BOLD}{loc_title}{C_RESET}")
                            for idx, m in enumerate(available_models, start=1):
                                p = Path(m)
                                m_disp = p.name
                                size_str = ""
                                try:
                                    f_path = p if p.is_absolute() else (config.REPO_ROOT / m)
                                    if f_path.exists():
                                        sz_gb = f_path.stat().st_size / (1024 ** 3)
                                        size_str = f"({sz_gb:.2f} GB)"
                                except Exception:
                                    pass
                                marker = f"{C_GREEN}* active{C_RESET}" if m == model_name or p.name == model_name else ""
                                print(f"  [{idx}] {m_disp} {C_DIM}{size_str}{C_RESET} {marker}")

                            del_prompt = t("model_remove_select", active_language, count=len(available_models))
                            choice_del = input(f"\n{del_prompt}").strip()
                            if not choice_del:
                                print(f"{C_DIM}{t('model_remove_cancelled', active_language)}{C_RESET}\n")
                                return
                            if choice_del.isdigit() and 1 <= int(choice_del) <= len(available_models):
                                target_to_del = available_models[int(choice_del) - 1]
                            else:
                                target_to_del = choice_del

                        resolved = config.resolve_model_file(target_to_del)
                        if not resolved or not resolved.exists():
                            if target_to_del.isdigit() and 1 <= int(target_to_del) <= len(available_models):
                                target_to_del = available_models[int(target_to_del) - 1]
                                resolved = config.resolve_model_file(target_to_del)

                        if not resolved or not resolved.exists():
                            print(f"{C_RED}{t('model_remove_not_found', active_language, name=target_to_del)}{C_RESET}\n")
                            return

                        del_name = resolved.name
                        del_size = ""
                        try:
                            sz_gb = resolved.stat().st_size / (1024 ** 3)
                            del_size = f"{sz_gb:.2f} GB"
                        except Exception:
                            pass

                        is_active = (del_name == model_name or (Path(model_name).name == del_name))
                        if is_active:
                            warn_msg = t("model_remove_active_warn", active_language, name=del_name)
                            confirm = input(f"{C_YELLOW}{warn_msg}{C_RESET}").strip().lower()
                        else:
                            conf_msg = t("model_remove_confirm", active_language, name=del_name, size=del_size)
                            confirm = input(f"{conf_msg}").strip().lower()

                        if confirm not in ("y", "yes"):
                            print(f"{C_DIM}{t('model_remove_cancelled', active_language)}{C_RESET}\n")
                            return

                        if is_active and server_mgr:
                            print(f"Stopping server for model '{del_name}'...")
                            server_mgr.stop()

                        ok, msg, _ = config.delete_model(str(resolved))
                        if ok:
                            print(f"{C_GREEN}{t('model_remove_success', active_language, name=del_name)}{C_RESET}\n")
                            if is_active:
                                remaining = config.list_gguf_models()
                                if remaining:
                                    next_model = config.pick_default_model() or remaining[0]
                                    next_name = Path(next_model).name
                                    print(f"Switching to available model: {next_name}...")
                                    if server_mgr:
                                        server_mgr.start(next_model)
                                    model_name = next_name
                                    agent.model_name = next_name
                                    agent.reset_session()
                                    print(f"{C_GREEN}{t('model_switch_success', active_language)} {model_name}{C_RESET}\n")
                                else:
                                    model_name = ""
                                    agent.model_name = ""
                                    print(f"{C_YELLOW}{t('model_remove_none_left', active_language)}{C_RESET}\n")
                        else:
                            print(f"{C_RED}{msg}{C_RESET}\n")

                    if sub_cmd in ("remove", "delete", "rm", "del"):
                        do_model_delete(sub_val)
                        continue

                    def do_model_search(query_str: str):
                        nonlocal model_name
                        query = query_str
                        if not query:
                            q_prompt = t("hf_search_query_prompt", active_language)
                            query = input(q_prompt).strip()
                        if not query:
                            return

                        import hf_hub
                        print(f"\n{C_CYAN}Searching Hugging Face Hub for '{query}' (filter: GGUF)...{C_RESET}")
                        results = hf_hub.search_hf_gguf_models(query, limit=10)
                        if not results:
                            print(f"{C_YELLOW}{t('hf_search_no_results', active_language)} '{query}'{C_RESET}\n")
                            return

                        search_title = t("hf_search_title", active_language)
                        print(f"\n{C_BOLD}{search_title}{C_RESET}")
                        for idx, item in enumerate(results, start=1):
                            dl_count = item.get("downloads", 0)
                            likes = item.get("likes", 0)
                            sz_disp = item.get("size_display")
                            sz_badge = f" | {C_GREEN}📦 {sz_disp}{C_RESET}" if sz_disp and sz_disp != "N/A" else ""
                            print(f"  [{idx}] {C_CYAN}{item.get('id')}{C_RESET} (↓ {dl_count:,} | ♥ {likes}{sz_badge})")

                        choice_prompt = t("hf_search_select_repo", active_language, count=len(results))
                        repo_choice = input(f"\n{choice_prompt}").strip()
                        if not repo_choice.isdigit() or not (1 <= int(repo_choice) <= len(results)):
                            return

                        selected_repo = results[int(repo_choice) - 1]["id"]
                        print(f"\n{C_CYAN}Fetching GGUF files for {selected_repo}...{C_RESET}")
                        files = hf_hub.list_hf_gguf_files(selected_repo)
                        if not files:
                            print(f"{C_YELLOW}{t('hf_files_no_gguf', active_language)}{C_RESET}\n")
                            return

                        files_title = t("hf_files_title", active_language, repo=selected_repo)
                        print(f"\n{C_BOLD}{files_title}{C_RESET}")
                        for f_idx, f_item in enumerate(files, start=1):
                            print(f"  [{f_idx}] {C_GREEN}{f_item.get('path')}{C_RESET} {C_DIM}({f_item.get('size_display')}){C_RESET}")

                        file_prompt = t("hf_files_select", active_language, count=len(files))
                        file_choice = input(f"\n{file_prompt}").strip()
                        if not file_choice.isdigit() or not (1 <= int(file_choice) <= len(files)):
                            return

                        chosen_file = files[int(file_choice) - 1]["path"]
                        models_dir = config.REPO_ROOT / "models"
                        ok, msg, path_res = hf_hub.download_hf_gguf_file(selected_repo, chosen_file, models_dir, lang=active_language)
                        if ok and path_res:
                            print(f"\n{C_GREEN}✓ {msg}{C_RESET}\n")
                            ask_sw = input(t("model_switch_ask", active_language)).strip().lower()
                            if ask_sw in ("", "y", "yes") and server_mgr:
                                chosen_name = Path(path_res).name
                                server_mgr.start(str(path_res))
                                model_name = chosen_name
                                agent.model_name = chosen_name
                                agent.reset_session()
                                print(f"{C_GREEN}{t('model_switch_success', active_language)} {model_name}{C_RESET}\n")
                        else:
                            print(f"\n{C_RED}{msg}{C_RESET}\n")

                    if sub_cmd == "search":
                        do_model_search(sub_val)
                        continue

                    if sub_cmd == "download":
                        if sub_val:
                            ok, msg, path_res = config.download_model_from_catalog(sub_val, lang=active_language)
                            if ok and path_res:
                                print(f"{C_GREEN}✓ {msg}{C_RESET}\n")
                                ask_sw = input(t("model_switch_ask", active_language)).strip().lower()
                                if ask_sw in ("", "y", "yes") and server_mgr:
                                    chosen_name = Path(path_res).name
                                    server_mgr.start(path_res)
                                    model_name = chosen_name
                                    agent.model_name = chosen_name
                                    agent.reset_session()
                                    print(f"{C_GREEN}{t('model_switch_success', active_language)} {model_name}{C_RESET}\n")
                            else:
                                print(f"{C_RED}{msg}{C_RESET}\n")
                        else:
                            catalog = config.load_model_catalog()
                            cat_title = t("catalog_title", active_language)
                            rec_badge = t("catalog_recommendation", active_language)
                            print(f"\n{C_BOLD}{cat_title}{C_RESET}")
                            for m in catalog.get("models", []):
                                rec = f" {C_GREEN}{rec_badge}{C_RESET}" if m.get("recommended") else ""
                                print(f"  • {C_CYAN}{m.get('id')}{C_RESET} ({m.get('size_display')}): {m.get('name')}{rec}")
                                print(f"    {C_DIM}{m.get('description')}{C_RESET}")
                            print(f"\n{C_DIM}{t('model_download_tip', active_language)}{C_RESET}\n")
                        continue

                    available = config.list_gguf_models()
                    loc_title = t("local_models_title", active_language)
                    print(f"\n{C_BOLD}{loc_title}{C_RESET}")
                    for idx, m in enumerate(available, start=1):
                        p = Path(m)
                        m_display = p.name
                        size_str = ""
                        try:
                            f_path = p if p.is_absolute() else (config.REPO_ROOT / m)
                            if f_path.exists():
                                sz_gb = f_path.stat().st_size / (1024 ** 3)
                                size_str = f"({sz_gb:.2f} GB)"
                        except Exception:
                            pass
                        marker = f"{C_GREEN}* active{C_RESET}" if m == model_name or p.name == model_name else ""
                        print(f"  [{idx}] {m_display} {C_DIM}{size_str}{C_RESET} {marker}")

                    print(f"\n{C_BOLD}Model Actions / Pilihan Aksi:{C_RESET}")
                    print(f"  [{C_CYAN}s{C_RESET}] {t('model_sub_search', active_language)} (/model search)")
                    print(f"  [{C_CYAN}d{C_RESET}] {t('model_sub_download', active_language)} (/model download)")
                    print(f"  [{C_CYAN}a{C_RESET}] {t('model_sub_add', active_language)} (/model add <path>)")
                    print(f"  [{C_CYAN}r{C_RESET}] {t('model_sub_remove', active_language)} (/model remove <id>)")

                    if active_language == "id":
                        choice_prompt = f"\nPilih nomor (1-{len(available)}), 's' (cari), 'd' (katalog), 'a' (tambah), 'r' (hapus), atau enter: "
                    elif active_language == "cn":
                        choice_prompt = f"\n输入模型序号 (1-{len(available)}), 's' (搜索), 'd' (目录), 'a' (添加), 'r' (删除), 或按回车: "
                    else:
                        choice_prompt = f"\nEnter model number (1-{len(available)}), 's' (search), 'd' (catalog), 'a' (add), 'r' (remove), or press enter: "

                    choice = input(choice_prompt).strip()

                    if choice.lower() in ("r", "rm", "del", "delete", "remove") or choice.lower().startswith("remove ") or choice.lower().startswith("delete ") or choice.lower().startswith("rm ") or choice.lower().startswith("r "):
                        r_target = ""
                        if " " in choice:
                            r_target = choice.split(maxsplit=1)[1].strip()
                        do_model_delete(r_target)
                        continue

                    if choice.lower() in ("s", "search") or choice.lower().startswith("search ") or choice.lower().startswith("s "):
                        s_q = ""
                        if " " in choice:
                            s_q = choice.split(maxsplit=1)[1].strip()
                        do_model_search(s_q)
                        continue

                    if choice.lower() in ("d", "download") or choice.lower().startswith("download "):
                        d_id = choice.split(maxsplit=1)[1].strip() if " " in choice else ""
                        if d_id:
                            ok, msg, path_res = config.download_model_from_catalog(d_id, lang=active_language)
                            if ok and path_res:
                                print(f"{C_GREEN}✓ {msg}{C_RESET}\n")
                        else:
                            catalog = config.load_model_catalog()
                            cat_title = t("catalog_title", active_language)
                            print(f"\n{C_BOLD}{cat_title}{C_RESET}")
                            for m in catalog.get("models", []):
                                print(f"  • {C_CYAN}{m.get('id')}{C_RESET} ({m.get('size_display')}): {m.get('name')}")
                            print(f"\n{C_DIM}{t('model_download_tip', active_language)}{C_RESET}\n")
                        continue

                    if choice.lower().startswith("add ") or choice.lower().startswith("a ") or choice.lower() == "a":
                        if choice.lower().startswith("add "):
                            add_path = choice[4:].strip()
                        elif choice.lower().startswith("a "):
                            add_path = choice[2:].strip()
                        else:
                            add_path = input(t("model_add_prompt", active_language)).strip()
                        if add_path:
                            ok, msg, p_res = config.add_custom_model_path(add_path, lang=active_language)
                            if ok:
                                print(f"{C_GREEN}{msg}{C_RESET}\n")
                                if p_res and p_res.is_file():
                                    ask_sw = input(t("model_switch_ask", active_language)).strip().lower()
                                    if ask_sw in ("", "y", "yes") and server_mgr:
                                        server_mgr.start(str(p_res))
                                        model_name = p_res.name
                                        agent.model_name = p_res.name
                                        agent.reset_session()
                                        print(f"{C_GREEN}{t('model_switch_success', active_language)} {model_name}{C_RESET}\n")
                            else:
                                print(f"{C_RED}{msg}{C_RESET}\n")
                        continue

                    if choice.isdigit() and 1 <= int(choice) <= len(available):
                        chosen = available[int(choice) - 1]
                        chosen_name = Path(chosen).name
                        if chosen_name != model_name and server_mgr:
                            print(f"Restarting server with model: {chosen_name}...")
                            server_mgr.start(chosen)
                            model_name = chosen_name
                            agent.model_name = chosen_name
                            agent.reset_session()
                            print(f"{C_GREEN}✓ Active model updated to: {model_name}{C_RESET}\n")
                    continue
                elif cmd == "/ctx":
                    if arg in ("4096", "8192", "16384", "32768"):
                        new_ctx = int(arg)
                        if server_mgr:
                            print(f"Restarting server with context window: {new_ctx}...")
                            server_mgr.ctx_size = new_ctx
                            server_mgr.start(model_name)
                            args.ctx = new_ctx
                            agent.ctx_size = new_ctx
                            print(f"{C_GREEN}✓ Context window changed to: {new_ctx}{C_RESET}\n")
                    else:
                        print(f"Recommended context choices: 4096, 8192, 16384")
                    continue

                # --- CHECK IF USER INVOKED A SKILL DIRECTLY VIA /<skill_name> ---
                skill_slug = cmd[1:]
                skill_prompt = skills_mgr.get_skill_prompt(skill_slug)
                if skill_prompt:
                    user_goal = arg if arg else "Lakukan analisis mendalam dan susun laporan terstruktur sesuai panduan skill ini."
                    combined_prompt = (
                        f"[PANDUAN SKILL: /{skill_slug}]\n"
                        f"{skill_prompt}\n\n"
                        f"--- DIRECTIVE PELAKSANAAN (STRICT) ---\n"
                        f"1. Anda adalah pelaksana mandiri tugas ini. JANGAN mencoba memanggil sub-agent eksternal atau memperlakukan nama skill sebagai MCP server.\n"
                        f"2. SKILL BUKAN SERVER MCP. Dilarang memanggil `mcp_list_tools` atau `mcp_call` dengan nama skill.\n"
                        f"3. Jika Anda memerlukan fakta terkini, literatur, statistik, atau referensi eksternal, panggil tool `web_search(query)`.\n"
                        f"4. Langsung susun dan sajikan hasil riset/analisis Anda secara mendalam, terstruktur, dan profesional.\n\n"
                        f"TUGAS PENGGUNA: {user_goal}"
                    )
                    try:
                        reply = agent.run_turn(combined_prompt, on_status=on_status, on_tool=on_tool)
                        print(f"\n{C_BOLD}{reply}{C_RESET}\n")
                    except KeyboardInterrupt:
                        print(f"\n{C_YELLOW}⚠️  Skill execution cancelled by user (Ctrl+C).{C_RESET}\n")
                    continue
                else:
                    print(f"{C_YELLOW}Unknown command '{cmd}'. Type /help for assistance.{C_RESET}\n")
                    continue

            # Chat biasa
            try:
                reply = agent.run_turn(user_input, on_status=on_status, on_tool=on_tool)
                print(f"\n{C_BOLD}{reply}{C_RESET}\n")
            except KeyboardInterrupt:
                print(f"\n{C_YELLOW}⚠️  Operation cancelled by user (Ctrl+C). Returned to prompt.{C_RESET}\n")

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}Interrupt detected. Exiting...{C_RESET}")
    finally:
        print(f"{C_DIM}Cleaning up sessions and shutting down server...{C_RESET}")
        mcp_mgr.close_all()
        if started_by_us and server_mgr:
            server_mgr.stop()
        print(f"{C_GREEN}Goodbye! / Sampai jumpa!{C_RESET}")

if __name__ == "__main__":
    main()
