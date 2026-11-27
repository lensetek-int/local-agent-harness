"""Builder resmi dataset distilasi 6.000 latih (1.500/expert) + 200 eval held-out (zero overlap)."""

import argparse
import json
from pathlib import Path
import random
import sys
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from training.teacher_corpus import (
    sample_expert_1,
    sample_expert_2,
    sample_expert_3,
    sample_expert_4,
)
from training.validate_and_merge_jsonl import validate_record

OUTPUT_DIR = Path(__file__).resolve().parent / "datasets"

SAMPLERS: dict[str, Callable[[int, random.Random], dict[str, Any]]] = {
    "expert_1_accounting": sample_expert_1,
    "expert_2_audit": sample_expert_2,
    "expert_3_tax_id": sample_expert_3,
    "expert_4_agentic": sample_expert_4,
}


def build_unique_split(
    expert_name: str,
    sampler: Callable[[int, random.Random], dict[str, Any]],
    train_count: int,
    eval_count: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Menghasilkan sampel train & eval yang 100% unik, tervalidasi, dan zero overlap."""
    rng = random.Random(seed)
    seen_prompts: set[str] = set()
    collected: list[dict[str, Any]] = []
    target_total = train_count + eval_count
    idx = 0
    max_attempts = target_total * 10

    while len(collected) < target_total and idx < max_attempts:
        rec = sampler(idx, rng)
        idx += 1
        ok, reason = validate_record(expert_name, rec)
        if not ok:
            raise RuntimeError(f"Sampler {expert_name} menghasilkan record tidak valid: {reason}")
        prompt_key = rec["messages"][-2]["content"].strip()
        if prompt_key in seen_prompts:
            continue
        seen_prompts.add(prompt_key)
        collected.append(rec)

    if len(collected) < target_total:
        raise RuntimeError(f"Gagal mencapai {target_total} sampel unik untuk {expert_name} (tercapai {len(collected)})")

    rng.shuffle(collected)
    return collected[:train_count], collected[train_count:target_total]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 6.000 train + 200 held-out eval dataset untuk 4-Expert MoE")
    parser.add_argument("--train-per-expert", type=int, default=1500)
    parser.add_argument("--eval-per-expert", type=int, default=50)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_eval: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {"experts": {}, "eval_heldout_total": 0}

    for offset, (expert_name, sampler) in enumerate(SAMPLERS.items()):
        train_recs, eval_recs = build_unique_split(
            expert_name=expert_name,
            sampler=sampler,
            train_count=args.train_per_expert,
            eval_count=args.eval_per_expert,
            seed=args.seed + offset * 101,
        )
        train_path = OUTPUT_DIR / f"{expert_name}.jsonl"
        train_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in train_recs) + "\n",
            encoding="utf-8",
        )
        for ev in eval_recs:
            all_eval.append({"expert": expert_name, **ev})
        manifest["experts"][expert_name] = {
            "train_count": len(train_recs),
            "eval_count": len(eval_recs),
            "file": str(train_path.name),
        }
        print(f"[OK] {expert_name}: train={len(train_recs)}, eval={len(eval_recs)} -> {train_path}")

    eval_path = OUTPUT_DIR / "eval_heldout_200.jsonl"
    eval_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in all_eval) + "\n",
        encoding="utf-8",
    )
    manifest["eval_heldout_total"] = len(all_eval)
    manifest["eval_file"] = eval_path.name

    manifest_path = OUTPUT_DIR / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] Held-out eval ({len(all_eval)} records) -> {eval_path}")
    print(f"[OK] Manifest -> {manifest_path}")


if __name__ == "__main__":
    main()
