import os
import sys
import json
import shutil
import queue
import threading
import subprocess
from pathlib import Path

import config

class MCPStdioClient:
    def __init__(self, name: str, command: str, args: list[str], env: dict = None):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or os.environ.copy()
        self.process = None
        self.msg_id = 0
        self.line_queue = queue.Queue()
        self.reader_thread = None
        self.tools_cache = []
        self._running = False

    def _reader_loop(self):
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    self.line_queue.put(line)
            except Exception:
                break

    def start(self, timeout: float = 25.0):
        if self.process and self.process.poll() is None:
            return

        exe = shutil.which(self.command)
        if not exe:
            # Di Windows, coba tambahkan .cmd jika belum ada
            if sys.platform == "win32":
                exe = shutil.which(f"{self.command}.cmd") or shutil.which(f"{self.command}.bat")
            if not exe:
                exe = self.command

        cmd_line = [exe] + list(self.args)
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            self.process = subprocess.Popen(
                cmd_line,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=self.env,
                creationflags=creationflags
            )
        except Exception as e:
            raise RuntimeError(f"Gagal menjalankan server MCP '{self.name}' ({cmd_line}): {e}")

        self._running = True
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

        # 1. Kirim JSON-RPC initialize dengan identitas Lensetek Lean Agent
        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "lensetek-lean-agent", "version": "2.0.0"}
            }
        }
        res = self._send_request(init_req, timeout=timeout)
        if not res:
            self.close()
            raise RuntimeError(f"MCP '{self.name}' tidak merespons request initialize (timeout {timeout}s).")

        # 2. Kirim notifikasi initialized
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        self._send_notification(notif)

    def _next_id(self) -> int:
        self.msg_id += 1
        return self.msg_id

    def _send_notification(self, payload: dict):
        if not self.process or not self.process.stdin:
            return
        try:
            data = json.dumps(payload, ensure_ascii=False) + "\n"
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except Exception:
            pass

    def _send_request(self, payload: dict, timeout: float = 30.0) -> dict | None:
        if not self.process or not self.process.stdin:
            return None
        target_id = payload.get("id")
        try:
            data = json.dumps(payload, ensure_ascii=False) + "\n"
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except Exception as e:
            return {"error": {"message": f"Write error: {e}"}}

        import time
        start_t = time.time()
        while time.time() - start_t < timeout:
            try:
                line = self.line_queue.get(timeout=0.5)
                try:
                    obj = json.loads(line)
                    if obj.get("id") == target_id:
                        return obj
                except json.JSONDecodeError:
                    continue
            except queue.Empty:
                if self.process.poll() is not None:
                    return {"error": {"message": f"Server process '{self.name}' telah berhenti tak terduga."}}
                continue

        return {"error": {"message": f"Request ke '{self.name}' timeout setelah {timeout} detik."}}

    def list_tools(self) -> list[dict]:
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        res = self._send_request(req, timeout=20.0)
        if res and "result" in res and "tools" in res["result"]:
            self.tools_cache = res["result"]["tools"]
            return self.tools_cache
        return self.tools_cache

    def call_tool(self, tool_name: str, arguments: dict = None) -> str:
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        res = self._send_request(req, timeout=45.0)
        if not res:
            return f"Error: MCP '{self.name}' tidak mengembalikan respons."

        if "error" in res:
            err = res["error"]
            return f"MCP Error ({self.name}): {err.get('message', str(err))}"

        result = res.get("result", {})
        content_items = result.get("content", [])
        text_parts = []
        for item in content_items:
            if isinstance(item, dict):
                itype = item.get("type")
                if itype == "text":
                    text_parts.append(item.get("text", ""))
                elif itype == "image":
                    text_parts.append("[Image data omitted to save context]")
                elif itype == "resource":
                    text_parts.append(f"[Resource: {item.get('resource', {}).get('uri', '')}]")
                else:
                    text_parts.append(str(item))
            else:
                text_parts.append(str(item))

        full_text = "\n".join(text_parts) if text_parts else json.dumps(result, ensure_ascii=False)
        # Smart Output Trimming (maksimal 3500 karakter agar tidak meledakkan context 8192)
        if len(full_text) > 3500:
            full_text = full_text[:3500] + "\n... [Output MCP terpotong: melebihi 3500 karakter untuk menghemat memori KV Cache]"
        return full_text

    def close(self):
        self._running = False
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
            except Exception:
                pass
            finally:
                self.process = None


class MCPManager:
    def __init__(self, config_dict: dict = None, confirm_fn=None, safety_mode: str = "strict"):
        self.config = config_dict or {}
        self.clients: dict[str, MCPStdioClient] = {}
        self.confirm_fn = confirm_fn
        self.safety_mode = safety_mode.strip().lower()

    def set_safety_mode(self, mode: str):
        mode = mode.strip().lower()
        if mode in ("strict", "auto-approve", "yolo", "read-only"):
            self.safety_mode = mode

    def get_server_names(self) -> list[str]:
        return [k for k, v in self.config.items() if v.get("enabled", True)]

    def _get_or_start_client(self, server_name: str) -> MCPStdioClient:
        if server_name in self.clients:
            client = self.clients[server_name]
            if client.process and client.process.poll() is None:
                return client

        if server_name not in self.config:
            raise ValueError(
                f"Server MCP '{server_name}' tidak terdaftar di konfigurasi. Pilihan server aktif: {list(self.config.keys())}. "
                f"PERHATIAN: Jika '{server_name}' adalah nama skill, SKILL BUKANLAH SERVER MCP! "
                f"Jangan mencoba memanggil skill lewat MCP. Gunakan tool 'read_skill' atau 'web_search', lalu sintesis jawaban secara langsung."
            )

        cfg = self.config[server_name]
        
        # Inject env variables dari .env.local dan os.environ secara aman
        env_map = os.environ.copy()
        dot_env = config.load_dotenv_local()
        env_map.update(dot_env)

        needed_keys = cfg.get("env_keys", [])
        for ek in needed_keys:
            if ek not in env_map or not env_map[ek]:
                print(f"[WARN] MCP '{server_name}' memerlukan environment variable '{ek}'. Pastikan sudah diatur di .env.local")

        client = MCPStdioClient(
            name=server_name,
            command=cfg.get("command", ""),
            args=cfg.get("args", []),
            env=env_map
        )
        client.start()
        self.clients[server_name] = client
        return client

    def install_server(self, name: str, command: str = "", args: list[str] = None, env_keys: list[str] = None, description: str = "") -> str:
        if self.safety_mode == "read-only":
            return "Ditolak: Agent berjalan dalam mode read-only."

        name = name.strip()
        if not name:
            return "Error: Nama server tidak boleh kosong."

        # Cek apakah nama merujuk ke preset
        if name in config.MCP_PRESETS and not command:
            preset = config.MCP_PRESETS[name]
            command = preset.get("command", "")
            args = preset.get("args", [])
            env_keys = preset.get("env_keys", [])
            description = description or preset.get("description", "")

        if not command:
            return f"Error: Command eksekusi untuk MCP '{name}' harus disediakan (atau gunakan preset: {list(config.MCP_PRESETS.keys())})."

        action_desc = f"Install MCP Server '{name}' (cmd: {command} {' '.join(args or [])})"
        if self.safety_mode != "yolo" and self.confirm_fn:
            if not self.confirm_fn(f"Apakah Anda mengizinkan: {action_desc}?"):
                return "Dibatalkan oleh pengguna."

        new_entry = {
            "command": command,
            "args": args or [],
            "enabled": True,
            "description": description or f"Server MCP {name}"
        }
        if env_keys:
            new_entry["env_keys"] = env_keys

        self.config[name] = new_entry
        config.save_mcp_config(self.config)

        # Uji koneksi langsung
        test_res = self.test_server(name)
        return f"Sukses mendaftarkan MCP '{name}'.\nHasil pengujian: {test_res}"

    def test_server(self, name: str) -> str:
        if name not in self.config:
            return f"Error: Server '{name}' tidak ada di konfigurasi."
        try:
            client = self._get_or_start_client(name)
            tools = client.list_tools()
            return f"Server '{name}' aktif dan siap. Ditemukan {len(tools)} tools: {[t.get('name') for t in tools[:8]]}"
        except Exception as e:
            return f"Peringatan: Gagal melakukan handshake dengan MCP '{name}': {e}"

    def remove_server(self, name: str) -> str:
        if self.safety_mode == "read-only":
            return "Ditolak: Agent berjalan dalam mode read-only."
        if name in self.clients:
            try:
                self.clients[name].close()
            except Exception:
                pass
            del self.clients[name]
        if name in self.config:
            del self.config[name]
            config.save_mcp_config(self.config)
            return f"Sukses menghapus server MCP '{name}'."
        return f"Server '{name}' tidak ditemukan."

    def toggle_server(self, name: str, enabled: bool) -> str:
        if name not in self.config:
            return f"Server '{name}' tidak ditemukan."
        self.config[name]["enabled"] = enabled
        config.save_mcp_config(self.config)
        state_str = "ENABLED" if enabled else "DISABLED"
        if not enabled and name in self.clients:
            self.clients[name].close()
            del self.clients[name]
        return f"Server MCP '{name}' sekarang {state_str}."

    def get_openai_tools(self) -> list[dict]:
        enabled_servers = ", ".join(self.get_server_names()) or "tidak ada"
        return [
            {
                "type": "function",
                "function": {
                    "name": "mcp_list_tools",
                    "description": f"Melihat daftar tool yang disediakan oleh server MCP tertentu. Server tersedia: [{enabled_servers}].",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "server_name": {"type": "string", "description": "Nama server MCP (contoh: 'fetch', 'chrome-devtools')"}
                        },
                        "required": ["server_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_call",
                    "description": "Menjalankan tool spesifik pada server MCP (seperti fetch url, inspect browser, query sqlite, dll).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "server_name": {"type": "string", "description": "Nama server MCP (contoh: 'fetch', 'chrome-devtools')"},
                            "tool_name": {"type": "string", "description": "Nama tool spesifik MCP"},
                            "arguments": {"type": "object", "description": "Argumen parameter untuk tool tersebut"}
                        },
                        "required": ["server_name", "tool_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "mcp_install",
                    "description": f"Menginstal dan mengaktifkan MCP server baru ke dalam sistem. Preset siap pakai: {list(config.MCP_PRESETS.keys())}.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Nama alias atau preset MCP (contoh: 'fetch', 'playwright-headless', 'sqlite')"},
                            "command": {"type": "string", "description": "Command binary (opsional jika menggunakan preset, contoh: 'npx', 'uvx')"},
                            "args": {"type": "array", "items": {"type": "string"}, "description": "Argumen command eksekusi"},
                            "description": {"type": "string", "description": "Deskripsi fungsi server MCP"}
                        },
                        "required": ["name"]
                    }
                }
            }
        ]

    def execute(self, name: str, args: dict) -> str:
        try:
            if name == "mcp_list_tools":
                server_name = args.get("server_name", "").strip()
                if not server_name:
                    return f"Error: Parameter 'server_name' wajib diisi. Pilihan: {self.get_server_names()}"
                client = self._get_or_start_client(server_name)
                tools = client.list_tools()
                if not tools:
                    return f"Server MCP '{server_name}' tidak memiliki tool aktif atau gagal memuat tool."

                # Format kompak hemat token
                lines = [f"Tools pada server MCP '{server_name}':"]
                for t in tools:
                    t_name = t.get("name", "unknown")
                    t_desc = t.get("description", "").split("\n")[0][:120]
                    params = t.get("inputSchema", {}).get("properties", {})
                    reqs = t.get("inputSchema", {}).get("required", [])
                    p_names = list(params.keys())
                    lines.append(f"- {t_name}: {t_desc} (params: {p_names}, required: {reqs})")
                return "\n".join(lines)

            elif name == "mcp_call":
                server_name = args.get("server_name", "").strip()
                tool_name = args.get("tool_name", "").strip()
                tool_args = args.get("arguments", {})

                if not server_name or not tool_name:
                    return "Error: 'server_name' dan 'tool_name' wajib diisi untuk mcp_call."

                # Safety check
                if self.safety_mode != "yolo" and self.confirm_fn:
                    prompt = f"Menjalankan MCP action '{server_name} -> {tool_name}' dengan argumen: {json.dumps(tool_args, ensure_ascii=False)[:200]}"
                    if not self.confirm_fn(f"Apakah Anda mengizinkan: {prompt}?"):
                        return "Dibatalkan oleh pengguna."

                client = self._get_or_start_client(server_name)
                return client.call_tool(tool_name, tool_args)

            elif name == "mcp_install":
                s_name = args.get("name", "").strip()
                s_cmd = args.get("command", "").strip()
                s_args = args.get("args") or []
                s_desc = args.get("description", "")
                return self.install_server(s_name, s_cmd, s_args, description=s_desc)

            else:
                return f"Error: Tool MCP '{name}' tidak dikenal."
        except Exception as e:
            return f"Error eksekusi MCP: {str(e)}"

    def close_all(self):
        for name, client in list(self.clients.items()):
            try:
                client.close()
            except Exception:
                pass
        self.clients.clear()
