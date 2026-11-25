import re
import json
import time
import http.client
import threading
import urllib.parse
import urllib.request
import urllib.error

from web_search import WebSearchTool

SYSTEM_PROMPTS = {
    "en": """You are LENSETEK LEAN AGENT HARNESS, an autonomous local AI assistant designed to be ultra-efficient, precise, and resourceful.
You manage files in the workspace/laptop, assist with coding, operate MCP servers (such as fetch/playwright/chrome), execute skills, and perform web searches.

CORE GUIDELINES:
1. Always inspect files using `list_dir`, `search_files`, or `read_file` before making modifications.
2. You have full filesystem and shell execution tools. When asked to create, generate, or edit any file, code, or document, or when asked if you can create files, NEVER refuse and NEVER say "As an AI, I cannot create files". Immediately execute directly in the active workspace using `write_or_edit_file` (mode='write' or 'edit', or a script via `run_command` for binary formats) rather than giving code examples, tutorials, or plain text in chat.
3. You have HEADLESS WEB SEARCH capability via `web_search(query)`. If you need up-to-date information, documentation, news, or technical solutions, use `web_search` first. To read full article/page contents from a discovered URL, call MCP fetch (`mcp_call` with server='fetch', tool='fetch', arguments={'url': ...}).
4. For browser or external MCP tools, call `mcp_list_tools` first to see available tools before calling `mcp_call`.
5. SKILLS ARE NOT MCP SERVERS:
   - Never call `mcp_list_tools` or `mcp_call` using skill names (e.g. 'research-orchestrator', 'code-review').
   - Skills are workflow guidelines that YOU execute directly.
   - Use `search_skills` to discover skills, and `read_skill(skill_name)` to view their full instructions.
6. Always respond accurately, helpfully, and concisely in English.""",

    "id": """Anda adalah LENSETEK LEAN AGENT HARNESS, asisten AI otonom lokal yang efisien, cermat, dan mandiri.
Tugas Anda mengelola file di workspace aktif, membantu coding, mengoperasikan MCP (seperti fetch/playwright/chrome), mengeksekusi skills, dan melakukan pencarian web.

PEDOMAN KERJA:
1. Selalu periksa file dengan `list_dir`, `search_files`, atau `read_file` sebelum memodifikasi file.
2. Anda memiliki akses penuh ke filesystem dan terminal. Saat diminta membuat, menulis, atau mengedit file, kode, maupun dokumen apa pun (atau saat ditanya apakah Anda bisa membuatnya), JANGAN PERNAH menolak dan JANGAN PERNAH berkata "Sebagai asisten AI saya tidak dapat membuat file". Eksekusi langsung di workspace aktif menggunakan `write_or_edit_file` (mode='write' atau 'edit', atau skrip via `run_command` untuk format biner) alih-alih hanya memberikan contoh kode, tutorial, atau teks di chat.
3. Anda memiliki kemampuan PENCARIAN WEB HEADLESS via `web_search(query)`. Gunakan tool ini jika Anda membutuhkan informasi terbaru, dokumentasi, tren, atau solusi error teknis sebelum menjawab. Untuk membaca isi lengkap dari URL yang ditemukan, panggil MCP fetch (`mcp_call` dengan server='fetch', tool='fetch', arguments={'url': ...}).
4. Untuk browser atau MCP eksternal: panggil `mcp_list_tools` terlebih dahulu untuk melihat daftar tool yang tersedia sebelum memanggil `mcp_call`.
5. ATURAN SKILL & MCP (PENTING):
   - SKILL BUKAN SERVER MCP! Jangan pernah memanggil `mcp_list_tools` atau `mcp_call` menggunakan nama skill (seperti 'research-orchestrator').
   - Skill adalah panduan kerja yang ANDA laksanakan secara mandiri.
   - Gunakan `search_skills` untuk mencari skill dan `read_skill(skill_name)` untuk membaca panduannya.
6. Selalu berikan respons yang ringkas, langsung ke inti permasalahan, dan akurat dalam Bahasa Indonesia.""",

    "cn": """您是 LENSETEK LEAN AGENT HARNESS，一个自主、高效、精准的本地AI助手。
您的职责包括管理工作区/电脑中的文件、编写代码、操作MCP服务器（如fetch/playwright/chrome）、执行技能以及进行无头网络搜索。

工作准则：
1. 在修改文件之前，务必先通过 `list_dir`、`search_files` 或 `read_file` 检查文件内容。
2. 您拥有完整的文件系统与终端执行权限。当用户要求创建、编写或编辑任何文件、代码或文档，或询问您是否能够创建时，切勿推脱，切勿声称“作为AI我无法直接创建文件”。务必直接使用 `write_or_edit_file`（mode='write' 或 'edit'，二进制格式可通过 `run_command` 运行生成脚本）在当前工作区落地执行，切勿仅输出示例代码、教程或解释性文本。
3. 您具备无头网络搜索功能 `web_search(query)`。当您需要获取最新资讯、学术文献或报错解决方案时，请先使用 `web_search`。如需阅读搜索结果中URL的完整内容，请调用 MCP fetch（`mcp_call`，server='fetch'）。
4. 对于浏览器或其他MCP服务，在调用 `mcp_call` 前请先通过 `mcp_list_tools` 查看可用工具。
5. 技能与MCP规范（重要）：
   - 技能（Skill）不是MCP服务器！切勿使用技能名称（如 'research-orchestrator'）调用 `mcp_list_tools` 或 `mcp_call`。
   - 技能是指引手册，由您直接执行。使用 `search_skills` 检索技能，使用 `read_skill(skill_name)` 阅读指引。
6. 请始终用简体中文准确、清晰、简洁地进行回复。"""
}

class LeanAgent:
    def __init__(self, base_url: str, fs_tools, mcp_manager, skills_manager=None, session_manager=None, ctx_size: int = 8192, model_name: str = None, language: str = "en", effort_level: str = "medium", plugin_tools: list[dict] = None):
        self.base_url = base_url.rstrip("/")
        self.fs_tools = fs_tools
        self.mcp_manager = mcp_manager
        self.skills_manager = skills_manager
        self.session_manager = session_manager
        self.plugin_tools = plugin_tools or []
        self.web_search_tool = WebSearchTool()
        self.ctx_size = ctx_size
        self.model_name = model_name
        self.language = language if language in SYSTEM_PROMPTS else "en"
        self.effort_level = effort_level.lower().strip() if effort_level in ("off", "low", "medium", "high") else "medium"
        self.messages = []
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.active_goal = None
        self.cancel_requested = False
        self._active_http_conn = None
        self._conn_lock = threading.Lock()
        self.reset_session()

    def _cancelled_message(self) -> str:
        if self.language == "id":
            return "⏹ Proses dibatalkan oleh pengguna."
        if self.language == "cn":
            return "⏹ 用户已取消操作。"
        return "⏹ Process cancelled by user."

    def cancel(self):
        """Request immediate cancellation of the active run_turn loop and abort in-flight LLM HTTP call."""
        self.cancel_requested = True
        with self._conn_lock:
            conn = self._active_http_conn
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def load_session(self, session_data: dict):
        """Memuat riwayat percakapan dari session tersimpan ke dalam messages aktif."""
        self.reset_session()
        for m in session_data.get("messages", []):
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and content:
                self.messages.append({"role": role, "content": content})

    def set_language(self, lang_code: str):
        """Mengubah bahasa agen dan memperbarui system prompt."""
        code = lang_code.lower().strip()
        if code in ("zh", "chinese"):
            code = "cn"
        if code in SYSTEM_PROMPTS:
            self.language = code
            self.reset_session()

    def set_effort(self, effort_level: str):
        """Mengubah tingkat thinking effort ('off', 'low', 'medium', 'high')."""
        level = effort_level.lower().strip()
        if level in ("off", "low", "medium", "high"):
            self.effort_level = level
            self.reset_session()

    def reset_session(self):
        prompt_text = SYSTEM_PROMPTS.get(self.language, SYSTEM_PROMPTS["en"])

        # Language-agnostic workspace grounding: inject active path + top-level snapshot
        ws_path = getattr(self.fs_tools, "workspace_root", ".")
        top_items = []
        try:
            from pathlib import Path as _Path
            ws_p = _Path(ws_path)
            if ws_p.exists() and ws_p.is_dir():
                for entry in sorted(ws_p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                    low_name = entry.name.lower()
                    if entry.name in (".git", ".venv", "__pycache__", "node_modules") or low_name.startswith(".env"):
                        continue
                    top_items.append(f"{entry.name}/" if entry.is_dir() else entry.name)
                    if len(top_items) >= 25:
                        top_items.append("...")
                        break
        except Exception:
            pass

        items_str = ", ".join(top_items) if top_items else "(empty)"
        prompt_text += (
            f"\n\n[WORKSPACE CONTEXT]\n"
            f"Active Directory: {ws_path}\n"
            f"Top-level items: {items_str}\n"
            f"Note: '.' always refers to this active workspace. Never ask the user for the current folder path; inspect directly with `list_dir(path=\".\")` or `read_file(...)`."
        )
        
        # Injeksi directive effort ke system prompt
        if self.effort_level == "off":
            if self.language == "id":
                prompt_text += "\n\n[PANDUAN PENALARAN: Tingkat effort = OFF. JANGAN hasilkan blok tag <think>...</think> atau monolog panjang. Berikan jawaban atau pemanggilan tool secara langsung dan cepat.]"
            elif self.language == "cn":
                prompt_text += "\n\n[思考准则：思考强度 = OFF。请勿输出 <think>...</think> 内部思考过程，直接提供明确答复或调用工具。]"
            else:
                prompt_text += "\n\n[REASONING DIRECTIVE: Effort = OFF. Do NOT generate internal <think>...</think> monologue. Provide direct, immediate answers and tool calls.]"
        elif self.effort_level == "low":
            if self.language == "id":
                prompt_text += "\n\n[PANDUAN PENALARAN: Tingkat effort = LOW. Buat penalaran internal dalam <think>...</think> secara ringkas, padat, dan terfokus.]"
            elif self.language == "cn":
                prompt_text += "\n\n[思考准则：思考强度 = LOW。保持 <think>...</think> 内的思考过程简明扼要。]"
            else:
                prompt_text += "\n\n[REASONING DIRECTIVE: Effort = LOW. Keep internal chain of thought in <think> tags concise and focused.]"
        elif self.effort_level == "high":
            if self.language == "id":
                prompt_text += "\n\n[PANDUAN PENALARAN: Tingkat effort = HIGH. Lakukan penalaran mendalam dan sistematis langkah demi langkah dalam <think>...</think> sebelum memberikan jawaban final.]"
            elif self.language == "cn":
                prompt_text += "\n\n[思考准则：思考强度 = HIGH。在 <think>...</think> 中进行深入、细致的多步推演后再输出最终结论。]"
            else:
                prompt_text += "\n\n[REASONING DIRECTIVE: Effort = HIGH. Perform rigorous, multi-step deep reasoning inside <think>...</think> tags before delivering conclusions.]"

        self.messages = [
            {"role": "system", "content": prompt_text}
        ]
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.active_goal = None

    def _format_content_with_effort(self, content: str) -> str:
        """Memformat atau membersihkan tag <think>...</think> sesuai tingkat effort."""
        if not content:
            return ""
        
        # Jika effort OFF: buang seluruh blok <think>...</think>
        if self.effort_level == "off":
            cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content)
            return cleaned.strip()

        # Jika effort low, medium, high: tata tampilan thinking secara elegan
        think_match = re.search(r"<think>([\s\S]*?)</think>", content)
        if think_match:
            thought_text = think_match.group(1).strip()
            answer_text = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
            
            if self.language == "id":
                lbl = "💭 [Proses Berpikir / Penalaran]"
            elif self.language == "cn":
                lbl = "💭 [思维链 / 深度思考过程]"
            else:
                lbl = "💭 [Thinking Process / Reasoning]"

            header = f"\033[2m\033[36m{lbl}:\n{thought_text}\n{'─' * 44}\033[0m"
            if answer_text:
                return f"{header}\n\n{answer_text}"
            return header

        return content

    def _get_all_tools(self) -> list[dict]:
        tools = []
        if self.fs_tools:
            tools.extend(self.fs_tools.get_openai_tools())
        if self.mcp_manager:
            tools.extend(self.mcp_manager.get_openai_tools())
        if self.skills_manager:
            tools.extend(self.skills_manager.get_openai_tools())
        if self.web_search_tool:
            tools.append(self.web_search_tool.get_openai_tool())
        if self.plugin_tools:
            for pt in self.plugin_tools:
                schema = pt.get("schema") or {
                    "type": "function",
                    "function": {
                        "name": pt.get("name"),
                        "description": pt.get("description", ""),
                        "parameters": pt.get("parameters", {"type": "object", "properties": {}})
                    }
                }
                tools.append(schema)
        return tools

    def _trim_history_if_needed(self):
        """Memangkas riwayat chat jika mendekati batas context window."""
        est_tokens = self.last_usage.get("total_tokens", 0)
        if est_tokens > int(self.ctx_size * 0.75):
            if self.active_goal and len(self.messages) > 5:
                del self.messages[2:4]
            elif len(self.messages) > 4:
                del self.messages[1:3]

    def _parse_xml_tool_calls(self, text: str) -> list[dict]:
        """Fallback parser when a 3B SLM emits <tool_call>{...}</tool_call> or a literal Python tool call in text."""
        tool_calls = []
        if not text:
            return tool_calls

        if "<tool_call>" in text:
            pattern = r"<tool_call>\s*(\{.*?\})\s*</tool_call>"
            matches = re.findall(pattern, text, re.DOTALL)
            for idx, match in enumerate(matches):
                try:
                    data = json.loads(match.strip())
                    name = data.get("name")
                    args = data.get("arguments", {})
                    if name:
                        tool_calls.append({
                            "id": f"call_xml_{idx}",
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args) if isinstance(args, dict) else str(args)
                            }
                        })
                except Exception:
                    continue
            if tool_calls:
                return tool_calls

        # Safe AST fallback if SLM wrote literal `write_or_edit_file(path="...", mode="write", content="...")` in a code block
        known_tools = {"list_dir", "search_files", "read_file", "write_or_edit_file", "run_command", "web_search"}
        if any(f"{t}(" in text for t in known_tools):
            import ast
            code_blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", text)
            candidates = code_blocks if code_blocks else [text]
            for blk in candidates:
                try:
                    tree = ast.parse(blk.strip())
                except Exception:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in known_tools:
                        if node.args:
                            continue  # require explicit keyword arguments with constant literals only
                        kw_dict = {}
                        valid_literals = True
                        for kw in node.keywords:
                            if not kw.arg:
                                valid_literals = False
                                break
                            try:
                                kw_dict[kw.arg] = ast.literal_eval(kw.value)
                            except Exception:
                                # Fallback evaluation for f-strings or string concatenation
                                if isinstance(kw.value, ast.JoinedStr):
                                    parts = []
                                    for part in kw.value.values:
                                        if isinstance(part, ast.Constant):
                                            parts.append(str(part.value))
                                        elif isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Constant):
                                            parts.append(str(part.value.value))
                                    if parts:
                                        kw_dict[kw.arg] = "".join(parts)
                                    else:
                                        valid_literals = False
                                        break
                                elif isinstance(kw.value, ast.BinOp) and isinstance(kw.value.op, ast.Add):
                                    try:
                                        kw_dict[kw.arg] = str(ast.literal_eval(kw.value.left)) + str(ast.literal_eval(kw.value.right))
                                    except Exception:
                                        valid_literals = False
                                        break
                                else:
                                    valid_literals = False
                                    break
                        if valid_literals and kw_dict:
                            tool_calls.append({
                                "id": f"call_ast_{len(tool_calls)}",
                                "type": "function",
                                "function": {
                                    "name": node.func.id,
                                    "arguments": json.dumps(kw_dict, ensure_ascii=False)
                                }
                            })
        return tool_calls

    def _execute_tool(self, name: str, args: dict) -> str:
        # 1. Native Web Search Tool
        if name == "web_search" and self.web_search_tool:
            return self.web_search_tool.execute(args)

        # 2. File & Shell Tools
        fs_names = {"list_dir", "search_files", "read_file", "write_or_edit_file", "run_command"}
        if name in fs_names and self.fs_tools:
            return self.fs_tools.execute(name, args)

        # 3. MCP Tools (dengan pengaman anti-halusinasi skill vs MCP)
        mcp_names = {"mcp_list_tools", "mcp_call", "mcp_install"}
        if name in mcp_names and self.mcp_manager:
            server_arg = (args.get("server_name") or "").strip()
            tool_arg = (args.get("tool_name") or "").strip()
            if self.skills_manager:
                try:
                    all_skills = self.skills_manager.scan_skills()
                    clean_srv = server_arg.lower().replace("_", "-")
                    clean_tool = tool_arg.lower().replace("_", "-")
                    if clean_srv in all_skills:
                        return (
                            f"Error: '{server_arg}' adalah SKILL, BUKAN SERVER MCP!\n"
                            f"Anda tidak dapat memanggil skill lewat {name}.\n"
                            f"Peran Anda adalah mengeksekusi langsung tugas tersebut. "
                            f"Gunakan 'web_search' bila memerlukan data/literatur luar, lalu susun jawaban lengkap Anda secara langsung."
                        )
                    if clean_tool in all_skills:
                        return (
                            f"Error: '{tool_arg}' adalah SKILL, BUKAN tool dari server MCP '{server_arg}'!\n"
                            f"Jangan panggil skill lewat MCP. Kerjakan analisis secara mandiri menggunakan informasi yang ada atau web_search."
                        )
                except Exception:
                    pass
            return self.mcp_manager.execute(name, args)

        # 4. Skills Tools
        skill_names = {"search_skills", "read_skill", "create_skill"}
        if name in skill_names and self.skills_manager:
            return self.skills_manager.execute(name, args)

        # 5. Plugin Tools
        if self.plugin_tools:
            for pt in self.plugin_tools:
                if pt.get("name") == name:
                    handler = pt.get("handler")
                    if callable(handler):
                        ctx = {
                            "workspace": str(self.fs_tools.workspace_root) if self.fs_tools else ".",
                            "lang": self.language
                        }
                        try:
                            return str(handler(args, ctx))
                        except Exception as e:
                            return f"Error executing plugin tool '{name}': {e}"

        return f"Error: Tool '{name}' tidak terdaftar pada sistem."

    def _expand_at_mentions(self, user_text: str) -> str:
        """Auto-attach content preview for @"file with spaces" or @path/to/file mentions."""
        if not self.fs_tools or "@" not in user_text:
            return user_text

        mentioned = []
        for m in re.finditer(r'@"([^"]+)"|(?:^|\s)@([^\s"\']+)', user_text):
            raw_p = (m.group(1) or m.group(2) or "").strip()
            if raw_p and raw_p not in mentioned:
                mentioned.append(raw_p)

        if not mentioned:
            return user_text

        blocks = []
        for rel_p in mentioned[:3]:
            try:
                target = self.fs_tools._resolve_path(rel_p)
                if target.exists() and target.is_file() and self.fs_tools._is_inside_workspace(target):
                    low = target.name.lower()
                    if low.startswith(".env") or target.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
                        continue
                    snippet = self.fs_tools.read_file(rel_p, 1, 90)
                    blocks.append(f"[ATTACHED FILE: {rel_p}]\n{snippet}")
            except Exception:
                continue

        if not blocks:
            return user_text
        return user_text + "\n\n" + "\n\n".join(blocks)

    def run_turn(self, user_text: str, on_status=None, on_tool=None, max_steps: int = 8) -> str:
        self.cancel_requested = False
        enriched_text = self._expand_at_mentions(user_text)
        self.messages.append({"role": "user", "content": enriched_text})
        failed_calls = {}

        try:
            for step in range(max_steps):
                if getattr(self, "cancel_requested", False):
                    self.cancel_requested = False
                    return self._cancelled_message()

                self._trim_history_if_needed()

                if on_status:
                    if self.language == "en":
                        status_msg = f"Thinking... (Step {step + 1}/{max_steps}) [Click Cancel to stop]"
                    elif self.language == "cn":
                        status_msg = f"思考中... (步骤 {step + 1}/{max_steps}) [点击取消终止]"
                    else:
                        status_msg = f"Sedang berpikir... (Langkah {step + 1}/{max_steps}) [Klik Batalkan untuk berhenti]"
                    on_status(status_msg)

                temp_map = {"off": 0.1, "low": 0.2, "medium": 0.4, "high": 0.7}
                temperature = temp_map.get(self.effort_level, 0.4)

                payload = {
                    "model": self.model_name or "local-model",
                    "messages": self.messages,
                    "tools": self._get_all_tools(),
                    "temperature": temperature,
                    "stream": False
                }
                if self.effort_level != "medium":
                    payload["reasoning_effort"] = self.effort_level

                parsed_url = urllib.parse.urlparse(self.base_url)
                host = parsed_url.hostname or "127.0.0.1"
                port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
                base_path = parsed_url.path.rstrip("/")
                conn = http.client.HTTPConnection(host, port, timeout=300)
                with self._conn_lock:
                    self._active_http_conn = conn

                try:
                    conn.request(
                        "POST",
                        f"{base_path}/v1/chat/completions",
                        body=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                    )
                    resp = conn.getresponse()
                    raw_body = resp.read().decode("utf-8", errors="ignore")
                    if resp.status >= 400:
                        if getattr(self, "cancel_requested", False):
                            self.cancel_requested = False
                            return self._cancelled_message()
                        return f"HTTP Error {resp.status} dari llama-server: {raw_body}"
                    res_data = json.loads(raw_body)
                except Exception as e:
                    if getattr(self, "cancel_requested", False):
                        self.cancel_requested = False
                        return self._cancelled_message()
                    return f"Error koneksi ke llama-server: {str(e)}"
                finally:
                    with self._conn_lock:
                        if self._active_http_conn is conn:
                            self._active_http_conn = None
                    try:
                        conn.close()
                    except Exception:
                        pass

                if getattr(self, "cancel_requested", False):
                    self.cancel_requested = False
                    return self._cancelled_message()

                choice = res_data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                raw_tool_calls = message.get("tool_calls") or []

                usage = res_data.get("usage", {})
                if usage:
                    self.last_usage = usage

                if not raw_tool_calls and content:
                    raw_tool_calls = self._parse_xml_tool_calls(content)

                if not raw_tool_calls:
                    self.messages.append({"role": "assistant", "content": content})
                    final_ans = self._format_content_with_effort(content)
                    if self.session_manager:
                        try:
                            act_id = self.session_manager.get_active_session_id()
                            self.session_manager.save_turn(act_id, user_text, final_ans, model_name=self.model_name or "")
                        except Exception:
                            pass
                    return final_ans

                self.messages.append(message)

                for tc in raw_tool_calls:
                    if getattr(self, "cancel_requested", False):
                        self.cancel_requested = False
                        return self._cancelled_message()
                    func = tc.get("function", {})
                    call_id = tc.get("id", "call_1")
                    t_name = func.get("name", "")
                    t_args_raw = func.get("arguments", "{}")

                    if isinstance(t_args_raw, str):
                        try:
                            t_args = json.loads(t_args_raw)
                        except Exception:
                            t_args = {}
                    else:
                        t_args = t_args_raw or {}

                    # Signature call untuk deteksi pengulangan error beruntun
                    call_sig = f"{t_name}:{json.dumps(t_args, sort_keys=True)}"
                    if failed_calls.get(call_sig, 0) >= 2:
                        result = (
                            f"Peringatan: Pemanggilan '{t_name}' berulang kali gagal. "
                            f"Hentikan pemanggilan tool ini. Segera susun jawaban final Anda langsung kepada pengguna."
                        )
                    else:
                        if on_tool:
                            on_tool(t_name, t_args, None)
                        result = self._execute_tool(t_name, t_args)
                        if "Error" in result or "tidak terdaftar" in result or "Unknown tool" in result:
                            failed_calls[call_sig] = failed_calls.get(call_sig, 0) + 1

                    if on_tool:
                        on_tool(t_name, t_args, result)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": t_name,
                        "content": result
                    })

            final_max = f"Completed: Maximum tool steps ({max_steps}) reached."
            if self.session_manager:
                try:
                    act_id = self.session_manager.get_active_session_id()
                    self.session_manager.save_turn(act_id, user_text, final_max, model_name=self.model_name or "")
                except Exception:
                    pass
            return final_max
        except KeyboardInterrupt:
            return "⚠️ [Interrupted: Operation cancelled by user via Ctrl+C]"

    def run_goal(self, goal_text: str, max_steps: int = 20, on_status=None, on_tool=None) -> str:
        """Mode /goal otonom dengan Pinned Goal yang kebal terhadap context trimming."""
        self.reset_session()
        self.active_goal = goal_text
        if self.language == "en":
            pinned_prompt = (
                f"[ACTIVE GOAL - DO NOT FORGET THIS TARGET]\n"
                f"Your Goal: {goal_text}\n\n"
                f"Autonomous Guidelines: Plan your steps, execute tools sequentially, verify "
                f"that the objective is successfully completed, and present the final report."
            )
        elif self.language == "cn":
            pinned_prompt = (
                f"[当前目标 - 请勿遗忘此目标]\n"
                f"目标内容: {goal_text}\n\n"
                f"自主执行准则: 规划步骤、依次调用工具、验证目标完成情况并输出最终报告。"
            )
        else:
            pinned_prompt = (
                f"[ACTIVE GOAL - JANGAN LUPAKAN TARGET INI]\n"
                f"Target Anda: {goal_text}\n\n"
                f"Instruksi Otonom: Rencanakan langkah-langkah kerja, jalankan tool secara berurutan, "
                f"lakukan verifikasi bahwa target tercapai dengan sukses, dan sajikan laporan akhir."
            )
        try:
            return self.run_turn(pinned_prompt, on_status=on_status, on_tool=on_tool, max_steps=max_steps)
        except KeyboardInterrupt:
            return "⚠️ [Interrupted: /goal mode stopped by user via Ctrl+C]"
        finally:
            self.active_goal = None

    def run_loop(self, count_or_interval: str, prompt_text: str, on_status=None, on_tool=None, on_iteration=None) -> str:
        """Mode /loop berulang (misal '3x' atau '5m') dengan reset context otomatis antar-iterasi."""
        spec = count_or_interval.strip().lower()
        last_summary = ""

        try:
            if spec.endswith("x"):
                try:
                    times = int(spec[:-1])
                except ValueError:
                    times = 3

                for i in range(1, times + 1):
                    if on_iteration:
                        on_iteration(i, times)
                    iter_prompt = prompt_text
                    if last_summary:
                        iter_prompt += f"\n\n[Previous iteration summary: {last_summary[:300]}]"

                    self.reset_session()
                    res = self.run_turn(iter_prompt, on_status=on_status, on_tool=on_tool, max_steps=8)
                    last_summary = res[:300]
                return f"Loop completed {times} times."

            else:
                interval_sec = 300
                if spec.endswith("s"):
                    interval_sec = max(5, int(spec[:-1]))
                elif spec.endswith("m"):
                    interval_sec = max(10, int(spec[:-1]) * 60)
                elif spec.endswith("h"):
                    interval_sec = max(60, int(spec[:-1]) * 3600)
                elif spec.isdigit():
                    interval_sec = max(10, int(spec) * 60)

                iter_count = 0
                while True:
                    iter_count += 1
                    if on_iteration:
                        on_iteration(iter_count, None)
                    iter_prompt = prompt_text
                    if last_summary:
                        iter_prompt += f"\n\n[Previous iteration summary: {last_summary[:300]}]"

                    self.reset_session()
                    res = self.run_turn(iter_prompt, on_status=on_status, on_tool=on_tool, max_steps=8)
                    last_summary = res[:300]

                    if on_status:
                        on_status(f"Waiting {interval_sec}s for next iteration... (Press Ctrl+C to stop loop)")
                    time.sleep(interval_sec)
        except KeyboardInterrupt:
            return "⚠️ [Interrupted: /loop mode stopped by user via Ctrl+C]"
