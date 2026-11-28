"""
WebUI HTTP API Router for Lensetek IoT Studio Plugin (/api/plugin/iot-studio/*).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import iot_engine


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
        if sub in ("", "status"):
            return 200, {
                "toolchain": iot_engine.get_toolchain_status(),
                "ports": iot_engine.list_serial_ports(),
                "sketches": iot_engine.list_sketch_files(ws),
                "serial": iot_engine.SERIAL_MGR.status(),
                "boards": {k: {"name": v["name"], "fqbn": v["fqbn"]} for k, v in iot_engine.BOARD_PROFILES.items()},
            }

        if sub == "file":
            rel = (query.get("path") or [""])[0].strip()
            if not rel:
                return 400, {"error": "Missing path"}
            target = (ws / rel).resolve()
            try:
                target.relative_to(ws)
            except ValueError:
                return 403, {"error": "Access denied outside workspace"}
            if not target.exists() or not target.is_file():
                return 404, {"error": "Sketch file not found"}
            return 200, {"path": rel, "content": target.read_text(encoding="utf-8", errors="replace")}

        if sub == "serial/read":
            after = int((query.get("after") or ["0"])[0] or 0)
            return 200, iot_engine.SERIAL_MGR.read_lines(after=after)

        return 404, {"error": f"Unknown GET endpoint: {sub}"}

    if method == "POST":
        if sub == "file/save":
            rel = str(body.get("path", "")).strip()
            content = str(body.get("content", ""))
            if not rel:
                return 400, {"error": "Missing path"}
            target = (ws / rel).resolve()
            try:
                target.relative_to(ws)
            except ValueError:
                return 403, {"error": "Access denied outside workspace"}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return 200, {"ok": True, "path": rel}

        if sub == "wiring/analyze":
            code = str(body.get("code", ""))
            board = str(body.get("board", "esp32"))
            return 200, {"ok": True, "wiring": iot_engine.analyze_sketch_wiring(code, board=board)}

        if sub in ("compile", "upload"):
            sketch = str(body.get("sketch", "")).strip()
            board = str(body.get("board", "esp32"))
            fqbn = iot_engine.BOARD_PROFILES.get(board, iot_engine.BOARD_PROFILES["esp32"])["fqbn"]
            port = str(body.get("port", "")).strip()
            res = iot_engine.run_arduino_cli(ws, sub, sketch, fqbn, port=port)
            return 200, res

        if sub == "serial/open":
            port = str(body.get("port", "")).strip()
            baud = int(body.get("baudrate", 115200) or 115200)
            ok, msg = iot_engine.SERIAL_MGR.open_port(port, baud)
            return (200 if ok else 400), {"ok": ok, "message": msg}

        if sub == "serial/close":
            iot_engine.SERIAL_MGR.close_port()
            return 200, {"ok": True}

        if sub == "serial/send":
            txt = str(body.get("text", ""))
            ok, msg = iot_engine.SERIAL_MGR.send(txt)
            return (200 if ok else 400), {"ok": ok, "message": msg}

    return 404, {"error": f"Unknown endpoint: {method} {sub}"}
