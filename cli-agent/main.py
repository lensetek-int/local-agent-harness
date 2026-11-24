import os
import sys
import argparse
from pathlib import Path

# Aktifkan dukungan ANSI escape sequences di Windows terminal
os.system("")

import config
from server_manager import LlamaServerManager
from tools_fs import LocalWorkspaceTools
from mcp_client import MCPManager
from skills_manager import SkillManager
from scheduler import TaskScheduler
from web_search import headless_web_search, format_search_results
from agent import LeanAgent
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
        def __init__(self, get_items_fn, get_lang_fn=None):
            self.get_items_fn = get_items_fn
            self.get_lang_fn = get_lang_fn or (lambda: "en")

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            if not text.startswith("/"):
                return

            cur_lang = self.get_lang_fn()

            if " " in text:
                tokens = text.split()
                first_word = tokens[0].lower()
                if first_word == "/mcp" and len(tokens) == 2 and not text.endswith(" "):
                    sub = tokens[1].lower()
                    mcp_subs = [
                        ("install", t("mcp_sub_install", cur_lang)),
                        ("test", t("mcp_sub_test", cur_lang)),
                        ("remove", t("mcp_sub_remove", cur_lang)),
                        ("enable", t("mcp_sub_enable", cur_lang)),
                        ("disable", t("mcp_sub_disable", cur_lang))
                    ]
                    for sc, desc in mcp_subs:
                        if sc.startswith(sub):
                            yield Completion(sc, start_position=-len(tokens[1]), display=sc, display_meta=desc)
                elif first_word == "/model" and len(tokens) == 2 and not text.endswith(" "):
                    sub = tokens[1].lower()
                    model_subs = [
                        ("download", t("model_sub_download", cur_lang)),
                        ("add", t("model_sub_add", cur_lang))
                    ]
                    for sc, desc in model_subs:
                        if sc.startswith(sub):
                            yield Completion(sc, start_position=-len(tokens[1]), display=sc, display_meta=desc)
                elif first_word == "/language" and len(tokens) == 2 and not text.endswith(" "):
                    sub = tokens[1].lower()
                    lang_opts = [
                        ("en", "English (Default)"),
                        ("id", "Bahasa Indonesia"),
                        ("cn", "简体中文 (Chinese)")
                    ]
                    for lc, ldesc in lang_opts:
                        if lc.startswith(sub):
                            yield Completion(lc, start_position=-len(tokens[1]), display=lc, display_meta=ldesc)
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

def print_banner(workspace: Path, model_name: str, ctx_size: int, port: int, mcp_names: list[str], safety_mode: str, skills_count: int, language: str):
    lang_name = config.SUPPORTED_LANGUAGES.get(language, language.upper())
    skills_lbl = t("banner_skills_detected", language)
    tip_lbl = t("banner_tip", language)
    print(f"{C_CYAN}{C_BOLD}===================================================================={C_RESET}")
    print(f"{C_CYAN}{C_BOLD}        ⚡ LENSETEK LEAN AGENT HARNESS                             {C_RESET}")
    print(f"{C_CYAN}{C_BOLD}===================================================================={C_RESET}")
    print(f" {C_BOLD}Workspace:{C_RESET} {workspace}")
    print(f" {C_BOLD}Model:{C_RESET}     {model_name} {C_DIM}(port: {port}, ctx: {ctx_size}){C_RESET}")
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

def main():
    parser = argparse.ArgumentParser(description="LENSETEK LEAN AGENT HARNESS")
    parser.add_argument("--workspace", "-w", default=".", help="Folder kerja awal (default: '.')")
    parser.add_argument("--model", "-m", default=None, help="Nama model GGUF (default: auto pick)")
    parser.add_argument("--ctx", "-c", type=int, default=config.DEFAULT_CTX, help="Ukuran context window (default: 8192)")
    parser.add_argument("--port", "-p", type=int, default=config.DEFAULT_PORT, help="Port llama-server (default: 8081)")
    parser.add_argument("--no-server", action="store_true", help="Jangan otomatis jalankan llama-server internal")
    parser.add_argument("--auto-approve", action="store_true", help="Mode auto-approve aksi di dalam workspace")
    parser.add_argument("--yolo", action="store_true", help="Mode tanpa konfirmasi (kecuali fatal command)")
    parser.add_argument("--once", type=str, default=None, help="Jalankan 1 tugas secara headless lalu keluar")
    args = parser.parse_args()

    # Baca preferensi bahasa pengguna terlebih dahulu (default: en)
    active_language = config.get_active_language()

    workspace_path = Path(args.workspace).resolve()
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
    elif args.once:
        safety_mode = "read-only"
    else:
        safety_mode = "strict"

    server_mgr = None
    started_by_us = False
    if not args.no_server:
        server_mgr = LlamaServerManager(port=args.port, ctx_size=args.ctx)
        if server_mgr.is_healthy():
            started_by_us = False
        else:
            if not args.once:
                print(f"{C_DIM}Starting llama-server for model '{model_name}' on port {args.port}...{C_RESET}")
            try:
                server_mgr.start(model_name)
                started_by_us = True
                if not args.once:
                    print(f"{C_GREEN}✓ llama-server active at http://127.0.0.1:{args.port} (ctx: {args.ctx}){C_RESET}\n")
            except Exception as e:
                print(f"{C_RED}[ERROR] Failed to start llama-server: {e}{C_RESET}")
                sys.exit(1)

    fs_tools = LocalWorkspaceTools(workspace_root=str(workspace_path), safety_mode=safety_mode)
    mcp_config = config.load_mcp_config()
    mcp_mgr = MCPManager(config_dict=mcp_config, safety_mode=safety_mode)
    skills_mgr = SkillManager(local_skills_dir=config.CLI_DIR / "skills", workspace_root=workspace_path, safety_mode=safety_mode)
    scheduler = TaskScheduler()

    agent = LeanAgent(
        base_url=f"http://127.0.0.1:{args.port}",
        fs_tools=fs_tools,
        mcp_manager=mcp_mgr,
        skills_manager=skills_mgr,
        ctx_size=args.ctx,
        model_name=model_name,
        language=active_language
    )

    def on_status(msg):
        if not args.once:
            print(f"{C_DIM}⏳ {msg}{C_RESET}")

    def on_tool(t_name, t_args, t_result):
        if args.once:
            return
        if t_result is None:
            args_summary = str(t_args)[:80]
            print(f"{C_MAGENTA}⚙️  [TOOL CALL] {t_name}({args_summary}){C_RESET}")
        else:
            res_lines = t_result.strip().splitlines()
            first_line = res_lines[0][:100] if res_lines else "OK"
            print(f"{C_DIM}   └─ Result: {first_line}{C_RESET}")

    # --- JIKA RUN DALAM MODE --ONCE (Headless) ---
    if args.once:
        try:
            res = agent.run_turn(args.once, on_status=None, on_tool=None)
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
            completer = SlashCommandCompleter(lambda: get_slash_items(skills_mgr, active_language), lambda: active_language)

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
                    if b.text.startswith('/'):
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

    # --- INTERACTIVE CLI UI ---
    all_skills = skills_mgr.scan_skills()
    print_banner(workspace_path, model_name, args.ctx, args.port, mcp_mgr.get_server_names(), safety_mode, len(all_skills), active_language)

    try:
        while True:
            total_tok = agent.last_usage.get("total_tokens", 0)
            pct = (total_tok / args.ctx) * 100.0 if args.ctx else 0.0
            print(f"{C_DIM}~ [{workspace_path.name}] {pct:.1f}%/{args.ctx // 1024}k tok [{safety_mode.upper()}|{active_language.upper()}] ({model_name}){C_RESET}")

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

                # --- MODEL & CTX COMMANDS ---
                elif cmd == "/model":
                    arg_parts = arg.split(maxsplit=1)
                    sub_cmd = arg_parts[0].lower() if arg_parts else ""
                    sub_val = arg_parts[1].strip() if len(arg_parts) > 1 else ""

                    if sub_cmd == "add" and sub_val:
                        ok, msg = config.add_custom_model_path(sub_val)
                        if ok:
                            print(f"{C_GREEN}✓ {msg}{C_RESET}\n")
                        else:
                            print(f"{C_RED}{msg}{C_RESET}\n")
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

                    print(f"\n{C_DIM}{t('model_selection_tip', active_language)}{C_RESET}")
                    choice_prompt = t("model_select_prompt", active_language, count=len(available))
                    choice = input(choice_prompt).strip()

                    if choice.lower().startswith("add "):
                        add_path = choice[4:].strip()
                        ok, msg = config.add_custom_model_path(add_path)
                        print(f"{C_GREEN if ok else C_RED}{msg}{C_RESET}\n")
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
