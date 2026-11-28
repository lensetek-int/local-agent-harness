"""
SQLite-backed Study Engine for Lensetek Tutor Mode Plugin.
Handles real PDF/DOCX/Markdown/Text ingestion, chapter segmentation,
mastery tracking, and LLM-generated quizzes, flashcards, and mindmaps.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_tutor_db_path(workspace_root: Path) -> Path:
    db_dir = Path(workspace_root).resolve() / ".lensetek-tutor"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "tutor.db"


def get_conn(workspace_root: Path) -> sqlite3.Connection:
    db_path = get_tutor_db_path(workspace_root)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            total_pages INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            chapter_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            page_range TEXT DEFAULT '',
            status TEXT DEFAULT 'belum',
            mastery_score INTEGER DEFAULT 0,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            options_json TEXT NOT NULL,
            correct_index INTEGER NOT NULL,
            user_index INTEGER DEFAULT -1,
            is_correct INTEGER DEFAULT -1,
            explanation TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mindmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            chapter_id INTEGER DEFAULT 0,
            title TEXT NOT NULL,
            tree_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def _extract_docx_text(file_path: Path) -> str:
    with zipfile.ZipFile(file_path, "r") as zf:
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for p in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        texts = [t.text for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if t.text]
        if texts:
            paragraphs.append("".join(texts))
    return "\n\n".join(paragraphs)


def _extract_pdf_pages(file_path: Path) -> List[Tuple[int, str]]:
    pages: List[Tuple[int, str]] = []
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(file_path))
        for idx, page in enumerate(reader.pages, start=1):
            txt = (page.extract_text() or "").strip()
            if txt:
                pages.append((idx, txt))
        return pages
    except ImportError:
        pass

    try:
        import fitz  # PyMuPDF fallback if installed
        doc = fitz.open(str(file_path))
        for idx, page in enumerate(doc, start=1):
            txt = (page.get_text() or "").strip()
            if txt:
                pages.append((idx, txt))
        return pages
    except ImportError:
        raise RuntimeError("PDF reader not available. Please install 'pypdf' (pip install pypdf) or reinstall plugin.")


def _segment_text_into_chapters(text: str) -> List[Tuple[str, str, str]]:
    """Split Markdown/Plain text into (title, content, page_range) sections."""
    lines = text.splitlines()
    sections: List[Tuple[str, List[str]]] = []
    cur_title = "Introduction / Bagian Awal"
    cur_lines: List[str] = []

    heading_re = re.compile(r"^(#{1,3}\s+.+|(?:CHAPTER|BAB|BAGIAN|MODULE|UNIT)\s+\w+.*)$", re.IGNORECASE)
    for ln in lines:
        m = heading_re.match(ln.strip())
        if m and len("\n".join(cur_lines).strip()) > 120:
            sections.append((cur_title, cur_lines))
            cur_title = m.group(1).lstrip("# ").strip()[:100]
            cur_lines = []
        else:
            cur_lines.append(ln)
    if cur_lines:
        sections.append((cur_title, cur_lines))

    # If text had no headings and is very long, split by ~3500 chars
    if len(sections) == 1 and len("\n".join(sections[0][1])) > 4500:
        full = "\n".join(sections[0][1])
        chunk_sz = 3800
        out = []
        for i in range(0, len(full), chunk_sz):
            idx = (i // chunk_sz) + 1
            out.append((f"Section {idx}", full[i : i + chunk_sz], f"Part {idx}"))
        return out

    return [(t, "\n".join(ls).strip(), "") for t, ls in sections if "\n".join(ls).strip()]


def ingest_book_file(workspace_root: Path, file_path: Path, custom_title: str = "") -> Dict[str, Any]:
    """Extract real content from PDF/DOCX/MD/TXT and store structured chapters in SQLite."""
    p = Path(file_path).resolve()
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = p.suffix.lower()
    title = custom_title.strip() or p.stem.replace("_", " ").replace("-", " ").title()
    chapters_data: List[Tuple[str, str, str]] = []
    total_pages = 1

    if ext == ".pdf":
        pages = _extract_pdf_pages(p)
        total_pages = len(pages)
        if not pages:
            raise ValueError("No extractable text found in PDF (it may be a scanned image PDF).")
        # Group every 5 pages into a structured study module/chapter
        group_size = 5
        for start in range(0, len(pages), group_size):
            batch = pages[start : start + group_size]
            p_start, p_end = batch[0][0], batch[-1][0]
            first_line = next((ln.strip() for ln in batch[0][1].splitlines() if len(ln.strip()) > 4), f"Pages {p_start}-{p_end}")
            ch_title = f"Hal {p_start}-{p_end}: {first_line[:65]}"
            ch_content = "\n\n".join(f"[Page {pg}]\n{txt}" for pg, txt in batch)
            chapters_data.append((ch_title, ch_content, f"p.{p_start}-{p_end}"))
    elif ext == ".docx":
        raw = _extract_docx_text(p)
        chapters_data = _segment_text_into_chapters(raw)
        total_pages = max(1, len(chapters_data))
    else:
        raw = p.read_text(encoding="utf-8", errors="replace")
        chapters_data = _segment_text_into_chapters(raw)
        total_pages = max(1, len(chapters_data))

    if not chapters_data:
        raise ValueError("Document appears empty.")

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        rel_path = str(p.relative_to(Path(workspace_root).resolve())).replace("\\", "/")
    except ValueError:
        rel_path = str(p)

    conn = get_conn(workspace_root)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO books (title, file_path, total_pages, created_at) VALUES (?, ?, ?, ?)",
            (title, rel_path, total_pages, now_iso),
        )
        book_id = cur.lastrowid
        for idx, (c_title, c_content, p_range) in enumerate(chapters_data, start=1):
            cur.execute(
                "INSERT INTO chapters (book_id, chapter_index, title, content, page_range) VALUES (?, ?, ?, ?, ?)",
                (book_id, idx, c_title, c_content, p_range),
            )
        conn.commit()
        return get_book_detail(workspace_root, book_id)
    finally:
        conn.close()


def list_books(workspace_root: Path) -> List[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        rows = conn.execute(
            """
            SELECT b.*,
                   COUNT(c.id) AS total_chapters,
                   SUM(CASE WHEN c.status = 'paham' THEN 1 ELSE 0 END) AS completed_chapters
            FROM books b
            LEFT JOIN chapters c ON c.book_id = b.id
            GROUP BY b.id
            ORDER BY b.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_book_detail(workspace_root: Path, book_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        b = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if not b:
            return None
        chs = conn.execute(
            "SELECT id, book_id, chapter_index, title, page_range, status, mastery_score, LENGTH(content) AS char_len FROM chapters WHERE book_id = ? ORDER BY chapter_index",
            (book_id,),
        ).fetchall()
        out = dict(b)
        out["chapters"] = [dict(c) for c in chs]
        return out
    finally:
        conn.close()


def get_chapter_detail(workspace_root: Path, chapter_id: int) -> Optional[Dict[str, Any]]:
    conn = get_conn(workspace_root)
    try:
        ch = conn.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        if not ch:
            return None
        quizzes = conn.execute("SELECT * FROM quizzes WHERE chapter_id = ? ORDER BY id DESC", (chapter_id,)).fetchall()
        cards = conn.execute("SELECT * FROM flashcards WHERE chapter_id = ? ORDER BY id DESC", (chapter_id,)).fetchall()
        mm = conn.execute("SELECT * FROM mindmaps WHERE chapter_id = ? ORDER BY id DESC LIMIT 1", (chapter_id,)).fetchone()

        q_list = []
        for q in quizzes:
            qd = dict(q)
            try:
                qd["options"] = json.loads(qd["options_json"])
            except Exception:
                qd["options"] = []
            q_list.append(qd)

        mm_obj = None
        if mm:
            mm_obj = dict(mm)
            try:
                mm_obj["tree"] = json.loads(mm_obj["tree_json"])
            except Exception:
                mm_obj["tree"] = None

        out = dict(ch)
        out["quizzes"] = q_list
        out["flashcards"] = [dict(c) for c in cards]
        out["mindmap"] = mm_obj
        return out
    finally:
        conn.close()


def update_chapter_status(workspace_root: Path, chapter_id: int, status: str, mastery_score: Optional[int] = None) -> bool:
    clean_st = status.lower().strip()
    if clean_st not in ("belum", "sedang", "paham"):
        clean_st = "sedang"
    conn = get_conn(workspace_root)
    try:
        if mastery_score is not None:
            conn.execute("UPDATE chapters SET status = ?, mastery_score = ? WHERE id = ?", (clean_st, int(mastery_score), chapter_id))
        else:
            conn.execute("UPDATE chapters SET status = ? WHERE id = ?", (clean_st, chapter_id))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_book(workspace_root: Path, book_id: int) -> bool:
    conn = get_conn(workspace_root)
    try:
        cur = conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _call_local_llm(base_url: str, model_name: str, system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": model_name or "local-model",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1400,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def _extract_json_block(text: str) -> Any:
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if m:
        cleaned = m.group(1).strip()
    for start_ch, end_ch in (("{", "}"), ("[", "]")):
        s_idx = cleaned.find(start_ch)
        e_idx = cleaned.rfind(end_ch)
        if s_idx != -1 and e_idx > s_idx:
            try:
                return json.loads(cleaned[s_idx : e_idx + 1])
            except Exception:
                continue
    return json.loads(cleaned)


def _fallback_mindmap_from_text(title: str, content: str) -> Dict[str, Any]:
    """Build a deterministic hierarchical mindmap directly from real chapter sentences/headings."""
    lines = [ln.strip() for ln in content.splitlines() if len(ln.strip()) > 6 and not ln.strip().startswith("[Page")]
    children = []
    for ln in lines[:6]:
        short = ln.lstrip("#*- ").strip()
        if len(short) > 48:
            short = short[:45] + "..."
        children.append({"label": short, "children": []})
    if not children:
        children = [{"label": "Core Concepts", "children": []}]
    return {"label": title[:40], "children": children}


def generate_mindmap_for_chapter(
    workspace_root: Path,
    chapter_id: int,
    llm_base_url: str,
    model_name: str = "local-model",
) -> Dict[str, Any]:
    ch = get_chapter_detail(workspace_root, chapter_id)
    if not ch:
        raise ValueError("Chapter not found")

    excerpt = ch["content"][:4500]
    sys_p = (
        "You are a structured study assistant. Output ONLY valid JSON representing a hierarchical mindmap tree: "
        '{"label": "Main Topic", "children": [{"label": "Subtopic", "children": [{"label": "Detail"}]}]}. '
        "Keep node labels concise (max 6 words). Create 3 to 5 main branches with 2 to 3 child nodes each."
    )
    usr_p = f"Chapter Title: {ch['title']}\n\nStudy Material:\n{excerpt}\n\nGenerate the JSON mindmap tree now."

    tree = None
    try:
        raw = _call_local_llm(llm_base_url, model_name, sys_p, usr_p)
        parsed = _extract_json_block(raw)
        if isinstance(parsed, dict) and "label" in parsed:
            tree = parsed
    except Exception:
        tree = None

    if tree is None:
        tree = _fallback_mindmap_from_text(ch["title"], ch["content"])

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = get_conn(workspace_root)
    try:
        conn.execute("DELETE FROM mindmaps WHERE chapter_id = ?", (chapter_id,))
        conn.execute(
            "INSERT INTO mindmaps (book_id, chapter_id, title, tree_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            (ch["book_id"], chapter_id, ch["title"], json.dumps(tree, ensure_ascii=False), now_iso),
        )
        conn.commit()
        return {"title": ch["title"], "tree": tree, "updated_at": now_iso}
    finally:
        conn.close()


def generate_quiz_for_chapter(
    workspace_root: Path,
    chapter_id: int,
    llm_base_url: str,
    model_name: str = "local-model",
    count: int = 3,
) -> List[Dict[str, Any]]:
    ch = get_chapter_detail(workspace_root, chapter_id)
    if not ch:
        raise ValueError("Chapter not found")

    excerpt = ch["content"][:4500]
    sys_p = (
        f"You are a strict tutor. Generate {count} multiple-choice quiz questions strictly grounded in the provided study text. "
        'Output ONLY a JSON array: [{"question": "...", "options": ["A...", "B...", "C...", "D..."], "correct_index": 0, "explanation": "..."}].'
    )
    usr_p = f"Chapter: {ch['title']}\n\nText:\n{excerpt}"

    raw = _call_local_llm(llm_base_url, model_name, sys_p, usr_p)
    items = _extract_json_block(raw)
    if not isinstance(items, list) or not items:
        raise ValueError("Model did not return valid quiz JSON list.")

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = get_conn(workspace_root)
    saved = []
    try:
        for item in items[:count]:
            q_text = str(item.get("question", "")).strip()
            opts = [str(o) for o in item.get("options", [])][:4]
            c_idx = int(item.get("correct_index", 0) or 0)
            expl = str(item.get("explanation", "")).strip()
            if not q_text or len(opts) < 2:
                continue
            cur = conn.execute(
                "INSERT INTO quizzes (chapter_id, question, options_json, correct_index, explanation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (chapter_id, q_text, json.dumps(opts, ensure_ascii=False), c_idx, expl, now_iso),
            )
            saved.append({
                "id": cur.lastrowid,
                "chapter_id": chapter_id,
                "question": q_text,
                "options": opts,
                "correct_index": c_idx,
                "user_index": -1,
                "is_correct": -1,
                "explanation": expl,
            })
        conn.commit()
        return saved
    finally:
        conn.close()


def answer_quiz(workspace_root: Path, quiz_id: int, selected_index: int) -> Dict[str, Any]:
    conn = get_conn(workspace_root)
    try:
        q = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
        if not q:
            raise ValueError("Quiz not found")
        is_ok = 1 if int(selected_index) == int(q["correct_index"]) else 0
        conn.execute("UPDATE quizzes SET user_index = ?, is_correct = ? WHERE id = ?", (int(selected_index), is_ok, quiz_id))

        # Recalculate chapter mastery from answered quizzes
        stats = conn.execute(
            "SELECT COUNT(*) AS tot, SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS ok FROM quizzes WHERE chapter_id = ? AND is_correct >= 0",
            (q["chapter_id"],),
        ).fetchone()
        tot = stats["tot"] or 0
        ok_cnt = stats["ok"] or 0
        score = int(round((ok_cnt / tot) * 100)) if tot > 0 else 0
        new_status = "paham" if (tot >= 2 and score >= 80) else "sedang"
        conn.execute("UPDATE chapters SET mastery_score = ?, status = ? WHERE id = ?", (score, new_status, q["chapter_id"]))
        conn.commit()
        return {
            "quiz_id": quiz_id,
            "is_correct": bool(is_ok),
            "correct_index": int(q["correct_index"]),
            "explanation": q["explanation"],
            "mastery_score": score,
        }
    finally:
        conn.close()


def generate_flashcards_for_chapter(
    workspace_root: Path,
    chapter_id: int,
    llm_base_url: str,
    model_name: str = "local-model",
    count: int = 5,
) -> List[Dict[str, Any]]:
    ch = get_chapter_detail(workspace_root, chapter_id)
    if not ch:
        raise ValueError("Chapter not found")

    excerpt = ch["content"][:4500]
    sys_p = (
        f"Extract {count} key study flashcards from the text. "
        'Output ONLY a JSON array: [{"front": "Concept / Question", "back": "Concise accurate answer"}].'
    )
    usr_p = f"Chapter: {ch['title']}\n\nText:\n{excerpt}"
    raw = _call_local_llm(llm_base_url, model_name, sys_p, usr_p)
    items = _extract_json_block(raw)
    if not isinstance(items, list) or not items:
        raise ValueError("Model did not return valid flashcards JSON list.")

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn = get_conn(workspace_root)
    saved = []
    try:
        for item in items[:count]:
            fr = str(item.get("front", "")).strip()
            bk = str(item.get("back", "")).strip()
            if not fr or not bk:
                continue
            cur = conn.execute(
                "INSERT INTO flashcards (chapter_id, front, back, created_at) VALUES (?, ?, ?, ?)",
                (chapter_id, fr, bk, now_iso),
            )
            saved.append({"id": cur.lastrowid, "chapter_id": chapter_id, "front": fr, "back": bk})
        conn.commit()
        return saved
    finally:
        conn.close()
