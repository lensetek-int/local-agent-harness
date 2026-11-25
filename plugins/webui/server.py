"""
Lensetek Agent WebUI Server
Serves the modern Antigravity/Codex-style responsive Web IDE & Agent Interface
and bridges it directly to LeanAgent, LocalWorkspaceTools, SessionManager, and llama-server.
Strictly binds to 127.0.0.1 and blocks credential/secret file access.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure cli-agent modules are importable
_THIS_DIR = Path(__file__).resolve().parent
_REPO_CLI = _THIS_DIR.parent.parent / "cli-agent"
_HOME_CLI = Path.home() / ".lensetek-agent" / "cli-agent"
for _p in (_REPO_CLI, _HOME_CLI):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import config
from agent import LeanAgent
from mcp_client import MCPManager
from server_manager import LlamaServerManager
from session_manager import SessionManager
from skills_manager import SkillManager
from tools_fs import LocalWorkspaceTools
from web_search import format_search_results, headless_web_search

try:
    from i18n import get_localized_slash_items
except ImportError:
    def get_localized_slash_items(lang="en"):
        return []

try:
    import plugin_manager
except ImportError:
    plugin_manager = None

try:
    import version as app_version
except ImportError:
    app_version = None

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".turbo"}
SENSITIVE_EXTS = {".pem", ".key", ".p12", ".pfx", ".crt", ".jks", ".keystore"}
SENSITIVE_KEYWORDS = (
    ".env",
    "secret",
    "credential",
    "password",
    "private_key",
    "id_rsa",
    "id_ed25519",
    "service_account",
    ".htpasswd",
    ".netrc",
    ".npmrc",
    ".pypirc",
)


def is_sensitive_path(target: Path, workspace_root: Path) -> bool:
    """Strictly block access to credentials, keys, .env files, and .git internals."""
    try:
        rel = target.resolve().relative_to(workspace_root.resolve())
    except Exception:
        return True

    for part in rel.parts:
        low = part.lower()
        if low == ".git":
            return True
        if low.startswith(".env"):
            return True
        for kw in SENSITIVE_KEYWORDS:
            if kw in low:
                return True

    if target.suffix.lower() in SENSITIVE_EXTS:
        return True
    return False


class WebUIBackendState:
    """Thread-safe controller bridging the HTTP server and LeanAgent."""

    def __init__(
        self,
        workspace: Path,
        llama_port: int = 8081,
        ctx_size: int = config.DEFAULT_CTX,
        model_name: Optional[str] = None,
        server_mgr: Optional[LlamaServerManager] = None,
        agent: Optional[LeanAgent] = None,
    ):
        self.workspace_root = Path(workspace).resolve()
        self.llama_port = llama_port
        self.ctx_size = ctx_size
        self.language = config.get_active_language()
        self.effort = config.get_active_effort()
        self.safety_mode = "strict"

        self.agent_lock = threading.Lock()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.jobs_lock = threading.Lock()
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        self.approvals_lock = threading.Lock()
        self.active_job_id: Optional[str] = None

        self.server_mgr = server_mgr or LlamaServerManager(port=llama_port, ctx_size=ctx_size)
        self.session_mgr = SessionManager()
        self.skills_mgr = SkillManager(
            local_skills_dir=config.CLI_DIR / "skills",
            workspace_root=self.workspace_root,
            safety_mode=self.safety_mode,
        )

        if agent is not None:
            self.agent = agent
            self.fs_tools = agent.fs_tools
            self.mcp_mgr = agent.mcp_manager
            self.safety_mode = getattr(self.fs_tools, "safety_mode", "strict")
            self.model_name = agent.model_name or model_name or config.pick_default_model()
        else:
            self.model_name = model_name or config.pick_default_model()
            self.fs_tools = LocalWorkspaceTools(
                workspace_root=str(self.workspace_root),
                confirm_fn=self._web_confirm,
                safety_mode=self.safety_mode,
            )
            mcp_cfg = config.load_mcp_config()
            self.mcp_mgr = MCPManager(config_dict=mcp_cfg, safety_mode=self.safety_mode)
            self.agent = LeanAgent(
                base_url=f"http://127.0.0.1:{self.llama_port}",
                fs_tools=self.fs_tools,
                mcp_manager=self.mcp_mgr,
                skills_manager=self.skills_mgr,
                session_manager=self.session_mgr,
                ctx_size=self.ctx_size,
                model_name=self.model_name,
                language=self.language,
                effort_level=self.effort,
            )
            active_sess = self.session_mgr.get_active_session()
            self.loaded_session_id = active_sess.get("id") if active_sess else None
            if active_sess:
                self.agent.load_session(active_sess)
        if not hasattr(self, "loaded_session_id"):
            active_sess = self.session_mgr.get_active_session()
            self.loaded_session_id = active_sess.get("id") if active_sess else None

    def _web_confirm(self, prompt_text: str) -> bool:
        """Pause tool execution and request approval in the active WebUI job."""
        if getattr(self.agent, "cancel_requested", False):
            return False
        job_id = self.active_job_id
        if not job_id:
            return False

        app_id = uuid.uuid4().hex[:10]
        evt = threading.Event()
        with self.approvals_lock:
            self.pending_approvals[app_id] = {
                "id": app_id,
                "prompt": prompt_text,
                "event": evt,
                "approved": False,
            }

        self._push_event(
            job_id,
            {
                "type": "approval_required",
                "approval_id": app_id,
                "prompt": prompt_text,
            },
        )

        # Wait up to 5 minutes for user click in WebUI
        evt.wait(timeout=300)
        with self.approvals_lock:
            rec = self.pending_approvals.pop(app_id, None)
            return bool(rec and rec.get("approved", False))

    def resolve_approval(self, approval_id: str, approved: bool) -> bool:
        with self.approvals_lock:
            rec = self.pending_approvals.get(approval_id)
            if not rec:
                return False
            rec["approved"] = bool(approved)
            rec["event"].set()
            return True

    def cancel_active_job(self, job_id: Optional[str] = None) -> bool:
        """Cancel the currently running agent job and unblock any pending approvals."""
        target_job_id = self.active_job_id or job_id
        self.agent.cancel()

        with self.approvals_lock:
            for rec in self.pending_approvals.values():
                rec["approved"] = False
                rec["event"].set()

        if target_job_id:
            self._push_event(target_job_id, {"type": "status", "message": "Cancelling..."})
            return True
        return False

    def cancel_active_job(self) -> bool:
        """Cancel current ongoing turn and unblock any pending approval prompts."""
        if hasattr(self, "agent") and self.agent:
            self.agent.cancel()
        with self.approvals_lock:
            for app_id, rec in list(self.pending_approvals.items()):
                rec["approved"] = False
                rec["event"].set()
        return True

    def _push_event(self, job_id: str, event: Dict[str, Any]):
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if job is not None:
                event["ts"] = time.time()
                job["events"].append(event)

    def get_slash_commands_payload(self) -> List[Dict[str, str]]:
        """Return all slash commands and discovered skills for WebUI '/' autocomplete."""
        items: List[Dict[str, str]] = []
        for cmd, desc, cat in get_localized_slash_items(self.agent.language):
            items.append({"cmd": cmd, "desc": desc, "cat": cat})

        try:
            all_skills = self.skills_mgr.scan_skills()
            for slug, s_data in all_skills.items():
                items.append({
                    "cmd": f"/{slug}",
                    "desc": s_data.get("description", "Activate skill"),
                    "cat": s_data.get("source", "skill").upper(),
                })
        except Exception:
            pass
        return items

    def _handle_slash_command(self, raw_text: str, job_id: str, on_status, on_tool) -> Optional[str]:
        """Handle '/' slash commands directly, returning reply string or None if delegated to agent."""
        parts = raw_text.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/help":
            lines = ["### Available Slash Commands\n"]
            for c_name, c_desc, c_cat in get_localized_slash_items(self.agent.language):
                lines.append(f"- `{c_name}` **[{c_cat}]** — {c_desc}")
            lines.append("\n*Tip: Type `/` in the composer for live autocomplete, or `/<skill-name> [task]` to run any skill.*")
            return "\n".join(lines)

        if cmd in ("/new", "/clear"):
            title = arg if arg else None
            sess = self.session_mgr.create_session(name=title)
            self.loaded_session_id = sess.get("id")
            self.agent.reset_session()
            self._push_event(job_id, {"type": "state_updated", "reset_view": cmd == "/clear"})
            return f"✓ Started new session: **{sess['name']}** (`{sess['id']}`)"

        if cmd == "/strict":
            self.fs_tools.set_safety_mode("strict")
            self.safety_mode = "strict"
            self._push_event(job_id, {"type": "state_updated"})
            return "✓ Safety mode set to **STRICT** (asks permission for file writes and commands)."

        if cmd == "/auto-approve":
            self.fs_tools.set_safety_mode("auto-approve")
            self.safety_mode = "auto-approve"
            self._push_event(job_id, {"type": "state_updated"})
            return "✓ Safety mode set to **AUTO-APPROVE** (workspace changes approved automatically)."

        if cmd == "/yolo":
            self.fs_tools.set_safety_mode("yolo")
            self.safety_mode = "yolo"
            self._push_event(job_id, {"type": "state_updated"})
            return "✓ Safety mode set to **YOLO** (unrestricted local execution)."

        if cmd == "/effort":
            if arg.lower() in ("off", "low", "medium", "high"):
                lvl = arg.lower()
                config.set_active_effort(lvl)
                self.agent.set_effort(lvl)
                self.effort = lvl
                self._push_event(job_id, {"type": "state_updated"})
                return f"✓ Thinking effort updated to **{lvl.upper()}**."
            return f"Current thinking effort: **{self.agent.effort_level.upper()}**\nUsage: `/effort <off|low|medium|high>`"

        if cmd == "/language":
            if not arg:
                return f"Active language: **{self.agent.language}**\nSupported: `/language en`, `/language id`, `/language cn`"
            ok, msg = config.set_active_language(arg)
            if ok:
                new_lang = config.get_active_language()
                self.agent.set_language(new_lang)
                self.language = new_lang
                self._push_event(job_id, {"type": "state_updated"})
                return f"✓ {msg}"
            return f"**Error:** {msg}"

        if cmd == "/model":
            if not arg:
                models = config.list_gguf_models()
                lines = [f"**Active Model:** `{Path(self.model_name).name if self.model_name else 'None'}`\n\n**Available Local Models:**"]
                for m in models:
                    lines.append(f"- `{Path(m).name}`")
                lines.append("\nSwitch via `/model <filename>` or use the top model dropdown.")
                return "\n".join(lines)
            m_parts = arg.split(maxsplit=1)
            m_sub = m_parts[0].lower()
            m_rest = m_parts[1].strip() if len(m_parts) > 1 else ""
            if m_sub == "search":
                if not m_rest:
                    return "Usage: `/model search <query>`"
                try:
                    from hf_hub import search_hf_gguf_models
                    results = search_hf_gguf_models(m_rest, limit=8)
                    if not results:
                        return f"No GGUF models found on Hugging Face for `{m_rest}`."
                    lines = [f"### Hugging Face GGUF Results for `{m_rest}`\n"]
                    for r in results:
                        lines.append(f"- `{r.get('id')}` (downloads: {r.get('downloads', 0)})")
                    return "\n".join(lines)
                except Exception as exc:
                    return f"**Error searching models:** {exc}"
            if m_sub in ("download", "add", "remove"):
                return f"Interactive `/model {m_sub}` is available in the CLI terminal (`lensetek`). In WebUI, use `/model <filename>` or the top model dropdown to switch installed models."
            models = config.list_gguf_models()
            matches = [m for m in models if arg.lower() in Path(m).name.lower()]
            if not matches:
                return f"No local model matching `{arg}` found."
            chosen = matches[0]
            self.model_name = chosen
            self.agent.model_name = Path(chosen).name
            self.server_mgr.start(chosen)
            self.agent.reset_session()
            self._push_event(job_id, {"type": "state_updated"})
            return f"✓ Active model switched to **{Path(chosen).name}**."

        if cmd == "/session":
            sub_parts = arg.split(maxsplit=1) if arg else []
            s_action = sub_parts[0].lower() if sub_parts else "list"
            s_param = sub_parts[1].strip() if len(sub_parts) > 1 else ""

            if s_action in ("list", "ls"):
                sessions = self.session_mgr.list_sessions()
                act_id = self.session_mgr.get_active_session_id()
                lines = ["### Chat Sessions\n"]
                for idx, s in enumerate(sessions, 1):
                    mark = " **(active)**" if s.get("id") == act_id else ""
                    lines.append(f"{idx}. **{s.get('name', 'Session')}** (`{s.get('id')}`){mark}")
                return "\n".join(lines)

            if s_action in ("new", "create"):
                new_s = self.session_mgr.create_session(name=s_param or None, model_name=self.model_name or "")
                self.loaded_session_id = new_s.get("id")
                self.agent.load_session(new_s)
                self._push_event(job_id, {"type": "state_updated", "reset_view": True})
                return f"✓ Created new session: **{new_s['name']}** (`{new_s['id']}`)"

            if s_action in ("switch", "use"):
                if not s_param:
                    return "Usage: `/session switch <id|number>`"
                ok, msg, s_data = self.session_mgr.switch_session(s_param)
                if ok and s_data:
                    self.loaded_session_id = s_data.get("id")
                    self.agent.load_session(s_data)
                    self._push_event(job_id, {"type": "state_updated", "reset_view": True})
                    return f"✓ Switched to session: **{s_data['name']}** (`{s_data['id']}`)"
                return f"**Error:** {msg}"

            if s_action in ("rename", "mv"):
                if not s_param:
                    return "Usage: `/session rename <new_name>` or `/session rename <id|number> <new_name>`"
                r_parts = s_param.split(maxsplit=1)
                all_s = self.session_mgr.list_sessions()
                if len(r_parts) > 1 and ((r_parts[0].isdigit() and int(r_parts[0]) <= len(all_s)) or any(s["id"] == r_parts[0] for s in all_s)):
                    target_id, new_name = r_parts[0], r_parts[1].strip()
                else:
                    target_id, new_name = None, s_param
                ok, msg = self.session_mgr.rename_session(target_id, new_name)
                if ok:
                    self._push_event(job_id, {"type": "state_updated"})
                    return f"✓ {msg}"
                return f"**Error:** {msg}"

            if s_action in ("delete", "rm", "remove"):
                if not s_param:
                    return "Usage: `/session delete <id|number>`"
                ok, msg = self.session_mgr.delete_session(s_param)
                if ok:
                    act_s = self.session_mgr.get_active_session()
                    if act_s:
                        self.loaded_session_id = act_s.get("id")
                        self.agent.load_session(act_s)
                    self._push_event(job_id, {"type": "state_updated", "reset_view": True})
                    return f"✓ {msg}"
                return f"**Error:** {msg}"

            return "Usage: `/session <list|new|switch|rename|delete> [args]`"

        if cmd == "/workspace":
            if not arg:
                return f"**Current workspace:** `{self.workspace_root}`"
            new_p = Path(arg).expanduser().resolve()
            if new_p.exists() and new_p.is_dir():
                self.workspace_root = new_p
                self.fs_tools.set_workspace(str(new_p))
                self.skills_mgr.workspace_root = new_p
                self._push_event(job_id, {"type": "state_updated"})
                return f"✓ Workspace changed to `{new_p}`"
            return f"**Error:** Directory not found: `{arg}`"

        if cmd == "/ctx":
            if arg in ("4096", "8192", "16384", "32768"):
                new_ctx = int(arg)
                self.ctx_size = new_ctx
                self.agent.ctx_size = new_ctx
                self.server_mgr.ctx_size = new_ctx
                if self.model_name and self.server_mgr.is_healthy():
                    self._push_event(job_id, {"type": "status", "message": f"Restarting llama-server (ctx={new_ctx})..."})
                    self.server_mgr.start(self.model_name)
                self._push_event(job_id, {"type": "state_updated"})
                return f"✓ Context window updated to **{new_ctx}**."
            return f"Current context window: **{self.agent.ctx_size}**\nUsage: `/ctx <4096|8192|16384|32768>`"

        if cmd == "/search":
            if not arg:
                return "Usage: `/search <query>`"
            self._push_event(job_id, {"type": "status", "message": f"Searching web for '{arg}'..."})
            res_list = headless_web_search(arg, max_results=5)
            return format_search_results(res_list)

        if cmd == "/skills":
            skills = self.skills_mgr.scan_skills()
            lines = [f"### Discovered Skills ({len(skills)})\n"]
            count = 0
            for slug, s_data in skills.items():
                if arg and arg.lower() not in slug.lower() and arg.lower() not in s_data.get("description", "").lower():
                    continue
                lines.append(f"- `/{slug}` — {s_data.get('description', '')}")
                count += 1
                if count >= 25:
                    lines.append("\n*...showing first 25 matches. Use `/skills <keyword>` to filter.*")
                    break
            return "\n".join(lines)

        if cmd == "/skill":
            if arg.lower().startswith("create"):
                body = arg[len("create"):].strip()
                s_parts = [p.strip() for p in body.split("|")]
                if len(s_parts) >= 2:
                    s_name = s_parts[0]
                    s_desc = s_parts[1]
                    s_inst = s_parts[2] if len(s_parts) > 2 else f"Instructions for skill {s_name}."
                    return self.skills_mgr.create_skill(s_name, s_desc, s_inst)
            return "Usage: `/skill create <name> | <description> | <instructions>`"

        if cmd == "/mcp":
            if not arg:
                lines = ["### Registered MCP Servers\n"]
                for k, v in self.mcp_mgr.config.items():
                    st = "ENABLED" if v.get("enabled", True) else "DISABLED"
                    lines.append(f"- `{k}` **[{st}]** — {v.get('description', '')}")
                lines.append(f"\nPresets: `{', '.join(config.MCP_PRESETS.keys())}`")
                lines.append("Usage: `/mcp <install|test|enable|disable|remove> <name>`")
                return "\n".join(lines)
            m_parts = arg.split(maxsplit=2)
            sub_cmd = m_parts[0].lower()
            s_target = m_parts[1] if len(m_parts) > 1 else ""
            s_rest = m_parts[2] if len(m_parts) > 2 else ""
            if sub_cmd == "install" and s_target:
                if s_rest:
                    cmd_tokens = s_rest.split()
                    return self.mcp_mgr.install_server(s_target, command=cmd_tokens[0], args=cmd_tokens[1:])
                return self.mcp_mgr.install_server(s_target)
            if sub_cmd == "test" and s_target:
                return self.mcp_mgr.test_server(s_target)
            if sub_cmd == "remove" and s_target:
                return self.mcp_mgr.remove_server(s_target)
            if sub_cmd == "enable" and s_target:
                return self.mcp_mgr.toggle_server(s_target, True)
            if sub_cmd == "disable" and s_target:
                return self.mcp_mgr.toggle_server(s_target, False)
            return "Usage: `/mcp <install|test|enable|disable|remove> <name>`"

        if cmd == "/schedule":
            try:
                from scheduler import SchedulerManager
                sched = SchedulerManager()
            except Exception as exc:
                return f"**Error:** Scheduler unavailable ({exc})."
            sch_parts = arg.split(maxsplit=4)
            sch_action = sch_parts[0].lower() if sch_parts else "list"
            if sch_action == "list":
                lines = ["### In-App Schedules\n"]
                in_app = sched.list_in_app()
                if in_app:
                    for item in in_app:
                        lines.append(f"- `{item['name']}` ({item['spec']}): {item['prompt'][:60]}")
                else:
                    lines.append("- *(none)*")
                lines.append("\n### OS Schedules\n```\n" + str(sched.list_os_tasks()) + "\n```")
                return "\n".join(lines)
            if sch_action == "add" and len(sch_parts) >= 5:
                sch_type, sch_name, sch_spec, sch_prompt = sch_parts[1].lower(), sch_parts[2], sch_parts[3], sch_parts[4]
                if sch_type == "os":
                    s_flag = "--auto-approve" if self.safety_mode == "auto-approve" else ("--yolo" if self.safety_mode == "yolo" else "")
                    return sched.register_os_task(sch_name, sch_spec, sch_prompt, str(self.workspace_root), safety_flag=s_flag)
                return "In WebUI, `/schedule add os <name> <5m|1h|daily 08:00> <prompt>` is supported. For `in-app` schedules, use the CLI (`lensetek`)."
            if sch_action == "remove" and len(sch_parts) >= 2:
                rem_name = sch_parts[1]
                sched.remove_in_app(rem_name)
                return sched.remove_os_task(rem_name)
            return "Usage: `/schedule list` | `/schedule add os <name> <5m|1h|daily 08:00> <prompt>` | `/schedule remove <name>`"

        if cmd == "/update":
            if not app_version:
                return "Version manager is not available."
            info = app_version.check_for_updates(force=True)
            if info.get("error"):
                return f"**Update check error:** {info['error']}"
            if info.get("update_available"):
                latest = info.get("latest_version")
                if arg.lower() in ("apply", "now", "yes"):
                    ok, msg = app_version.perform_update()
                    return f"✓ {msg} (Restart `lensetek --gui` to load the new version.)" if ok else f"**Update failed:** {msg}"
                notes = "\n".join(f"- {w}" for w in info.get("whats_new", [])[:6])
                return f"**Update available:** `v{latest}` (current: `v{app_version.get_current_version()}`)\n\n{notes}\n\nRun `/update apply` to install the update."
            return f"✓ You are already on the latest version (`v{app_version.get_current_version()}`)."

        if cmd in ("/gui", "/webui"):
            return "✓ Lensetek WebUI is already active."

        if cmd in ("/exit", "/quit"):
            return "In WebUI, you can close this browser tab or press `Ctrl+C` in the terminal running `lensetek --gui` to stop the server."

        if cmd == "/plugins":
            if not plugin_manager:
                return "Plugin manager is not available."
            p_parts = arg.split(maxsplit=1)
            p_act = p_parts[0].lower() if p_parts else "list"
            p_val = p_parts[1].strip() if len(p_parts) > 1 else ""
            if p_act == "install" and p_val:
                ok, msg = plugin_manager.install_plugin(p_val, lang=self.agent.language)
                return msg
            if p_act in ("remove", "uninstall") and p_val:
                ok, msg = plugin_manager.uninstall_plugin(p_val, lang=self.agent.language)
                return msg
            if p_act == "create" and p_val:
                ok, msg = plugin_manager.create_plugin_scaffold(p_val, lang=self.agent.language)
                return msg
            items = plugin_manager.get_all_catalog_plugins()
            if p_act == "search" and p_val:
                q_low = p_val.lower()
                items = [
                    i for i in items
                    if q_low in i.get("id", "").lower()
                    or q_low in i.get("name", "").lower()
                    or q_low in i.get("description", "").lower()
                ]
            lines = ["### Plugin Catalog\n"]
            for itm in items:
                st = "Installed" if itm.get("is_installed") else "Available"
                desc = itm.get(f"description_{self.agent.language}", itm.get("description", ""))
                lines.append(f"- `{itm.get('id')}` **[{st}]** — {desc}")
            lines.append("\nUsage: `/plugins list`, `/plugins search <q>`, `/plugins install <id>`, `/plugins remove <id>`, `/plugins create <name>`")
            return "\n".join(lines)

        if cmd == "/goal":
            if not arg:
                return "Usage: `/goal <autonomous goal description>`"
            if not self.server_mgr.is_healthy() and self.model_name:
                self._push_event(job_id, {"type": "status", "message": f"Starting llama-server ({Path(self.model_name).name})..."})
                self.server_mgr.start(self.model_name)
            return self.agent.run_goal(arg, max_steps=20, on_status=on_status, on_tool=on_tool)

        if cmd == "/loop":
            l_parts = arg.split(maxsplit=1)
            if len(l_parts) < 2:
                return "Usage: `/loop <3x|30s|5m> <task to repeat>`"
            if not self.server_mgr.is_healthy() and self.model_name:
                self._push_event(job_id, {"type": "status", "message": f"Starting llama-server ({Path(self.model_name).name})..."})
                self.server_mgr.start(self.model_name)
            def _on_iter(i, total):
                lbl = f"Loop iteration {i}/{total}..." if total else f"Loop iteration {i}..."
                self._push_event(job_id, {"type": "status", "message": lbl})
            return self.agent.run_loop(l_parts[0], l_parts[1], on_status=on_status, on_tool=on_tool, on_iteration=_on_iter)

        # Check if user invoked a skill directly via /<skill_slug>
        skill_slug = cmd[1:]
        skill_prompt = self.skills_mgr.get_skill_prompt(skill_slug)
        if skill_prompt:
            trimmed_skill = skill_prompt[:3200]
            user_goal = arg if arg else "Execute this skill workflow and save requested output files directly in the workspace."
            combined = (
                f"[SKILL GUIDE: /{skill_slug}]\n"
                f"{trimmed_skill}\n\n"
                f"[EXECUTION NOTE: Execute directly using workspace tools (`list_dir`, `read_file` for text/PDF/DOCX, and `write_or_edit_file` to create `.md`/`.docx`/code files on disk). Do not delegate to subagents or MCP.]\n"
                f"USER TASK: {user_goal}"
            )
            if not self.server_mgr.is_healthy() and self.model_name:
                self._push_event(job_id, {"type": "status", "message": f"Starting llama-server ({Path(self.model_name).name})..."})
                self.server_mgr.start(self.model_name)
            return self.agent.run_turn(combined, on_status=on_status, on_tool=on_tool)

        return f"Unknown command `{cmd}`. Type `/help` to see available commands."

    def start_chat_job(self, prompt_text: str) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self.jobs_lock:
            self.jobs[job_id] = {"id": job_id, "done": False, "events": []}

        def _worker():
            # Temporarily attach web confirm callback while running from WebUI
            prev_confirm = self.fs_tools.confirm_fn
            self.fs_tools.confirm_fn = self._web_confirm
            with self.agent_lock:
                self.active_job_id = job_id
                try:
                    # Auto-sync session if active_session_id changed externally
                    cur_sid = self.session_mgr.get_active_session_id()
                    if cur_sid and cur_sid != getattr(self, "loaded_session_id", None):
                        cur_sess = self.session_mgr.get_active_session()
                        if cur_sess is not None:
                            self.agent.load_session(cur_sess)
                            self.loaded_session_id = cur_sid

                    def on_status(msg: str):
                        self._push_event(job_id, {"type": "status", "message": msg})

                    def on_tool(t_name: str, t_args: Any, t_result: Optional[str]):
                        if t_result is None:
                            self._push_event(
                                job_id,
                                {"type": "tool_call", "name": t_name, "args": t_args},
                            )
                        else:
                            self._push_event(
                                job_id,
                                {
                                    "type": "tool_result",
                                    "name": t_name,
                                    "result": str(t_result)[:4000],
                                },
                            )

                    if prompt_text.lstrip().startswith("/"):
                        reply = self._handle_slash_command(prompt_text.lstrip(), job_id, on_status, on_tool)
                    else:
                        # Ensure llama-server is running if model exists
                        if not self.server_mgr.is_healthy() and self.model_name:
                            self._push_event(
                                job_id,
                                {"type": "status", "message": f"Starting llama-server ({Path(self.model_name).name})..."},
                            )
                            self.server_mgr.start(self.model_name)
                        reply = self.agent.run_turn(prompt_text, on_status=on_status, on_tool=on_tool)

                    self._push_event(
                        job_id,
                        {
                            "type": "assistant_reply",
                            "content": reply,
                            "usage": self.agent.last_usage,
                        },
                    )
                except Exception as exc:
                    self._push_event(job_id, {"type": "error", "message": str(exc)})
                finally:
                    self.active_job_id = None
                    self.fs_tools.confirm_fn = prev_confirm
                    with self.jobs_lock:
                        if job_id in self.jobs:
                            self.jobs[job_id]["done"] = True

        threading.Thread(target=_worker, daemon=True).start()
        return job_id

    def get_state_payload(self) -> Dict[str, Any]:
        models_raw = config.list_gguf_models()
        models_info = []
        for m in models_raw:
            p = Path(m)
            sz_mb = round(p.stat().st_size / (1024 * 1024), 1) if p.exists() else 0
            models_info.append({"name": p.name, "path": str(p), "size_mb": sz_mb})

        sessions_list = self.session_mgr.list_sessions()
        active_sess = self.session_mgr.get_active_session()

        return {
            "workspace": str(self.workspace_root),
            "workspace_name": self.workspace_root.name,
            "model": Path(self.model_name).name if self.model_name else "None",
            "models": models_info,
            "effort": self.agent.effort_level,
            "safety_mode": self.fs_tools.safety_mode,
            "language": self.agent.language,
            "ctx": self.agent.ctx_size,
            "llama_port": self.llama_port,
            "server_healthy": self.server_mgr.is_healthy(),
            "usage": self.agent.last_usage,
            "sessions": sessions_list,
            "active_session_id": active_sess.get("id") if active_sess else None,
            "version": app_version.get_current_version() if app_version else "0.3.0",
        }


def make_handler(state: WebUIBackendState):
    static_dir = _THIS_DIR / "static"

    class WebUIRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = 15

        def log_message(self, format: str, *args: Any) -> None:
            # Suppress noisy HTTP request logging in CLI console
            return

        def _send_json(self, payload: Any, status: int = 200):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 10 * 1024 * 1024:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/" or path == "/index.html":
                index_file = static_dir / "index.html"
                if not index_file.exists():
                    self._send_json({"error": "WebUI frontend not found"}, 404)
                    return
                content = index_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            if path == "/api/state":
                self._send_json(state.get_state_payload())
                return

            if path == "/api/commands":
                self._send_json({"commands": state.get_slash_commands_payload()})
                return

            if path == "/api/workspace/files":
                self._send_json({"files": state.fs_tools.list_mentionable_files()})
                return

            if path == "/api/session/messages":
                active_sess = state.session_mgr.get_active_session()
                msgs = active_sess.get("messages", []) if active_sess else []
                self._send_json({"messages": msgs, "session": active_sess})
                return

            if path == "/api/events":
                job_id = (qs.get("job_id") or [""])[0]
                after = int((qs.get("after") or ["0"])[0])
                with state.jobs_lock:
                    job = state.jobs.get(job_id)
                    if not job:
                        self._send_json({"error": "Job not found"}, 404)
                        return
                    evts = job["events"][after:]
                    done = job["done"]
                self._send_json({"events": evts, "next_index": after + len(evts), "done": done})
                return

            if path == "/api/files":
                rel_dir = (qs.get("path") or [""])[0].strip()
                target_dir = (state.workspace_root / rel_dir).resolve() if rel_dir else state.workspace_root
                try:
                    target_dir.relative_to(state.workspace_root)
                except ValueError:
                    self._send_json({"error": "Access denied outside workspace"}, 403)
                    return

                if not target_dir.exists() or not target_dir.is_dir():
                    self._send_json({"error": "Directory not found"}, 404)
                    return

                entries = []
                try:
                    for item in sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                        if item.name in SKIP_DIRS:
                            continue
                        if is_sensitive_path(item, state.workspace_root):
                            continue
                        rel_item = str(item.relative_to(state.workspace_root)).replace("\\", "/")
                        entries.append(
                            {
                                "name": item.name,
                                "path": rel_item,
                                "is_dir": item.is_dir(),
                                "size": 0 if item.is_dir() else item.stat().st_size,
                            }
                        )
                except Exception as exc:
                    self._send_json({"error": str(exc)}, 500)
                    return

                self._send_json({"path": rel_dir, "entries": entries})
                return

            if path == "/api/file":
                rel_file = (qs.get("path") or [""])[0].strip()
                if not rel_file:
                    self._send_json({"error": "Missing file path"}, 400)
                    return
                target_file = (state.workspace_root / rel_file).resolve()
                if is_sensitive_path(target_file, state.workspace_root):
                    self._send_json({"error": "Access to sensitive/credential files is blocked"}, 403)
                    return
                if not target_file.exists() or not target_file.is_file():
                    self._send_json({"error": "File not found"}, 404)
                    return
                if target_file.stat().st_size > 1024 * 1024:
                    self._send_json({"error": "File too large to open in inline editor (>1 MB)"}, 413)
                    return
                try:
                    content = target_file.read_text(encoding="utf-8", errors="replace")
                    self._send_json({"path": rel_file.replace("\\", "/"), "content": content})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, 500)
                return

            self._send_json({"error": "Not found"}, 404)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            try:
                body = self._read_json_body()
            except Exception:
                self._send_json({"error": "Invalid JSON body"}, 400)
                return

            if path == "/api/chat":
                prompt = str(body.get("prompt", "")).strip()
                if not prompt:
                    self._send_json({"error": "Prompt cannot be empty"}, 400)
                    return
                job_id = state.start_chat_job(prompt)
                self._send_json({"job_id": job_id})
                return

            if path in ("/api/cancel", "/api/chat/cancel"):
                jid = body.get("job_id")
                ok = state.cancel_active_job(str(jid) if jid else None)
                self._send_json({"ok": ok})
                return

            if path == "/api/chat/cancel":
                state.cancel_active_job()
                self._send_json({"ok": True})
                return

            if path == "/api/approve":
                app_id = str(body.get("approval_id", ""))
                approved = bool(body.get("approved", False))
                ok = state.resolve_approval(app_id, approved)
                self._send_json({"ok": ok})
                return

            if path == "/api/file":
                rel_file = str(body.get("path", "")).strip()
                content = body.get("content", "")
                if not rel_file:
                    self._send_json({"error": "Missing file path"}, 400)
                    return
                target_file = (state.workspace_root / rel_file).resolve()
                if is_sensitive_path(target_file, state.workspace_root):
                    self._send_json({"error": "Writing to sensitive/credential files is blocked"}, 403)
                    return
                try:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_text(str(content), encoding="utf-8")
                    self._send_json({"ok": True, "path": rel_file.replace("\\", "/")})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, 500)
                return

            if path == "/api/settings":
                if "safety_mode" in body:
                    mode = str(body["safety_mode"]).lower()
                    if mode in ("strict", "auto-approve", "yolo"):
                        state.fs_tools.set_safety_mode(mode)
                        state.safety_mode = mode

                if "effort" in body:
                    eff = str(body["effort"]).lower()
                    if eff in ("off", "low", "medium", "high"):
                        config.set_active_effort(eff)
                        state.agent.set_effort(eff)
                        state.effort = eff

                if "language" in body:
                    lang = str(body["language"]).lower()
                    ok, _ = config.set_active_language(lang)
                    if ok:
                        state.agent.set_language(lang)
                        state.language = lang

                if "model" in body:
                    new_model = str(body["model"]).strip()
                    if new_model:
                        state.model_name = new_model
                        state.agent.model_name = Path(new_model).name
                        try:
                            state.server_mgr.start(new_model)
                        except Exception as exc:
                            self._send_json({"error": f"Failed to switch model: {exc}"}, 500)
                            return

                if body.get("action") == "new_session":
                    title = str(body.get("title", "")).strip() or None
                    sess = state.session_mgr.create_session(name=title)
                    state.loaded_session_id = sess.get("id")
                    state.agent.reset_session()
                    self._send_json({"ok": True, "session": sess, "state": state.get_state_payload()})
                    return

                if body.get("action") == "switch_session":
                    sid = str(body.get("session_id", "")).strip()
                    ok, msg, s_data = state.session_mgr.switch_session(sid)
                    if ok and s_data:
                        state.loaded_session_id = sid
                        state.agent.load_session(s_data)
                        self._send_json({"ok": True, "session": s_data, "state": state.get_state_payload()})
                    else:
                        self._send_json({"error": msg}, 400)
                    return

                self._send_json({"ok": True, "state": state.get_state_payload()})
                return

            if path == "/api/shutdown":
                if self.client_address[0] == "127.0.0.1":
                    self._send_json({"ok": True})
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return
                self._send_json({"error": "Forbidden"}, 403)
                return

            self._send_json({"error": "Not found"}, 404)

    return WebUIRequestHandler


class _LeanWebUIHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


_ACTIVE_SERVER: Optional[ThreadingHTTPServer] = None


def _get_webui_pid_file() -> Path:
    import tempfile
    return Path(tempfile.gettempdir()) / "lensetek-webui.pid"


def _cleanup_hung_webui_pid():
    """If an older Lensetek WebUI process is hung on the port, terminate it via its recorded PID."""
    pid_file = _get_webui_pid_file()
    if not pid_file.exists():
        return
    try:
        old_pid = int(pid_file.read_text(encoding="utf-8").strip())
    except Exception:
        return
    if old_pid <= 0 or old_pid == os.getpid():
        return
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
        else:
            import signal
            os.kill(old_pid, signal.SIGTERM)
        time.sleep(0.3)
    except Exception:
        pass


def start_webui_server(
    workspace: Path | str = ".",
    llama_port: int = 8081,
    web_port: int = 3001,
    model_name: Optional[str] = None,
    server_mgr: Optional[LlamaServerManager] = None,
    agent: Optional[LeanAgent] = None,
) -> ThreadingHTTPServer:
    """Start the Lensetek Agent WebUI server in a background daemon thread."""
    global _ACTIVE_SERVER
    if _ACTIVE_SERVER is not None:
        return _ACTIVE_SERVER

    state = WebUIBackendState(
        workspace=Path(workspace),
        llama_port=llama_port,
        model_name=model_name,
        server_mgr=server_mgr,
        agent=agent,
    )
    handler_cls = make_handler(state)

    # If an older Lensetek WebUI instance is squatting on web_port, gracefully replace it
    replaced = False
    try:
        import urllib.request
        chk = urllib.request.urlopen(f"http://127.0.0.1:{web_port}/api/state", timeout=0.8)
        st_json = json.loads(chk.read().decode("utf-8"))
        if "workspace" in st_json and "safety_mode" in st_json:
            req_sd = urllib.request.Request(
                f"http://127.0.0.1:{web_port}/api/shutdown",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req_sd, timeout=0.8)
            time.sleep(0.4)
            replaced = True
    except Exception:
        pass

    if not replaced:
        _cleanup_hung_webui_pid()

    httpd: Optional[ThreadingHTTPServer] = None
    last_err: Optional[OSError] = None
    for candidate_port in range(web_port, web_port + 21):
        try:
            httpd = _LeanWebUIHTTPServer(("127.0.0.1", candidate_port), handler_cls)
            break
        except OSError as exc:
            last_err = exc
    if httpd is None:
        raise last_err or OSError(f"Unable to bind WebUI server on ports {web_port}-{web_port + 20}")
    _ACTIVE_SERVER = httpd

    pid_file = _get_webui_pid_file()
    try:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
        import atexit
        def _remove_pid():
            try:
                if pid_file.exists() and pid_file.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    pid_file.unlink()
            except Exception:
                pass
        atexit.register(_remove_pid)
    except Exception:
        pass

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd
