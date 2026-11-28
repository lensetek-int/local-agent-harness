"""
Lensetek Agent WebUI Server
Serves the modern Antigravity/Codex-style responsive Web IDE & Agent Interface
and bridges it directly to LeanAgent, LocalWorkspaceTools, SessionManager, and llama-server.
Strictly binds to 127.0.0.1 and blocks credential/secret file access.
"""

from __future__ import annotations

import base64
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
for _p in (_HOME_CLI, _REPO_CLI):
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
    import hf_hub
except ImportError:
    hf_hub = None

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


def _open_path_in_os_explorer(target_path: Path) -> Path:
    """Open the containing folder in OS File Explorer, selecting the file when applicable."""
    import subprocess
    p_resolved = target_path.resolve()
    folder_path = p_resolved.parent if p_resolved.is_file() else p_resolved
    if sys.platform == "win32":
        if p_resolved.is_file():
            subprocess.Popen(["explorer", "/select,", str(p_resolved)])
        else:
            os.startfile(str(folder_path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p_resolved)] if p_resolved.is_file() else ["open", str(folder_path)])
    else:
        subprocess.Popen(["xdg-open", str(folder_path)])
    return folder_path


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
        self.download_jobs: Dict[str, Dict[str, Any]] = {}
        self.download_lock = threading.Lock()
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
            active_sess = self.session_mgr.get_active_session(workspace=str(self.workspace_root))
            self.loaded_session_id = active_sess.get("id") if active_sess else None
            if active_sess:
                self.agent.load_session(active_sess)
        if not hasattr(self, "loaded_session_id"):
            active_sess = self.session_mgr.get_active_session(workspace=str(self.workspace_root))
            self.loaded_session_id = active_sess.get("id") if active_sess else None
        self._register_project(self.workspace_root)

    @staticmethod
    def _is_blocked_project_dir(target: Path) -> bool:
        """Block sensitive system or credential directories from being opened as workspaces."""
        low = str(target.resolve()).lower()
        blocked_parts = ("\\.ssh", "/.ssh", "\\.gnupg", "/.gnupg", "\\.git", "/.git")
        if any(bp in low for bp in blocked_parts):
            return True
        sys_roots = ("c:\\windows", "c:\\program files", "/etc", "/root", "/bin", "/sbin", "/usr")
        if any(low == sr or low.startswith(sr + "\\") or low.startswith(sr + "/") for sr in sys_roots):
            return True
        return False

    def _register_project(self, project_path: Path):
        """Record a project directory into user_settings.json recent_projects."""
        try:
            resolved = str(project_path.resolve())
            st = config.load_user_settings()
            projects = st.get("recent_projects", [])
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
            norm_res = resolved.lower() if sys.platform == "win32" else resolved
            filtered = [
                p for p in projects
                if (p.get("path", "").lower() if sys.platform == "win32" else p.get("path", "")) != norm_res
            ]
            filtered.insert(0, {
                "name": project_path.resolve().name or resolved,
                "path": resolved,
                "last_opened": now_iso,
            })
            st["recent_projects"] = filtered[:25]
            config.save_user_settings(st)
        except Exception:
            pass

    def list_projects(self) -> List[Dict[str, Any]]:
        st = config.load_user_settings()
        projects = st.get("recent_projects", [])
        active_str = str(self.workspace_root.resolve())
        norm_active = active_str.lower() if sys.platform == "win32" else active_str
        out = []
        seen = set()
        for p in projects:
            raw_p = p.get("path", "")
            if not raw_p:
                continue
            norm_p = raw_p.lower() if sys.platform == "win32" else raw_p
            if norm_p in seen:
                continue
            seen.add(norm_p)
            p_obj = Path(raw_p)
            out.append({
                "name": p.get("name") or p_obj.name or raw_p,
                "path": raw_p,
                "last_opened": p.get("last_opened", ""),
                "exists": p_obj.exists() and p_obj.is_dir(),
                "is_active": norm_p == norm_active,
            })
        if norm_active not in seen:
            out.insert(0, {
                "name": self.workspace_root.name or active_str,
                "path": active_str,
                "last_opened": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "exists": True,
                "is_active": True,
            })
        return out

    def switch_project(self, raw_path: str, create_if_missing: bool = False) -> tuple[bool, str]:
        """Switch active workspace_root dynamically without restarting llama-server."""
        clean = raw_path.strip().strip("'\"")
        if not clean:
            return False, "Project path cannot be empty."
        target = Path(clean).expanduser().resolve()
        if self._is_blocked_project_dir(target):
            return False, "Access to system or credential directories is blocked."
        if not target.exists():
            if create_if_missing:
                try:
                    target.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    return False, f"Failed to create directory: {exc}"
            else:
                return False, f"Directory not found: {target}"
        if not target.is_dir():
            return False, f"Not a directory: {target}"

        with self.agent_lock:
            self.workspace_root = target
            self.fs_tools = LocalWorkspaceTools(
                workspace_root=str(self.workspace_root),
                confirm_fn=self._web_confirm,
                safety_mode=self.safety_mode,
            )
            self.skills_mgr = SkillManager(
                local_skills_dir=config.CLI_DIR / "skills",
                workspace_root=self.workspace_root,
                safety_mode=self.safety_mode,
            )
            self.agent.fs_tools = self.fs_tools
            self.agent.skills_manager = self.skills_mgr
            active_sess = self.session_mgr.get_active_session(workspace=str(self.workspace_root))
            self.loaded_session_id = active_sess.get("id") if active_sess else None
            if active_sess:
                self.agent.load_session(active_sess)
            self._register_project(self.workspace_root)
        return True, f"Switched project to {self.workspace_root.name}"

    def remove_project(self, raw_path: str) -> bool:
        clean = raw_path.strip()
        if not clean:
            return False
        norm_target = str(Path(clean).resolve()).lower() if sys.platform == "win32" else str(Path(clean).resolve())
        st = config.load_user_settings()
        projects = st.get("recent_projects", [])
        new_list = [
            p for p in projects
            if (p.get("path", "").lower() if sys.platform == "win32" else p.get("path", "")) != norm_target
        ]
        st["recent_projects"] = new_list
        config.save_user_settings(st)
        return len(new_list) != len(projects)

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
                    cur_sid = self.session_mgr.get_active_session_id(workspace=str(self.workspace_root))
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
                            self.server_mgr.start(self.model_name, loras=config.get_active_loras())
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

    def _spawn_hf_download_worker(self, job_id: str):
        with self.download_lock:
            job = self.download_jobs.get(job_id)
            if not job:
                return
            url = job["url"]
            out_file = Path(job["out_file"])
            safe_name = job["filename"]
            auto_switch = bool(job.get("auto_switch", True))
            cancel_evt = job["cancel_event"]

        def _on_progress(done_bytes: int, total_bytes: int):
            with self.download_lock:
                j = self.download_jobs.get(job_id)
                if not j or j.get("status") != "downloading":
                    return
                if total_bytes > 0:
                    j["total_mb"] = round(total_bytes / (1024 * 1024), 1)
                    j["downloaded_mb"] = round(done_bytes / (1024 * 1024), 1)
                    j["progress_pct"] = round((done_bytes / total_bytes) * 100, 1)

        def _dl_worker():
            try:
                ok, msg, final_path = hf_hub.download_file_parallel(
                    url,
                    out_file,
                    cancel_event=cancel_evt,
                    progress_cb=_on_progress,
                )
                with self.download_lock:
                    j = self.download_jobs.get(job_id)
                    if not j:
                        return
                    intent = j.get("action_intent")
                    if ok and final_path:
                        j["status"] = "done"
                        j["progress_pct"] = 100.0
                        if final_path.exists():
                            sz_mb = round(final_path.stat().st_size / (1024 * 1024), 1)
                            j["downloaded_mb"] = sz_mb
                            j["total_mb"] = sz_mb
                        j["message"] = f"Downloaded {safe_name} successfully."
                        if auto_switch:
                            self.model_name = str(final_path)
                            self.agent.model_name = final_path.name
                    elif intent == "pause":
                        j["status"] = "paused"
                        j["message"] = f"Paused {safe_name} ({j.get('progress_pct', 0)}%)"
                    elif intent == "cancel":
                        j["status"] = "cancelled"
                        j["message"] = f"Cancelled {safe_name}."
                        for tmp_f in (
                            out_file.parent / f"{out_file.name}.part",
                            out_file.parent / f"{out_file.name}.part.meta.json",
                        ):
                            try:
                                if tmp_f.exists():
                                    tmp_f.unlink()
                            except Exception:
                                pass
                    else:
                        j["status"] = "error"
                        j["message"] = msg or "Download failed."
            except Exception as exc:
                with self.download_lock:
                    j = self.download_jobs.get(job_id)
                    if j:
                        if j.get("action_intent") == "pause":
                            j["status"] = "paused"
                        elif j.get("action_intent") == "cancel":
                            j["status"] = "cancelled"
                        else:
                            j["status"] = "error"
                            j["message"] = str(exc)

        threading.Thread(target=_dl_worker, daemon=True).start()

    def start_hf_download(self, repo_id: str, filename: str, auto_switch: bool = True) -> str:
        """Start an asynchronous GGUF download from Hugging Face into REPO_ROOT/models/."""
        if hf_hub is None:
            raise RuntimeError("hf_hub module is not available.")

        clean_repo = repo_id.strip()
        clean_file = filename.strip().lstrip("/")
        safe_name = Path(clean_file).name
        if not safe_name.lower().endswith(".gguf"):
            raise ValueError("Only .gguf model files are supported.")

        models_dir = config.REPO_ROOT / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        out_file = models_dir / safe_name
        url = f"https://huggingface.co/{clean_repo}/resolve/main/{urllib.parse.quote(clean_file)}"

        job_id = "dl_" + uuid.uuid4().hex[:10]
        with self.download_lock:
            for existing_id, existing_job in self.download_jobs.items():
                if existing_job.get("filename") == safe_name and existing_job.get("status") in ("downloading", "paused"):
                    return existing_id
            self.download_jobs[job_id] = {
                "job_id": job_id,
                "repo_id": clean_repo,
                "filename": safe_name,
                "url": url,
                "out_file": str(out_file),
                "auto_switch": auto_switch,
                "cancel_event": threading.Event(),
                "action_intent": None,
                "status": "downloading",
                "progress_pct": 0.0,
                "downloaded_mb": 0.0,
                "total_mb": 0.0,
                "message": f"Downloading {safe_name}...",
            }

        self._spawn_hf_download_worker(job_id)
        return job_id

    def pause_hf_download(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.download_lock:
            job = self.download_jobs.get(job_id)
            if not job:
                return None
            if job["status"] == "downloading":
                job["action_intent"] = "pause"
                job["status"] = "paused"
                job["message"] = f"Paused {job['filename']} ({job.get('progress_pct', 0)}%)"
                job["cancel_event"].set()
        return self.get_hf_download_status(job_id)

    def resume_hf_download(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.download_lock:
            job = self.download_jobs.get(job_id)
            if not job:
                return None
            if job["status"] in ("paused", "error"):
                job["action_intent"] = None
                job["cancel_event"] = threading.Event()
                job["status"] = "downloading"
                job["message"] = f"Resuming {job['filename']}..."
                should_spawn = True
            else:
                should_spawn = False
        if should_spawn:
            self._spawn_hf_download_worker(job_id)
        return self.get_hf_download_status(job_id)

    def cancel_hf_download(self, job_id: str) -> Optional[Dict[str, Any]]:
        out_file = None
        with self.download_lock:
            job = self.download_jobs.get(job_id)
            if not job:
                return None
            job["action_intent"] = "cancel"
            job["status"] = "cancelled"
            job["message"] = f"Cancelled {job['filename']}."
            job["cancel_event"].set()
            out_file = Path(job["out_file"])
        if out_file:
            for tmp_f in (
                out_file.parent / f"{out_file.name}.part",
                out_file.parent / f"{out_file.name}.part.meta.json",
            ):
                try:
                    if tmp_f.exists():
                        tmp_f.unlink()
                except Exception:
                    pass
        return self.get_hf_download_status(job_id)

    def get_hf_download_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self.download_lock:
            job = self.download_jobs.get(job_id)
            if not job:
                return None
            res = {k: v for k, v in job.items() if k not in ("cancel_event", "url", "action_intent")}
        return res

    def _resolve_installed_plugin_dir(self, plugin_id: str) -> Optional[Path]:
        if not plugin_manager or not plugin_id or "/" in plugin_id or "\\" in plugin_id or ".." in plugin_id:
            return None
        if plugin_id not in set(plugin_manager.list_installed_plugin_ids()):
            return None
        for d in (plugin_manager.get_plugins_dir() / plugin_id, config.REPO_ROOT / "plugins" / plugin_id):
            if d.exists() and d.is_dir():
                return d
        return None

    def get_installed_plugin_panels(self) -> List[Dict[str, Any]]:
        if not plugin_manager:
            return []
        panels = []
        for pid in plugin_manager.list_installed_plugin_ids():
            p_dir = self._resolve_installed_plugin_dir(pid)
            if not p_dir:
                continue
            meta_file = p_dir / "plugin.json"
            if not meta_file.exists():
                continue
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                ui_cfg = meta.get("ui")
                if isinstance(ui_cfg, dict) and ui_cfg.get("entry"):
                    entry = str(ui_cfg["entry"]).lstrip("/")
                    panels.append({
                        "id": pid,
                        "title": ui_cfg.get("title", meta.get("name", pid)),
                        "icon": ui_cfg.get("icon", "🧩"),
                        "url": f"/plugin-ui/{pid}/{entry}",
                    })
            except Exception:
                continue
        return panels

    def dispatch_plugin_api(self, plugin_id: str, method: str, sub_path: str, qs: Dict[str, Any], body: Dict[str, Any]) -> tuple[int, Dict[str, Any]]:
        import importlib.util
        p_dir = self._resolve_installed_plugin_dir(plugin_id)
        if not p_dir:
            return 404, {"error": f"Installed plugin '{plugin_id}' not found."}
        api_file = p_dir / "server_api.py"
        if not api_file.exists():
            return 404, {"error": f"Plugin '{plugin_id}' has no server_api.py"}
        try:
            mod_name = f"lensetek_plugin_api_{plugin_id.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(mod_name, str(api_file))
            if not spec or not spec.loader:
                return 500, {"error": "Unable to load plugin API module."}
            mod = sys.modules.get(mod_name)
            if mod is None:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
            if not hasattr(mod, "handle_request"):
                return 500, {"error": "server_api.py missing handle_request()"}
            return mod.handle_request(method=method, sub_path=sub_path, query=qs, body=body, state=self)
        except Exception as exc:
            return 500, {"error": f"Plugin API error: {exc}"}

    def get_state_payload(self) -> Dict[str, Any]:
        models_raw = config.list_gguf_models()
        models_info = []
        for m in models_raw:
            p = Path(m)
            resolved = config.resolve_model_file(m)
            if resolved and resolved.exists():
                p = resolved
            elif not p.is_absolute() and (config.REPO_ROOT / p).exists():
                p = (config.REPO_ROOT / p).resolve()
            sz_mb = round(p.stat().st_size / (1024 * 1024), 1) if p.exists() else 0
            models_info.append({"name": p.name, "path": str(p), "size_mb": sz_mb})

        sessions_list = self.session_mgr.list_sessions(workspace=str(self.workspace_root))
        active_sess = self.session_mgr.get_active_session(workspace=str(self.workspace_root))

        return {
            "workspace": str(self.workspace_root),
            "workspace_name": self.workspace_root.name,
            "model": Path(self.model_name).name if self.model_name else "None",
            "models": models_info,
            "loras": config.list_lora_adapters(),
            "active_loras": config.get_active_loras(),
            "plugin_panels": self.get_installed_plugin_panels(),
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
            if length <= 0 or length > 75 * 1024 * 1024:
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

            if path == "/api/plugins":
                if plugin_manager is None:
                    self._send_json({"plugins": [], "error": "plugin_manager unavailable"})
                    return
                q = (qs.get("q") or [""])[0].strip().lower()
                force_refresh = (qs.get("refresh") or ["0"])[0] in ("1", "true", "yes")
                all_p = plugin_manager.get_all_catalog_plugins(force_remote=force_refresh)
                if q:
                    all_p = [
                        p for p in all_p
                        if q in p.get("id", "").lower()
                        or q in p.get("name", "").lower()
                        or q in p.get("category", "").lower()
                        or q in p.get(f"description_{state.language}", p.get("description", "")).lower()
                    ]
                self._send_json({"plugins": all_p, "language": state.language})
                return

            if path == "/api/plugins/ui":
                self._send_json({"panels": state.get_installed_plugin_panels()})
                return

            if path.startswith("/plugin-ui/"):
                parts = path[len("/plugin-ui/"):].split("/", 1)
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    self._send_json({"error": "Invalid plugin UI path"}, 400)
                    return
                pid, rel_f = parts[0], parts[1]
                p_dir = state._resolve_installed_plugin_dir(pid)
                if not p_dir:
                    self._send_json({"error": "Plugin not installed"}, 404)
                    return
                ui_root = (p_dir / "ui").resolve()
                target_f = (p_dir / rel_f).resolve()
                try:
                    target_f.relative_to(ui_root)
                except ValueError:
                    self._send_json({"error": "Forbidden"}, 403)
                    return
                if not target_f.exists() or not target_f.is_file():
                    self._send_json({"error": "Plugin UI file not found"}, 404)
                    return
                ctype, _ = mimetypes.guess_type(str(target_f))
                content = target_f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", f"{ctype or 'text/html'}; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                return

            if path.startswith("/api/plugin/"):
                rest = path[len("/api/plugin/"):]
                parts = rest.split("/", 1)
                pid = parts[0]
                sub_p = parts[1] if len(parts) > 1 else ""
                code, payload = state.dispatch_plugin_api(pid, "GET", sub_p, qs, {})
                self._send_json(payload, status=code)
                return

            if path == "/api/models/hf/search":
                if hf_hub is None:
                    self._send_json({"results": [], "error": "hf_hub unavailable"}, 500)
                    return
                q = (qs.get("q") or [""])[0].strip()
                if not q:
                    self._send_json({"results": []})
                    return
                results = hf_hub.search_hf_gguf_models(q, limit=12, fetch_sizes=True)
                self._send_json({"results": results})
                return

            if path == "/api/models/hf/files":
                if hf_hub is None:
                    self._send_json({"files": [], "error": "hf_hub unavailable"}, 500)
                    return
                repo = (qs.get("repo") or [""])[0].strip()
                if not repo:
                    self._send_json({"error": "Missing repo parameter"}, 400)
                    return
                files = hf_hub.list_hf_gguf_files(repo)
                self._send_json({"repo": repo, "files": files})
                return

            if path == "/api/models/hf/download_status":
                jid = (qs.get("job_id") or [""])[0].strip()
                st_job = state.get_hf_download_status(jid)
                if not st_job:
                    self._send_json({"error": "Download job not found"}, 404)
                    return
                if st_job.get("status") == "done":
                    st_job["state"] = state.get_state_payload()
                self._send_json(st_job)
                return

            if path == "/api/projects":
                self._send_json({
                    "projects": state.list_projects(),
                    "active_workspace": str(state.workspace_root),
                })
                return

            if path == "/api/session/messages":
                active_sess = state.session_mgr.get_active_session(workspace=str(state.workspace_root))
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

            if path == "/api/workspace/upload":
                filename = str(body.get("filename", "")).strip()
                content_b64 = str(body.get("content_base64", "")).strip()
                target_dir_rel = str(body.get("target_dir", "")).strip()
                if not filename or not content_b64:
                    self._send_json({"error": "Missing filename or file content"}, 400)
                    return
                safe_name = Path(filename).name
                if not safe_name or safe_name in (".", ".."):
                    self._send_json({"error": "Invalid filename"}, 400)
                    return
                dest_dir = (state.workspace_root / target_dir_rel).resolve() if target_dir_rel else state.workspace_root
                try:
                    dest_dir.relative_to(state.workspace_root)
                except ValueError:
                    self._send_json({"error": "Target directory outside workspace"}, 403)
                    return
                dest_file = (dest_dir / safe_name).resolve()
                if is_sensitive_path(dest_file, state.workspace_root):
                    self._send_json({"error": "Uploading sensitive/credential files is blocked"}, 403)
                    return
                try:
                    raw_bytes = base64.b64decode(content_b64)
                    if len(raw_bytes) > 50 * 1024 * 1024:
                        self._send_json({"error": "File exceeds 50 MB limit"}, 413)
                        return
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_file.write_bytes(raw_bytes)
                    rel_item = str(dest_file.relative_to(state.workspace_root)).replace("\\", "/")
                    self._send_json({
                        "ok": True,
                        "name": safe_name,
                        "path": rel_item,
                        "size": len(raw_bytes),
                    })
                except Exception as exc:
                    self._send_json({"error": f"Upload failed: {exc}"}, 500)
                return

            if path == "/api/plugins/install":
                if plugin_manager is None:
                    self._send_json({"error": "plugin_manager unavailable"}, 500)
                    return
                pid = str(body.get("plugin_id", "")).strip()
                if not pid:
                    self._send_json({"error": "Missing plugin_id"}, 400)
                    return
                ok, msg = plugin_manager.install_plugin(pid, lang=state.language)
                self._send_json({
                    "ok": ok,
                    "message": msg,
                    "plugins": plugin_manager.get_all_catalog_plugins(),
                })
                return

            if path == "/api/plugins/uninstall":
                if plugin_manager is None:
                    self._send_json({"error": "plugin_manager unavailable"}, 500)
                    return
                pid = str(body.get("plugin_id", "")).strip()
                if not pid:
                    self._send_json({"error": "Missing plugin_id"}, 400)
                    return
                ok, msg = plugin_manager.uninstall_plugin(pid, lang=state.language)
                self._send_json({
                    "ok": ok,
                    "message": msg,
                    "plugins": plugin_manager.get_all_catalog_plugins(),
                })
                return

            if path == "/api/plugins/open_folder":
                if self.client_address[0] != "127.0.0.1":
                    self._send_json({"error": "Forbidden"}, 403)
                    return
                if plugin_manager is None:
                    self._send_json({"error": "plugin_manager unavailable"}, 500)
                    return
                pid = str(body.get("plugin_id", "")).strip()
                if not pid or "/" in pid or "\\" in pid or ".." in pid:
                    self._send_json({"error": "Invalid plugin_id"}, 400)
                    return
                cand_dirs = [
                    plugin_manager.get_plugins_dir() / pid,
                    config.REPO_ROOT / "plugins" / pid,
                ]
                target_dir = next((d for d in cand_dirs if d.exists() and d.is_dir()), None)
                if not target_dir:
                    self._send_json({"error": f"Plugin folder '{pid}' not found on disk."}, 404)
                    return
                try:
                    folder_path = _open_path_in_os_explorer(target_dir)
                    self._send_json({"ok": True, "folder": str(folder_path)})
                except Exception as exc:
                    self._send_json({"error": f"Failed to open plugin folder: {exc}"}, 500)
                return

            if path == "/api/models/hf/download":
                repo_id = str(body.get("repo_id", "")).strip()
                filename = str(body.get("filename", "")).strip()
                auto_switch = bool(body.get("auto_switch", True))
                if not repo_id or not filename:
                    self._send_json({"error": "Missing repo_id or filename"}, 400)
                    return
                try:
                    jid = state.start_hf_download(repo_id, filename, auto_switch=auto_switch)
                    self._send_json({"ok": True, "job_id": jid})
                except Exception as exc:
                    self._send_json({"error": str(exc)}, 400)
                return

            if path == "/api/models/hf/pause":
                jid = str(body.get("job_id", "")).strip()
                res = state.pause_hf_download(jid)
                if not res:
                    self._send_json({"error": "Download job not found"}, 404)
                    return
                self._send_json({"ok": True, "job": res})
                return

            if path == "/api/models/hf/resume":
                jid = str(body.get("job_id", "")).strip()
                res = state.resume_hf_download(jid)
                if not res:
                    self._send_json({"error": "Download job not found"}, 404)
                    return
                self._send_json({"ok": True, "job": res})
                return

            if path == "/api/models/hf/cancel":
                jid = str(body.get("job_id", "")).strip()
                res = state.cancel_hf_download(jid)
                if not res:
                    self._send_json({"error": "Download job not found"}, 404)
                    return
                self._send_json({"ok": True, "job": res})
                return

            if path == "/api/models/add":
                path_str = str(body.get("path", "")).strip()
                if not path_str:
                    self._send_json({"error": "Missing model path"}, 400)
                    return
                ok, msg, p_obj = config.add_custom_model_path(path_str, lang=state.language)
                if ok and p_obj and p_obj.is_file() and body.get("auto_switch"):
                    state.model_name = str(p_obj)
                    state.agent.model_name = p_obj.name
                self._send_json({"ok": ok, "message": msg, "state": state.get_state_payload()})
                return

            if path == "/api/workspace/open_explorer":
                if self.client_address[0] != "127.0.0.1":
                    self._send_json({"error": "Forbidden"}, 403)
                    return
                rel_path = str(body.get("path", "")).strip()
                target = (state.workspace_root / rel_path).resolve() if rel_path else state.workspace_root.resolve()
                try:
                    target.relative_to(state.workspace_root.resolve())
                except ValueError:
                    self._send_json({"error": "Access denied outside workspace"}, 403)
                    return
                if rel_path and is_sensitive_path(target, state.workspace_root):
                    self._send_json({"error": "Access to sensitive/credential paths is blocked"}, 403)
                    return
                if not target.exists():
                    self._send_json({"error": "Path not found"}, 404)
                    return
                try:
                    folder_path = _open_path_in_os_explorer(target)
                    self._send_json({"ok": True, "folder": str(folder_path)})
                except Exception as exc:
                    self._send_json({"error": f"Failed to open Explorer: {exc}"}, 500)
                return

            if path == "/api/models/open_folder":
                if self.client_address[0] != "127.0.0.1":
                    self._send_json({"error": "Forbidden"}, 403)
                    return
                target_path = str(body.get("path", "")).strip()
                if not target_path:
                    self._send_json({"error": "Missing model path"}, 400)
                    return
                p = Path(target_path)
                if not p.is_absolute():
                    cand_models = config.REPO_ROOT / "models" / target_path
                    cand_root = config.REPO_ROOT / target_path
                    p = cand_models if cand_models.exists() else cand_root
                p_resolved = p.resolve()
                if not p_resolved.exists():
                    self._send_json({"error": "Model path not found"}, 404)
                    return
                if p_resolved.is_file() and p_resolved.suffix.lower() != ".gguf":
                    self._send_json({"error": "Only .gguf model paths are allowed"}, 403)
                    return
                try:
                    folder_path = _open_path_in_os_explorer(p_resolved)
                    self._send_json({"ok": True, "folder": str(folder_path)})
                except Exception as exc:
                    self._send_json({"error": f"Failed to open folder: {exc}"}, 500)
                return

            if path == "/api/models/delete":
                target_path = str(body.get("path", "")).strip()
                if not target_path:
                    self._send_json({"error": "Missing model path"}, 400)
                    return
                p = Path(target_path)
                if not p.is_absolute():
                    cand_models = config.REPO_ROOT / "models" / target_path
                    cand_root = config.REPO_ROOT / target_path
                    p = cand_models if cand_models.exists() else cand_root
                p_resolved = p.resolve()

                removed_from_custom = False
                st_cfg = config.load_user_settings()
                custom_list = st_cfg.get("custom_models", [])
                new_custom = [c for c in custom_list if Path(c).resolve() != p_resolved]
                if len(new_custom) != len(custom_list):
                    st_cfg["custom_models"] = new_custom
                    config.save_user_settings(st_cfg)
                    removed_from_custom = True

                deleted_file = False
                repo_root_res = config.REPO_ROOT.resolve()
                is_in_repo = False
                try:
                    p_resolved.relative_to(repo_root_res)
                    is_in_repo = True
                except ValueError:
                    is_in_repo = False

                if is_in_repo and p_resolved.exists() and p_resolved.is_file() and p_resolved.suffix.lower() == ".gguf":
                    try:
                        if state.model_name and Path(state.model_name).resolve() == p_resolved:
                            if state.server_mgr.is_healthy():
                                state.server_mgr.stop()
                        p_resolved.unlink()
                        deleted_file = True
                    except Exception as exc:
                        self._send_json({"error": f"Failed to delete model file: {exc}"}, 500)
                        return

                if not deleted_file and not removed_from_custom:
                    self._send_json({"error": "Model file not found or cannot be deleted outside workspace."}, 404)
                    return

                if state.model_name and (Path(state.model_name).name == p_resolved.name):
                    next_model = config.pick_default_model()
                    state.model_name = next_model
                    state.agent.model_name = Path(next_model).name if next_model else "None"

                msg = f"Removed model '{p_resolved.name}'."
                self._send_json({"ok": True, "message": msg, "state": state.get_state_payload()})
                return

            if path == "/api/projects/browse":
                if self.client_address[0] != "127.0.0.1":
                    self._send_json({"error": "Forbidden"}, 403)
                    return
                try:
                    import subprocess
                    init_dir = str(state.workspace_root)
                    py_code = (
                        "import tkinter as tk, tkinter.filedialog as fd; "
                        "r=tk.Tk(); r.withdraw(); r.attributes('-topmost', True); "
                        f"p=fd.askdirectory(initialdir={init_dir!r}, title='Select Project Folder'); "
                        "print(p or '')"
                    )
                    res = subprocess.run(
                        [sys.executable, "-c", py_code],
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    chosen = (res.stdout or "").strip()
                    if chosen:
                        self._send_json({"ok": True, "path": str(Path(chosen).resolve())})
                    else:
                        self._send_json({"ok": False, "cancelled": True})
                except Exception as exc:
                    self._send_json({"ok": False, "error": f"Folder picker failed: {exc}"}, 500)
                return

            if path == "/api/projects/open":
                if self.client_address[0] != "127.0.0.1":
                    self._send_json({"error": "Forbidden"}, 403)
                    return
                proj_path = str(body.get("path", "")).strip()
                create_flag = bool(body.get("create_if_missing", False))
                ok, msg = state.switch_project(proj_path, create_if_missing=create_flag)
                if ok:
                    self._send_json({
                        "ok": True,
                        "message": msg,
                        "state": state.get_state_payload(),
                        "projects": state.list_projects(),
                    })
                else:
                    self._send_json({"ok": False, "error": msg}, 400)
                return

            if path == "/api/projects/remove":
                if self.client_address[0] != "127.0.0.1":
                    self._send_json({"error": "Forbidden"}, 403)
                    return
                proj_path = str(body.get("path", "")).strip()
                removed = state.remove_project(proj_path)
                self._send_json({"ok": removed, "projects": state.list_projects()})
                return

            if path == "/api/loras/add":
                p_str = str(body.get("path", "")).strip()
                if not p_str:
                    self._send_json({"error": "Missing LoRA path"}, 400)
                    return
                ok, msg, _ = config.add_custom_lora_path(p_str)
                self._send_json({"ok": ok, "message": msg, "state": state.get_state_payload()})
                return

            if path == "/api/loras/delete":
                p_str = str(body.get("path", "")).strip()
                if not p_str:
                    self._send_json({"error": "Missing LoRA path"}, 400)
                    return
                ok, msg = config.remove_lora_adapter(p_str)
                self._send_json({"ok": ok, "message": msg, "state": state.get_state_payload()})
                return

            if path == "/api/loras/set":
                loras_in = body.get("loras", [])
                clean = config.set_active_loras(loras_in)
                if state.server_mgr.is_healthy() and state.model_name:
                    try:
                        state.server_mgr.start(state.model_name, loras=clean)
                    except Exception as exc:
                        self._send_json({"ok": False, "error": f"Failed to reload model with LoRA: {exc}"}, 500)
                        return
                self._send_json({"ok": True, "active_loras": clean, "state": state.get_state_payload()})
                return

            if path.startswith("/api/plugin/"):
                rest = path[len("/api/plugin/"):]
                parts = rest.split("/", 1)
                pid = parts[0]
                sub_p = parts[1] if len(parts) > 1 else ""
                code, payload = state.dispatch_plugin_api(pid, "POST", sub_p, {}, body)
                self._send_json(payload, status=code)
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
                            state.server_mgr.start(new_model, loras=config.get_active_loras())
                        except Exception as exc:
                            self._send_json({"error": f"Failed to switch model: {exc}"}, 500)
                            return

                if body.get("action") == "new_session":
                    title = str(body.get("title", "")).strip() or None
                    sess = state.session_mgr.create_session(name=title or "", workspace=str(state.workspace_root))
                    state.loaded_session_id = sess.get("id")
                    state.agent.reset_session()
                    self._send_json({"ok": True, "session": sess, "state": state.get_state_payload()})
                    return

                if body.get("action") == "switch_session":
                    sid = str(body.get("session_id", "")).strip()
                    ok, msg, s_data = state.session_mgr.switch_session(sid, workspace=str(state.workspace_root))
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
