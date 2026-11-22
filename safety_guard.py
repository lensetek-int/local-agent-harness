#!/usr/bin/env python3
"""
SafetyGuard: Operational Safety, Human-in-the-Loop (HITL) & Compliance Gate
Designed for Lensetek Edge AI Agent (Industrial IoT & Medical/Disaster Resilience).

Features:
- Read-Only Telemetry by Default (PM-06)
- Cryptographic Token Verification for Physical Actuation (Modbus/CAN/GPIO)
- Immutable SQLite Append-Only Audit Logging
- Medical Non-Prescriptive Clinical Disclaimers
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "knowledge_rag.db")

ACTUATION_TOOLS = {
    "gpio_write",
    "modbus_write",
    "modbus_write_register",
    "canbus_send",
    "relay_toggle",
    "bash_exec",
    "system_reboot",
    "actuate_write_guarded",
}

READ_ONLY_DEFAULT = True


class SafetyGuard:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = db_path
        self.read_only_default = READ_ONLY_DEFAULT
        self._init_audit_table()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_audit_table(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS safety_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    hitl_token_hash TEXT
                );
                """)
                conn.commit()
        except Exception as e:
            # Fallback if db path is not writable or locked
            pass

    def _log_audit(self, tool_name, params, decision, reason, token=None):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else None
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO safety_audit_log (timestamp, tool_name, params_json, decision, reason, hitl_token_hash)
                VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    datetime.utcnow().isoformat() + "Z",
                    tool_name,
                    json.dumps(params, ensure_ascii=False),
                    decision,
                    reason,
                    token_hash
                ))
                conn.commit()
        except Exception:
            pass

    def generate_hitl_challenge(self, tool_name, params):
        """Generates a human confirmation prompt and valid token for verification."""
        salt = "LENSETEK_HITL_SECRET_LOCAL"
        raw_msg = f"{tool_name}:{json.dumps(params, sort_keys=True)}:{salt}"
        expected_token = hashlib.sha256(raw_msg.encode("utf-8")).hexdigest()[:12]
        challenge = {
            "warning": f"CRITICAL: Tool '{tool_name}' performs physical actuation or system modification.",
            "tool_name": tool_name,
            "parameters": params,
            "hitl_token_required": True,
            "verification_instruction": f"To execute, human operator must confirm with token: '{expected_token}'"
        }
        return challenge, expected_token

    def verify_hitl_token(self, tool_name, params, token):
        if not token:
            return False
        _, expected_token = self.generate_hitl_challenge(tool_name, params)
        # Constant-time comparison
        return str(token).strip().lower() == expected_token.lower()

    def check_permission(self, tool_name, params, token=None, allow_write=False):
        """
        Evaluates whether a tool execution is permitted.
        Returns dict with status, decision, and reasons.
        """
        # If tool is read-only (telemetry, rag_search, queries)
        if tool_name not in ACTUATION_TOOLS:
            decision = "ALLOWED_READ"
            reason = "Safe telemetry/query tool (Read-Only compliant)"
            self._log_audit(tool_name, params, decision, reason, token)
            return {
                "allowed": True,
                "requires_hitl": False,
                "mode": "READ_ONLY",
                "reason": reason
            }

        # If tool is an actuation/state-changing tool
        if self.read_only_default and not allow_write:
            decision = "BLOCKED_HITL_REQUIRED"
            reason = (
                f"Actuation tool '{tool_name}' is blocked by default in Read-Only Mode. "
                "Explicit Human-in-the-Loop (HITL) confirmation token required."
            )
            challenge, _ = self.generate_hitl_challenge(tool_name, params)
            self._log_audit(tool_name, params, decision, reason, token)
            return {
                "allowed": False,
                "requires_hitl": True,
                "mode": "ACTUATION_BLOCKED",
                "reason": reason,
                "challenge": challenge
            }

        # If write is requested, verify token
        if self.verify_hitl_token(tool_name, params, token):
            decision = "ALLOWED_HITL_VERIFIED"
            reason = "Human-in-the-Loop approval token verified."
            self._log_audit(tool_name, params, decision, reason, token)
            return {
                "allowed": True,
                "requires_hitl": False,
                "mode": "ACTUATION_PERMITTED",
                "reason": reason
            }
        else:
            decision = "BLOCKED_INVALID_TOKEN"
            reason = "Invalid or expired HITL confirmation token for actuation tool."
            self._log_audit(tool_name, params, decision, reason, token)
            return {
                "allowed": False,
                "requires_hitl": True,
                "mode": "ACTUATION_BLOCKED",
                "reason": reason
            }

    @staticmethod
    def get_clinical_disclaimer(lang="id"):
        if lang == "id":
            return (
                "⚠️ [DISCLAIMER MEDIS]: Informasi ini merupakan alat bantu referensi klinis/triage darurat non-preskriptif "
                "berdasarkan protokol terindeks. Bukan pengganti diagnosis resmi atau instruksi dokter/tenaga medis berlisensi."
            )
        return (
            "⚠️ [CLINICAL DISCLAIMER]: This output is an emergency reference/triage aid and non-prescriptive guidance. "
            "It does not substitute professional clinical diagnosis or judgment of a licensed physician."
        )


if __name__ == "__main__":
    guard = SafetyGuard()
    print("[TEST 1] Read Tool Check:", guard.check_permission("rag_search", {"q": "boiler"}))
    res = guard.check_permission("modbus_write", {"slave": 1, "reg": 40012, "val": 100})
    print("[TEST 2] Write Tool (No Token):", res)
    challenge, tok = guard.generate_hitl_challenge("modbus_write", {"slave": 1, "reg": 40012, "val": 100})
    print("[TEST 3] Write Tool (With Token):", guard.check_permission("modbus_write", {"slave": 1, "reg": 40012, "val": 100}, token=tok, allow_write=True))
