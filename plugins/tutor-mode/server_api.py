"""
WebUI HTTP API Router for Lensetek Tutor Mode Plugin (/api/plugin/tutor-mode/*).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Tuple

import tutor_db


def _ensure_llm_ready(state: Any) -> Tuple[str, str]:
    if not state.server_mgr.is_healthy() and state.model_name:
        import config
        state.server_mgr.start(state.model_name, loras=config.get_active_loras())
    base_url = f"http://127.0.0.1:{state.llama_port}"
    model_name = Path(state.model_name).name if state.model_name else "local-model"
    return base_url, model_name


def handle_request(
    method: str,
    sub_path: str,
    query: Dict[str, Any],
    body: Dict[str, Any],
    state: Any,
) -> Tuple[int, Dict[str, Any]]:
    ws = Path(state.workspace_root).resolve()
    sub = sub_path.strip("/").lower()

    if method == "GET":
        if sub in ("", "status", "books"):
            return 200, {"books": tutor_db.list_books(ws)}

        if sub == "book":
            bid = int((query.get("id") or ["0"])[0] or 0)
            book = tutor_db.get_book_detail(ws, bid)
            if not book:
                return 404, {"error": "Book not found"}
            return 200, {"book": book}

        if sub == "chapter":
            cid = int((query.get("id") or ["0"])[0] or 0)
            ch = tutor_db.get_chapter_detail(ws, cid)
            if not ch:
                return 404, {"error": "Chapter not found"}
            return 200, {"chapter": ch}

        return 404, {"error": f"Unknown GET endpoint: {sub}"}

    if method == "POST":
        if sub == "ingest":
            file_path_str = str(body.get("file_path", "")).strip()
            filename = str(body.get("filename", "")).strip()
            content_b64 = str(body.get("content_base64", "")).strip()
            title = str(body.get("title", "")).strip()

            target_file: Path | None = None
            if filename and content_b64:
                safe_name = Path(filename).name
                study_dir = ws / "study_materials"
                study_dir.mkdir(parents=True, exist_ok=True)
                target_file = (study_dir / safe_name).resolve()
                raw_bytes = base64.b64decode(content_b64)
                if len(raw_bytes) > 50 * 1024 * 1024:
                    return 413, {"error": "File exceeds 50 MB limit"}
                target_file.write_bytes(raw_bytes)
            elif file_path_str:
                cand = Path(file_path_str)
                target_file = cand.resolve() if cand.is_absolute() else (ws / cand).resolve()
                try:
                    target_file.relative_to(ws)
                except ValueError:
                    return 403, {"error": "File must be inside active workspace"}
            else:
                return 400, {"error": "Provide file_path or uploaded file content"}

            try:
                book = tutor_db.ingest_book_file(ws, target_file, custom_title=title)
                return 200, {"ok": True, "book": book}
            except Exception as exc:
                return 400, {"error": str(exc)}

        if sub == "chapter/status":
            cid = int(body.get("chapter_id", 0) or 0)
            st_val = str(body.get("status", "sedang"))
            score = body.get("mastery_score")
            ok = tutor_db.update_chapter_status(ws, cid, st_val, score)
            return 200, {"ok": ok}

        if sub == "mindmap/generate":
            cid = int(body.get("chapter_id", 0) or 0)
            try:
                base_url, model_name = _ensure_llm_ready(state)
                mm = tutor_db.generate_mindmap_for_chapter(ws, cid, base_url, model_name)
                return 200, {"ok": True, "mindmap": mm}
            except Exception as exc:
                return 500, {"error": str(exc)}

        if sub == "quiz/generate":
            cid = int(body.get("chapter_id", 0) or 0)
            cnt = int(body.get("count", 3) or 3)
            try:
                base_url, model_name = _ensure_llm_ready(state)
                qs = tutor_db.generate_quiz_for_chapter(ws, cid, base_url, model_name, count=cnt)
                return 200, {"ok": True, "quizzes": qs}
            except Exception as exc:
                return 500, {"error": str(exc)}

        if sub == "quiz/answer":
            qid = int(body.get("quiz_id", 0) or 0)
            idx = int(body.get("selected_index", -1))
            try:
                res = tutor_db.answer_quiz(ws, qid, idx)
                return 200, {"ok": True, "result": res}
            except Exception as exc:
                return 400, {"error": str(exc)}

        if sub == "flashcards/generate":
            cid = int(body.get("chapter_id", 0) or 0)
            cnt = int(body.get("count", 5) or 5)
            try:
                base_url, model_name = _ensure_llm_ready(state)
                cards = tutor_db.generate_flashcards_for_chapter(ws, cid, base_url, model_name, count=cnt)
                return 200, {"ok": True, "flashcards": cards}
            except Exception as exc:
                return 500, {"error": str(exc)}

        if sub == "book/delete":
            bid = int(body.get("book_id", 0) or 0)
            ok = tutor_db.delete_book(ws, bid)
            return 200, {"ok": ok, "books": tutor_db.list_books(ws)}

    return 404, {"error": f"Unknown endpoint: {method} {sub}"}
