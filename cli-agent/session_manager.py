"""
Lensetek Local LLM Agent Harness - Session & Chat History Manager
Provides multi-session management, persistence, context reloading, and chat history inspection.
"""
from __future__ import annotations
import os
import json
import time
from datetime import datetime
from pathlib import Path

try:
    import config
except ImportError:
    from cli_agent import config

class SessionManager:
    def __init__(self, sessions_dir: Path | str | None = None):
        if sessions_dir:
            self.sessions_dir = Path(sessions_dir)
        else:
            self.sessions_dir = config.CLI_DIR / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _get_settings(self) -> dict:
        return config.load_user_settings()

    def _save_settings(self, st: dict):
        config.save_user_settings(st)

    def get_active_session_id(self) -> str:
        """Mengambil ID session yang sedang aktif."""
        st = self._get_settings()
        sess_id = st.get("active_session_id")
        if sess_id:
            sess_file = self.sessions_dir / f"{sess_id}.json"
            if sess_file.exists():
                return sess_id

        # Fallback: ambil session terbaru jika ada, atau buat baru
        sessions = self.list_sessions()
        if sessions:
            new_id = sessions[0]["id"]
            self.set_active_session_id(new_id)
            return new_id

        new_sess = self.create_session("Default Session")
        return new_sess["id"]

    def set_active_session_id(self, session_id: str):
        """Menyimpan ID session aktif ke user_settings.json."""
        st = self._get_settings()
        st["active_session_id"] = session_id
        self._save_settings(st)

    def list_sessions(self) -> list[dict]:
        """
        Mengembalikan daftar semua session yang tersimpan,
        diurutkan dari yang paling baru diperbarui.
        """
        results = []
        if not self.sessions_dir.exists():
            return results

        for p in self.sessions_dir.glob("*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    messages = data.get("messages", [])
                    user_msgs = [m for m in messages if m.get("role") == "user"]
                    results.append({
                        "id": data.get("id", p.stem),
                        "name": data.get("name", "Untitled Session"),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "total_messages": len(messages),
                        "user_turns": len(user_msgs),
                        "model_name": data.get("model_name", "local-model"),
                        "file_path": str(p)
                    })
            except Exception:
                continue

        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return results

    def create_session(self, name: str = "", model_name: str = "") -> dict:
        """Membuat session baru dan menjadikannya sebagai session aktif."""
        now_dt = datetime.now()
        timestamp_str = now_dt.strftime("%Y%m%d_%H%M%S")
        sess_id = f"sess_{timestamp_str}"
        
        all_sess = self.list_sessions()
        if not name:
            name = f"Session #{len(all_sess) + 1}"

        iso_now = now_dt.isoformat()
        session_data = {
            "id": sess_id,
            "name": name,
            "created_at": iso_now,
            "updated_at": iso_now,
            "model_name": model_name or "local-model",
            "messages": []
        }

        file_path = self.sessions_dir / f"{sess_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        self.set_active_session_id(sess_id)
        return session_data

    def load_session(self, session_id: str) -> dict | None:
        """Membaca isi lengkap session berdasarkan ID."""
        file_path = self.sessions_dir / f"{session_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def get_active_session(self) -> dict:
        """Mengambil data lengkap session aktif saat ini."""
        sess_id = self.get_active_session_id()
        data = self.load_session(sess_id)
        if not data:
            data = self.create_session("Default Session")
        return data

    def save_turn(self, session_id: str, user_text: str, assistant_text: str, model_name: str = ""):
        """
        Menyimpan sepasang user prompt & assistant response ke riwayat session.
        Otomatis memperbarui judul session bila masih menggunakan nama default.
        """
        data = self.load_session(session_id)
        if not data:
            data = {
                "id": session_id,
                "name": "Session",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "model_name": model_name,
                "messages": []
            }

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        iso_now = datetime.now().isoformat()

        # Tambahkan giliran pesan
        data["messages"].append({
            "role": "user",
            "content": user_text,
            "timestamp": now_str
        })
        data["messages"].append({
            "role": "assistant",
            "content": assistant_text,
            "timestamp": now_str
        })

        # Smart session title naming: jika masih default dan ini giliran pertama, beri nama sesuai topik prompt
        curr_name = data.get("name", "")
        if curr_name.startswith("Session #") or curr_name in ("Default Session", "New Session", "Untitled Session"):
            clean_title = user_text.strip().replace("\n", " ")
            if len(clean_title) > 36:
                clean_title = clean_title[:33] + "..."
            if clean_title:
                data["name"] = clean_title

        data["updated_at"] = iso_now
        if model_name:
            data["model_name"] = model_name

        file_path = self.sessions_dir / f"{session_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Gagal menyimpan session turn: {e}")

    def switch_session(self, identifier: str) -> tuple[bool, str, dict | None]:
        """
        Beralih ke session yang dituju.
        Identifier bisa berupa ID session lengkap (sess_...) atau nomor indeks (1, 2, ...).
        """
        sessions = self.list_sessions()
        target_id = None

        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(sessions):
                target_id = sessions[idx]["id"]
        else:
            for s in sessions:
                if s["id"] == identifier or s["name"].lower() == identifier.lower():
                    target_id = s["id"]
                    break

        if not target_id:
            return False, f"Session '{identifier}' tidak ditemukan.", None

        sess_data = self.load_session(target_id)
        if not sess_data:
            return False, f"Gagal membaca berkas session '{target_id}'.", None

        self.set_active_session_id(target_id)
        return True, f"Beralih ke session: '{sess_data.get('name')}' ({target_id})", sess_data

    def delete_session(self, identifier: str) -> tuple[bool, str]:
        """Menghapus session tertentu."""
        sessions = self.list_sessions()
        target_id = None
        target_name = ""

        if identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(sessions):
                target_id = sessions[idx]["id"]
                target_name = sessions[idx]["name"]
        else:
            for s in sessions:
                if s["id"] == identifier or s["name"].lower() == identifier.lower():
                    target_id = s["id"]
                    target_name = s["name"]
                    break

        if not target_id:
            return False, f"Session '{identifier}' tidak ditemukan."

        file_path = self.sessions_dir / f"{target_id}.json"
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            return False, f"Gagal menghapus session: {e}"

        # Jika yang dihapus adalah session aktif, pindah ke session lain
        active_id = self._get_settings().get("active_session_id")
        if active_id == target_id:
            remaining = self.list_sessions()
            if remaining:
                self.set_active_session_id(remaining[0]["id"])
            else:
                new_s = self.create_session("Default Session")
                self.set_active_session_id(new_s["id"])

        return True, f"Session '{target_name or target_id}' berhasil dihapus."

    def rename_session(self, identifier: str | None, new_name: str) -> tuple[bool, str]:
        """
        Mengubah nama/judul session.
        identifier bisa berupa session_id, nomor urut (1, 2, ...), nama lama, atau None (sesi aktif).
        """
        sessions = self.list_sessions()
        target_id = None

        if not identifier:
            target_id = self.get_active_session_id()
        elif identifier.isdigit():
            idx = int(identifier) - 1
            if 0 <= idx < len(sessions):
                target_id = sessions[idx]["id"]
        else:
            for s in sessions:
                if s["id"] == identifier or s["name"].lower() == identifier.lower():
                    target_id = s["id"]
                    break
            if not target_id:
                # Coba langsung sebagai session_id
                target_id = identifier

        data = self.load_session(target_id)
        if not data:
            return False, f"Session '{identifier or target_id}' tidak ditemukan."

        clean_name = new_name.strip()
        if not clean_name:
            return False, "Nama sesi baru tidak boleh kosong."

        old_name = data.get("name", "Untitled")
        data["name"] = clean_name
        data["updated_at"] = datetime.now().isoformat()
        file_path = self.sessions_dir / f"{target_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True, f"Nama session berhasil diubah dari '{old_name}' menjadi: '{clean_name}'"
        except Exception as e:
            return False, f"Gagal mengubah nama session: {e}"

    def format_session_history(self, session_id: str, lang: str = "en") -> str:
        """Memformat riwayat percakapan session untuk dicetak di terminal."""
        data = self.load_session(session_id)
        if not data:
            return f"\033[31mSession '{session_id}' tidak ditemukan.\033[0m"

        s_name = data.get("name", "Untitled")
        s_created = data.get("created_at", "")[:19].replace("T", " ")
        s_updated = data.get("updated_at", "")[:19].replace("T", " ")
        msgs = data.get("messages", [])

        if lang == "id":
            h_title = "RIWAYAT PERCAKAPAN SESSION"
            lbl_msgs = "pesan"
            lbl_created = "Dibuat"
            lbl_updated = "Diperbarui"
            lbl_empty = "(Belum ada riwayat percakapan pada session ini)"
        elif lang == "cn":
            h_title = "会话对话历史记录"
            lbl_msgs = "条消息"
            lbl_created = "创建时间"
            lbl_updated = "更新时间"
            lbl_empty = "(当前会话暂无历史对话记录)"
        else:
            h_title = "SESSION CHAT HISTORY"
            lbl_msgs = "messages"
            lbl_created = "Created"
            lbl_updated = "Updated"
            lbl_empty = "(No conversation history in this session yet)"

        lines = [
            f"\033[1m\033[36m====================================================================\033[0m",
            f"\033[1m💬 {h_title}: \033[33m{s_name}\033[0m \033[2m(ID: {session_id})\033[0m",
            f"\033[2m   {lbl_created}: {s_created} | {lbl_updated}: {s_updated} | {len(msgs)} {lbl_msgs}\033[0m",
            f"\033[1m\033[36m====================================================================\033[0m"
        ]

        if not msgs:
            lines.append(f"\033[2m{lbl_empty}\033[0m")
        else:
            for idx, m in enumerate(msgs, start=1):
                role = m.get("role", "").upper()
                ts = m.get("timestamp", "")
                ts_badge = f"\033[2m[{ts}]\033[0m " if ts else ""
                content = m.get("content", "").strip()

                if role == "USER":
                    lines.append(f"\n{ts_badge}\033[1m\033[32m[USER]\033[0m:")
                    lines.append(f"  {content}")
                elif role == "ASSISTANT":
                    lines.append(f"\n{ts_badge}\033[1m\033[36m[ASSISTANT]\033[0m:")
                    lines.append(f"  {content}")

        lines.append(f"\033[36m--------------------------------------------------------------------\033[0m")
        return "\n".join(lines)
