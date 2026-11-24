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
            if active_sess:
                self.agent.load_session(active_sess)

    def _web_confirm(self, prompt_text: str) -> bool:
        """Pause tool execution and request approval in the active WebUI job."""
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
            items = plugin_manager.get_all_catalog_plugins()
            lines = ["### Plugin Catalog\n"]
            for itm in items:
                st = "Installed" if itm.get("is_installed") else "Available"
                desc = itm.get(f"description_{self.agent.language}", itm.get("description", ""))
                lines.append(f"- `{itm.get('id')}` **[{st}]** — {desc}")
            lines.append("\nUsage: `/plugins install <id>` or `/plugins remove <id>`")
            return "\n".join(lines)

        # Check if user invoked a skill directly via /<skill_slug>
        skill_slug = cmd[1:]
        skill_prompt = self.skills_mgr.get_skill_prompt(skill_slug)
        if skill_prompt:
            user_goal = arg if arg else "Analyze thoroughly and provide a structured report following this skill guide."
            combined = (
                f"[SKILL GUIDE: /{skill_slug}]\n"
                f"{skill_prompt}\n\n"
                f"USER TASK: {user_goal}"
            )
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
                    state.agent.reset_session()
                    self._send_json({"ok": True, "session": sess, "state": state.get_state_payload()})
                    return

                if body.get("action") == "switch_session":
                    sid = str(body.get("session_id", "")).strip()
                    ok, msg, s_data = state.session_mgr.switch_session(sid)
                    if ok and s_data:
                        state.agent.load_session(s_data)
                        self._send_json({"ok": True, "session": s_data, "state": state.get_state_payload()})
                    else:
                        self._send_json({"error": msg}, 400)
                    return

                self._send_json({"ok": True, "state": state.get_state_payload()})
                return

            self._send_json({"error": "Not found"}, 404)

    return WebUIRequestHandler


_ACTIVE_SERVER: Optional[ThreadingHTTPServer] = None


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
    httpd: Optional[ThreadingHTTPServer] = None
    last_err: Optional[OSError] = None
    for candidate_port in range(web_port, web_port + 21):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate_port), handler_cls)
            break
        except OSError as exc:
            last_err = exc
    if httpd is None:
        raise last_err or OSError(f"Unable to bind WebUI server on ports {web_port}-{web_port + 20}")
    _ACTIVE_SERVER = httpd

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd
