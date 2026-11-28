"""
Entry point for Lensetek Tutor Mode Plugin.
Registers workspace study tools for the CLI & WebUI agent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import tutor_db

_CTX: Dict[str, Any] = {}


def on_load(context: Dict[str, Any]):
    global _CTX
    _CTX = context or {}


def _get_ws() -> Path:
    ws = _CTX.get("workspace")
    if ws:
        return Path(ws).resolve()
    return Path.cwd().resolve()


def _tool_tutor_list_books(_args: Dict[str, Any]) -> str:
    books = tutor_db.list_books(_get_ws())
    if not books:
        return "No study books ingested yet in this project."
    return json.dumps(books, indent=2, ensure_ascii=False)


def _tool_tutor_ingest_book(args: Dict[str, Any]) -> str:
    rel_path = str(args.get("file_path", "")).strip()
    title = str(args.get("title", "")).strip()
    if not rel_path:
        return "Error: file_path is required."
    ws = _get_ws()
    target = (ws / rel_path).resolve()
    try:
        target.relative_to(ws)
    except ValueError:
        return "Error: Access denied outside workspace."
    book = tutor_db.ingest_book_file(ws, target, custom_title=title)
    return json.dumps({
        "book_id": book["id"],
        "title": book["title"],
        "total_chapters": len(book.get("chapters", [])),
    }, indent=2, ensure_ascii=False)


def register_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "tutor_list_books",
                "description": "List all ingested study books and chapter mastery progress in Tutor Mode SQLite.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            "handler": _tool_tutor_list_books,
        },
        {
            "type": "function",
            "function": {
                "name": "tutor_ingest_book",
                "description": "Ingest a PDF, DOCX, Markdown, or text book from the workspace into Tutor Mode SQLite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Relative path to PDF/DOCX/MD/TXT in workspace"},
                        "title": {"type": "string", "description": "Optional custom book title"},
                    },
                    "required": ["file_path"],
                },
            },
            "handler": _tool_tutor_ingest_book,
        },
    ]
