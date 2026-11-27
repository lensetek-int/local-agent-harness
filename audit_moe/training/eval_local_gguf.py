"""Evaluator lokal untuk menguji asadeltek-indo-tax-moe-5b.gguf terhadap eval_heldout_200.jsonl via llama-server."""

import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from training.validate_and_merge_jsonl import validate_record


def query_llama_server(base_url: str, messages: list[dict[str, str]], max_tokens: int = 512) -> str:
    """Mengirim request chat completion ke llama-server lokal."""
    payload = {
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _strip_think_and_fence(text: str) -> str:
    """Membersihkan blok <think>...</think> atau markdown code fence sebelum validasi JSON."""
    cleaned = text.strip()
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>", 1)[-1].strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluasi lokal GGUF terhadap eval_heldout_200.jsonl")
    parser.add_argument("--server", default="http://127.0.0.1:8080", help="URL llama-server")
    parser.add_argument("--limit", type=int, default=20, help="Jumlah sampel uji (default: 20, 5 per expert)")
    args = parser.parse_args()

    eval_path = Path(__file__).resolve().parent / "datasets" / "eval_heldout_200.jsonl"
    records = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # Ambil sampel merata per expert
    by_expert: dict[str, list[dict]] = {}
    for r in records:
        by_expert.setdefault(r["expert"], []).append(r)

    per_exp = max(1, args.limit // max(1, len(by_expert)))
    selected = []
    for exp_recs in by_expert.values():
        selected.extend(exp_recs[:per_exp])

    passed = 0
    for idx, rec in enumerate(selected, start=1):
        exp = rec["expert"]
        prompt_msgs = rec["messages"][:-1]
        raw_out = query_llama_server(args.server, prompt_msgs)
        cleaned_out = _strip_think_and_fence(raw_out)

        candidate = {"messages": prompt_msgs + [{"role": "assistant", "content": cleaned_out}]}
        ok, reason = validate_record(exp, candidate)
        status = "PASS" if ok else f"FAIL ({reason})"
        if ok:
            passed += 1
        print(f"[{idx}/{len(selected)}] {exp}: {status}")

    print(f"\nSCORE: {passed}/{len(selected)} ({round(passed / max(1, len(selected)) * 100, 1)}%)")


if __name__ == "__main__":
    main()
