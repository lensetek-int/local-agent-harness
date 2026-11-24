import os
import re
from pathlib import Path

class SkillManager:
    def __init__(self, local_skills_dir: Path, workspace_root: Path = None, confirm_fn=None, safety_mode: str = "strict"):
        self.local_skills_dir = Path(local_skills_dir).resolve()
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.confirm_fn = confirm_fn
        self.safety_mode = safety_mode.strip().lower()

    def set_safety_mode(self, mode: str):
        mode = mode.strip().lower()
        if mode in ("strict", "auto-approve", "yolo", "read-only"):
            self.safety_mode = mode

    def _get_search_dirs(self) -> list[tuple[Path, str]]:
        """Mengembalikan urutan direktori pencarian skill (prioritas: local -> workspace -> global)."""
        dirs = []
        # 1. Local skills
        if self.local_skills_dir.exists():
            dirs.append((self.local_skills_dir, "local"))

        # 2. Workspace skills (.agents/skills atau .skills)
        if self.workspace_root and self.workspace_root.exists():
            ws_agents = self.workspace_root / ".agents" / "skills"
            if ws_agents.exists():
                dirs.append((ws_agents, "workspace"))
            ws_skills = self.workspace_root / ".skills"
            if ws_skills.exists():
                dirs.append((ws_skills, "workspace"))

        # 3. Global skills (npx skills add -g dan tools CLI lainnya)
        home = Path.home()
        global_paths = [
            home / ".agents" / "skills",
            home / ".skills",
            home / ".claude" / "skills",
            home / ".codex" / "skills",
            home / ".gemini" / "antigravity" / "skills",
            home / ".config" / "agents" / "skills"
        ]
        for gp in global_paths:
            if gp.exists():
                dirs.append((gp, "global"))

        return dirs

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        """Mengekstrak frontmatter YAML tanpa dependensi eksternal."""
        meta = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                raw_front = parts[1]
                body = parts[2].strip()
                for line in raw_front.splitlines():
                    line = line.strip()
                    if ":" in line and not line.startswith("#"):
                        k, v = line.split(":", 1)
                        meta[k.strip().lower()] = v.strip().strip('"').strip("'")
        return meta, body

    def scan_skills(self) -> dict[str, dict]:
        """Memindai seluruh skill lokal, workspace, dan global (de-duplikasi berdasarkan nama)."""
        skills = {}
        for search_dir, source in self._get_search_dirs():
            try:
                for entry in search_dir.iterdir():
                    if not entry.is_dir() or entry.name.startswith("."):
                        continue
                    skill_md = entry / "SKILL.md"
                    if not skill_md.exists():
                        continue

                    slug = entry.name.lower()
                    if slug in skills:
                        continue

                    try:
                        content = skill_md.read_text(encoding="utf-8", errors="ignore")
                        meta, _ = self._parse_frontmatter(content)
                        s_name = meta.get("name") or slug
                        s_desc = meta.get("description") or f"Skill dari {source}"
                        skills[slug] = {
                            "slug": slug,
                            "name": s_name,
                            "description": s_desc,
                            "path": skill_md,
                            "source": source
                        }
                    except Exception:
                        continue
            except Exception:
                continue
        return skills

    def get_skill_prompt(self, skill_name: str) -> str | None:
        """Mengambil isi prompt SKILL.md dengan batasan 4000 karakter agar hemat context."""
        slug_target = re.sub(r"[^a-z0-9_-]", "-", skill_name.lower().strip()).strip("-")
        all_skills = self.scan_skills()

        target = None
        if slug_target in all_skills:
            target = all_skills[slug_target]
        else:
            for k, v in all_skills.items():
                if slug_target in k or slug_target in v["name"].lower():
                    target = v
                    break

        if not target:
            return None

        try:
            content = target["path"].read_text(encoding="utf-8", errors="ignore")
            _, body = self._parse_frontmatter(content)
            if len(body) > 2500:
                body = body[:2500] + "\n... [Instruksi skill diringkas untuk efisiensi context window edge model]"
            return f"[PANDUAN SKILL: {target['name']} ({target['source']})]\n{body}"
        except Exception as e:
            return f"Error membaca skill '{skill_name}': {e}"

    def read_skill(self, skill_name: str) -> str:
        """Membaca panduan instruksi dari sebuah skill."""
        p = self.get_skill_prompt(skill_name)
        if p:
            return p
        return f"Error: Skill '{skill_name}' tidak ditemukan. Gunakan search_skills untuk melihat daftar yang tersedia."

    def search_skills(self, query: str = "") -> list[dict]:
        """Mencari skill berdasarkan kata kunci."""
        all_skills = self.scan_skills()
        if not query.strip():
            return list(all_skills.values())

        q = query.lower()
        res = []
        for s in all_skills.values():
            if q in s["slug"] or q in s["name"].lower() or q in s["description"].lower():
                res.append(s)
        return res

    def create_skill(self, name: str, description: str, instructions: str) -> str:
        """Membuat skill baru di dalam folder lokal cli-agent/skills/."""
        if self.safety_mode == "read-only":
            return "Ditolak: Agent berjalan dalam mode read-only."

        slug = re.sub(r"[^a-z0-9_-]", "-", name.lower().strip()).strip("-")
        if not slug:
            return "Error: Nama skill tidak valid."

        target_folder = self.local_skills_dir / slug
        skill_file = target_folder / "SKILL.md"

        action_desc = f"Membuat skill baru '{slug}' di {skill_file}"
        if self.safety_mode != "yolo" and self.confirm_fn:
            if not self.confirm_fn(f"Apakah Anda mengizinkan: {action_desc}?"):
                return "Dibatalkan oleh pengguna."

        try:
            target_folder.mkdir(parents=True, exist_ok=True)
            content = f"---\nname: {slug}\ndescription: {description.strip()}\n---\n\n{instructions.strip()}\n"
            skill_file.write_text(content, encoding="utf-8")
            return f"Sukses membuat skill '{slug}'. Anda dapat memanggilnya kapan saja dengan ketik: `/{slug}`."
        except Exception as e:
            return f"Error membuat skill: {e}"

    def get_openai_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_skills",
                    "description": "Mencari daftar skill lokal atau global yang terpasang di sistem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Kata kunci pencarian skill (opsional, kosongkan untuk melihat semua)"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_skill",
                    "description": "Membaca panduan instruksi detail dari sebuah skill (bukan MCP server).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {"type": "string", "description": "Nama unik / slug skill (contoh: 'code-review', 'web-research')"}
                        },
                        "required": ["skill_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_skill",
                    "description": "Membuat skill custom baru dengan instruksi khusus agar dapat dipakai kembali.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Nama unik / slug skill (contoh: 'security-audit')"},
                            "description": {"type": "string", "description": "Deskripsi singkat fungsi skill"},
                            "instructions": {"type": "string", "description": "Instruksi kerja detail dalam format Markdown"}
                        },
                        "required": ["name", "description", "instructions"]
                    }
                }
            }
        ]

    def execute(self, name: str, args: dict) -> str:
        try:
            if name == "search_skills":
                q = args.get("query", "")
                results = self.search_skills(q)
                if not results:
                    return f"Tidak ditemukan skill yang cocok dengan '{q}'."
                lines = [f"Ditemukan {len(results)} skills:"]
                for s in results[:20]:
                    lines.append(f"- `/{s['slug']}` ({s['source']}): {s['description'][:90]}")
                if len(results) > 20:
                    lines.append(f"... dan {len(results) - 20} skill lainnya. Gunakan read_skill(skill_name) untuk membaca instruksinya.")
                return "\n".join(lines)

            elif name == "read_skill":
                s_name = args.get("skill_name", "")
                return self.read_skill(s_name)

            elif name == "create_skill":
                s_name = args.get("name", "")
                s_desc = args.get("description", "")
                s_inst = args.get("instructions", "")
                return self.create_skill(s_name, s_desc, s_inst)

            else:
                return f"Error: Tool skill '{name}' tidak dikenal."
        except Exception as e:
            return f"Error eksekusi skill: {str(e)}"
