"""
Entry point for Lensetek IoT Studio Plugin.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

import iot_engine

_CTX: Dict[str, Any] = {}


def on_load(context: Dict[str, Any]):
    global _CTX
    _CTX = context or {}


def _get_ws() -> Path:
    ws = _CTX.get("workspace")
    return Path(ws).resolve() if ws else Path.cwd().resolve()


def _tool_list_ports(_args: Dict[str, Any]) -> str:
    return json.dumps({
        "toolchain": iot_engine.get_toolchain_status(),
        "ports": iot_engine.list_serial_ports(),
    }, indent=2)


def _tool_analyze_wiring(args: Dict[str, Any]) -> str:
    rel = str(args.get("sketch_path", "")).strip()
    board = str(args.get("board", "esp32")).strip()
    ws = _get_ws()
    p = (ws / rel).resolve()
    try:
        p.relative_to(ws)
    except ValueError:
        return "Error: Path outside workspace."
    if not p.exists():
        return f"Error: File not found: {rel}"
    res = iot_engine.analyze_sketch_wiring(p.read_text(encoding="utf-8", errors="replace"), board=board)
    return json.dumps(res, indent=2)


def register_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "iot_list_ports",
                "description": "Detect real USB/COM serial ports and arduino-cli toolchain availability.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            "handler": _tool_list_ports,
        },
        {
            "type": "function",
            "function": {
                "name": "iot_analyze_wiring",
                "description": "Parse GPIO pins and check for pin conflicts in an Arduino/ESP32 sketch.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sketch_path": {"type": "string", "description": "Relative path to .ino or .cpp file"},
                        "board": {"type": "string", "description": "esp32, uno, or nano"},
                    },
                    "required": ["sketch_path"],
                },
            },
            "handler": _tool_analyze_wiring,
        },
    ]
