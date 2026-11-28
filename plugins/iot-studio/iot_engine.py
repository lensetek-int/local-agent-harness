"""
Real Hardware & Sketch Engine for Lensetek IoT Studio Plugin.
Uses pyserial for real COM port discovery/monitoring, arduino-cli for real
compilation/flashing, and AST/regex analysis for interactive SVG wiring diagrams.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BOARD_PROFILES = {
    "esp32": {
        "name": "ESP32 DevKit V1",
        "fqbn": "esp32:esp32:esp32",
        "pins": ["3V3", "EN", "VP/36", "VN/39", "34", "35", "32", "33", "25", "26", "27", "14", "12", "GND", "13",
                 "23", "22", "TX0", "RX0", "21", "19", "18", "5", "17", "16", "4", "2", "15"],
    },
    "uno": {
        "name": "Arduino Uno",
        "fqbn": "arduino:avr:uno",
        "pins": ["IOREF", "RESET", "3.3V", "5V", "GND", "VIN", "A0", "A1", "A2", "A3", "A4", "A5",
                 "13", "12", "11", "10", "9", "8", "7", "6", "5", "4", "3", "2", "1/TX", "0/RX"],
    },
    "nano": {
        "name": "Arduino Nano",
        "fqbn": "arduino:avr:nano",
        "pins": ["D13", "3V3", "REF", "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "5V", "RST", "GND", "VIN",
                 "D12", "D11", "D10", "D9", "D8", "D7", "D6", "D5", "D4", "D3", "D2", "GND2", "RST2", "RX0", "TX1"],
    },
}


def get_toolchain_status() -> Dict[str, Any]:
    serial_ok = False
    try:
        import serial  # noqa: F401
        serial_ok = True
    except ImportError:
        serial_ok = False

    arduino_cli = shutil.which("arduino-cli")
    return {
        "pyserial_available": serial_ok,
        "arduino_cli_available": bool(arduino_cli),
        "arduino_cli_path": arduino_cli or "",
    }


def list_serial_ports() -> List[Dict[str, str]]:
    try:
        from serial.tools import list_ports
        ports = []
        for p in list_ports.comports():
            ports.append({
                "device": p.device,
                "description": p.description or p.device,
                "hwid": p.hwid or "",
            })
        return ports
    except Exception:
        return []


class SerialMonitorManager:
    """Thread-safe real serial port reader/writer."""

    def __init__(self):
        self._lock = threading.Lock()
        self._ser = None
        self._port = ""
        self._baud = 115200
        self._running = False
        self._lines: List[str] = []

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "connected": self._running and self._ser is not None,
                "port": self._port,
                "baudrate": self._baud,
                "buffer_len": len(self._lines),
            }

    def open_port(self, port: str, baudrate: int = 115200) -> Tuple[bool, str]:
        self.close_port()
        try:
            import serial
        except ImportError:
            return False, "pyserial is not installed (run: pip install pyserial)."

        try:
            ser = serial.Serial(port.strip(), int(baudrate), timeout=0.15)
        except Exception as exc:
            return False, f"Failed to open {port}: {exc}"

        with self._lock:
            self._ser = ser
            self._port = port.strip()
            self._baud = int(baudrate)
            self._running = True
            self._lines.append(f"[CONNECTED] {self._port} @ {self._baud} baud")

        def _reader():
            while True:
                with self._lock:
                    if not self._running or self._ser is None:
                        break
                    s_obj = self._ser
                try:
                    raw = s_obj.readline()
                    if raw:
                        txt = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                        with self._lock:
                            self._lines.append(txt)
                            if len(self._lines) > 500:
                                self._lines = self._lines[-400:]
                except Exception as exc:
                    with self._lock:
                        self._lines.append(f"[SERIAL ERROR] {exc}")
                        self._running = False
                    break
                time.sleep(0.02)

        threading.Thread(target=_reader, daemon=True).start()
        return True, f"Connected to {port} @ {baudrate}"

    def close_port(self):
        with self._lock:
            self._running = False
            if self._ser is not None:
                try:
                    self._ser.close()
                except Exception:
                    pass
                self._ser = None
                self._lines.append("[DISCONNECTED]")

    def send(self, text: str) -> Tuple[bool, str]:
        with self._lock:
            if not self._running or self._ser is None:
                return False, "Serial port is not connected."
            s_obj = self._ser
        try:
            payload = (text.rstrip("\r\n") + "\n").encode("utf-8")
            s_obj.write(payload)
            with self._lock:
                self._lines.append(f"> {text}")
            return True, "Sent"
        except Exception as exc:
            return False, f"Send failed: {exc}"

    def read_lines(self, after: int = 0) -> Dict[str, Any]:
        with self._lock:
            total = len(self._lines)
            slice_lines = self._lines[after:] if after < total else []
            return {
                "connected": self._running and self._ser is not None,
                "port": self._port,
                "lines": slice_lines,
                "next_index": total,
            }


SERIAL_MGR = SerialMonitorManager()


def list_sketch_files(workspace_root: Path) -> List[str]:
    ws = Path(workspace_root).resolve()
    found = []
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv"}
    for p in ws.rglob("*"):
        if any(part in skip for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in (".ino", ".cpp", ".c", ".h"):
            found.append(str(p.relative_to(ws)).replace("\\", "/"))
    found.sort()
    return found[:100]


def analyze_sketch_wiring(code_text: str, board: str = "esp32") -> Dict[str, Any]:
    """
    Parse real pin definitions and peripheral calls from Arduino/ESP32 C++ code
    and detect pin conflicts.
    """
    profile = BOARD_PROFILES.get(board, BOARD_PROFILES["esp32"])
    connections: List[Dict[str, str]] = []
    pin_usage: Dict[str, List[str]] = {}

    def _add_conn(comp_name: str, pin_str: str, role: str):
        clean_pin = pin_str.strip()
        if not clean_pin:
            return
        connections.append({"component": comp_name, "pin": clean_pin, "role": role})
        pin_usage.setdefault(clean_pin, []).append(comp_name)

    # 1. #define NAME PIN  or  const int NAME = PIN;
    var_to_pin: Dict[str, str] = {}
    for m in re.finditer(r"#define\s+([A-Za-z_]\w*)\s+(A?\d+|D\d+)\b", code_text):
        var_to_pin[m.group(1)] = m.group(2)
        _add_conn(m.group(1), m.group(2), "define")

    for m in re.finditer(r"(?:const\s+)?(?:int|uint8_t|byte)\s+([A-Za-z_]\w*)\s*=\s*(A?\d+|D\d+)\s*;", code_text):
        var_to_pin[m.group(1)] = m.group(2)
        _add_conn(m.group(1), m.group(2), "const")

    # 2. pinMode(PIN_OR_VAR, MODE)
    for m in re.finditer(r"pinMode\s*\(\s*([A-Za-z0-9_]+)\s*,\s*(OUTPUT|INPUT|INPUT_PULLUP)\s*\)", code_text):
        target, mode = m.group(1), m.group(2)
        resolved = var_to_pin.get(target, target)
        if not any(c["component"] == target and c["pin"] == resolved for c in connections):
            _add_conn(target, resolved, mode)

    # 3. I2C Wire.begin(SDA, SCL)
    for m in re.finditer(r"Wire\.begin\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", code_text):
        _add_conn("I2C_SDA", m.group(1), "I2C")
        _add_conn("I2C_SCL", m.group(2), "I2C")

    # 4. Servo.attach(PIN)
    for m in re.finditer(r"([A-Za-z_]\w*)\.attach\s*\(\s*([A-Za-z0-9_]+)\s*\)", code_text):
        resolved = var_to_pin.get(m.group(2), m.group(2))
        _add_conn(f"Servo:{m.group(1)}", resolved, "PWM")

    conflicts = []
    for pin, users in pin_usage.items():
        uniq = list(dict.fromkeys(users))
        if len(uniq) > 1:
            conflicts.append({"pin": pin, "components": uniq})

    return {
        "board": board,
        "board_name": profile["name"],
        "board_pins": profile["pins"],
        "connections": connections,
        "conflicts": conflicts,
    }


def run_arduino_cli(workspace_root: Path, action: str, sketch_rel: str, fqbn: str, port: str = "") -> Dict[str, Any]:
    cli_bin = shutil.which("arduino-cli")
    if not cli_bin:
        return {
            "ok": False,
            "returncode": -1,
            "output": "arduino-cli is not installed or not in PATH.\nInstall from: https://arduino.github.io/arduino-cli/latest/installation/",
        }

    ws = Path(workspace_root).resolve()
    target = (ws / sketch_rel).resolve()
    try:
        target.relative_to(ws)
    except ValueError:
        return {"ok": False, "returncode": -1, "output": "Sketch path outside workspace."}

    if not target.exists():
        return {"ok": False, "returncode": -1, "output": f"Sketch not found: {sketch_rel}"}

    sketch_dir = target.parent if target.is_file() else target
    if action == "compile":
        cmd = [cli_bin, "compile", "--fqbn", fqbn, str(sketch_dir)]
    elif action == "upload":
        if not port:
            return {"ok": False, "returncode": -1, "output": "Select a COM/Serial port before uploading."}
        cmd = [cli_bin, "upload", "-p", port, "--fqbn", fqbn, str(sketch_dir)]
    else:
        return {"ok": False, "returncode": -1, "output": f"Unknown action: {action}"}

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        combined = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "output": combined or "(no output)"}
    except Exception as exc:
        return {"ok": False, "returncode": -1, "output": str(exc)}
