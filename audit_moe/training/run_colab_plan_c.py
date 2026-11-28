"""Skrip end-to-end Plan C: Unified Qwen2.5-Coder-3B-Instruct (6.480 sampel) + Benchmark 2 Lapis di Colab T4."""

import ast
from decimal import Decimal, ROUND_HALF_UP
import gc
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
import urllib.request


def sh(cmd: str) -> None:
    print(f"\n>>> {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True)


VALID_TOOLS = {
    "list_client_files",
    "inspect_excel_template",
    "write_excel_preserving_template",
    "read_document_or_ocr",
    "rwed_file",
    "run_sqlite_query",
    "verify_accounting_balance",
    "build_non_html_dashboard",
    "run_python_calc",
}


def exec_python_sandbox(code: str):
    tree = ast.parse(code, mode="exec")
    forbidden = (ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith, ast.Try, ast.ClassDef, ast.Global, ast.Nonlocal)
    for node in ast.walk(tree):
        if isinstance(node, forbidden):
            raise ValueError(f"Forbidden AST: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Forbidden dunder")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Forbidden dunder attr")
    safe_globals = {
        "__builtins__": {
            "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
            "len": len, "range": range, "int": int, "float": float, "str": str,
            "dict": dict, "list": list, "tuple": tuple,
        },
        "Decimal": Decimal,
        "ROUND_HALF_UP": ROUND_HALF_UP,
        "math": math,
        "statistics": statistics,
    }
    local_env = {}
    exec(compile(tree, "<python_calc>", "exec"), safe_globals, local_env)
    out = local_env.get("result", local_env.get("hasil"))
    if isinstance(out, Decimal):
        out = str(out)
    return out


def strip_fence(text: str) -> str:
    cleaned = text.strip()
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>", 1)[-1].strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            cleaned = "\n".join(lines[1:-1]).strip()
    return cleaned


def check_record(exp: str, raw_out: str) -> tuple[bool, str]:
    cleaned = strip_fence(raw_out)
    try:
        obj = json.loads(cleaned)
    except Exception:
        return False, "invalid_json"
    if not isinstance(obj, dict):
        return False, "not_dict"
    if exp == "expert_1_accounting":
        lines = obj.get("lines", [])
        if not isinstance(lines, list) or len(lines) < 2:
            return False, "missing_lines"
        d = sum(int(x.get("debit", 0)) for x in lines)
        c = sum(int(x.get("credit", 0)) for x in lines)
        return (d == c and d > 0), ("ok" if d == c and d > 0 else "unbalanced")
    if exp == "expert_2_audit":
        ok = "metrik" in obj and any(isinstance(v, (int, float)) for v in obj.values())
        return ok, ("ok" if ok else "missing_metrik")
    if exp == "expert_3_tax_id":
        ok = any(k in obj for k in ("jenis_pajak", "laba_fiskal", "jenis_analisis"))
        return ok, ("ok" if ok else "missing_tax_keys")
    if exp == "expert_4_agentic":
        tcs = obj.get("tool_calls", [])
        if not isinstance(tcs, list) or not tcs:
            return False, "missing_tool_calls"
        ok = all(tc.get("name") in VALID_TOOLS and isinstance(tc.get("arguments"), dict) for tc in tcs)
        return ok, ("ok" if ok else "invalid_tool_name")
    return False, "unknown"


def run_server_eval(model_path: str, samples: list[dict], port: int, python_mode: bool = False):
    cmd = ["/content/llama.cpp/build/bin/llama-server", "-m", model_path, "--host", "127.0.0.1", "--port", str(port), "-c", "2048", "-t", "2"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(45):
            time.sleep(1)
            try:
                if urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2).status == 200:
                    break
            except Exception:
                pass
        passed = 0
        details = []
        for rec in samples:
            payload = {"messages": rec["messages"][:-1], "temperature": 0.1, "max_tokens": 512}
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            out = json.loads(urllib.request.urlopen(req, timeout=240).read())["choices"][0]["message"]["content"]
            if not python_mode:
                exp = rec["expert"]
                ok, reason = check_record(exp, out)
                if ok:
                    passed += 1
                details.append([exp, ok, reason])
            else:
                cleaned = strip_fence(out)
                try:
                    obj = json.loads(cleaned)
                    tcs = obj.get("tool_calls", [])
                    if not tcs or tcs[0].get("name") != "run_python_calc":
                        details.append([False, "not_run_python_calc"])
                        continue
                    code = tcs[0]["arguments"]["code"]
                    res = exec_python_sandbox(code)
                    ok = res == rec["expected_result"]
                    if ok:
                        passed += 1
                    details.append([ok, "ok" if ok else f"mismatch:{res}!={rec['expected_result']}"])
                except Exception as exc:
                    details.append([False, f"err:{type(exc).__name__}"])
        return passed, details
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def main() -> None:
    sh("nvidia-smi")
    try:
        import unsloth  # noqa: F401
    except ImportError:
        sh("pip install -q unsloth trl peft accelerate bitsandbytes datasets huggingface_hub")

    from unsloth import FastLanguageModel
    import torch
    from datasets import load_dataset
    from huggingface_hub import snapshot_download
    from trl import SFTConfig, SFTTrainer

    merged_dir = "/content/plan_c_3b_merged"
    if not os.path.exists(merged_dir):
        print("\n=== TRAINING PLAN C (Qwen2.5-Coder-3B-Instruct, 6.480 samples) ===", flush=True)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name="unsloth/Qwen2.5-Coder-3B-Instruct-bnb-4bit",
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=True,
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            lora_alpha=16,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
            random_state=2026,
        )

        ds = load_dataset("json", data_files="/content/datasets/unified_plan_c_6480.jsonl", split="train")

        def format_chat(batch):
            texts = [tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False) for m in batch["messages"]]
            return {"text": texts}

        ds = ds.map(format_chat, batched=True)

        trainer = SFTTrainer(
            model=model,
            processing_class=tokenizer,
            train_dataset=ds,
            args=SFTConfig(
                dataset_text_field="text",
                max_length=2048,
                per_device_train_batch_size=2,
                gradient_accumulation_steps=4,
                warmup_steps=30,
                num_train_epochs=2,
                learning_rate=2e-4,
                lr_scheduler_type="cosine",
                fp16=not torch.cuda.is_bf16_supported(),
                bf16=torch.cuda.is_bf16_supported(),
                logging_steps=50,
                output_dir="/content/outputs_plan_c",
                save_strategy="no",
            ),
        )
        trainer.train()
        model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")
        del model, trainer, ds
        gc.collect()
        torch.cuda.empty_cache()

    if not os.path.exists("/content/llama.cpp"):
        sh("git clone --depth 1 https://github.com/ggml-org/llama.cpp /content/llama.cpp")
    if not os.path.exists("/content/llama.cpp/build/bin/llama-server"):
        sh("cmake -B /content/llama.cpp/build /content/llama.cpp && cmake --build /content/llama.cpp/build --target llama-quantize llama-cli llama-server -j4")

    plan_c_gguf = "/content/asadeltek-indo-tax-3b.gguf"
    if not os.path.exists(plan_c_gguf):
        sh(f"python3 /content/llama.cpp/convert_hf_to_gguf.py {merged_dir} --outfile /content/asadeltek-indo-tax-3b-f16.gguf --outtype f16")
        sh(f"/content/llama.cpp/build/bin/llama-quantize /content/asadeltek-indo-tax-3b-f16.gguf {plan_c_gguf} Q4_K_M")
        sh("rm -f /content/asadeltek-indo-tax-3b-f16.gguf")

    base_gguf = "/content/qwen2.5-coder-3b-q4_k_m.gguf"
    if not os.path.exists(base_gguf):
        snapshot_download("Qwen/Qwen2.5-Coder-3B-Instruct", local_dir="/content/qwen25_coder_3b_hf")
        sh("python3 /content/llama.cpp/convert_hf_to_gguf.py /content/qwen25_coder_3b_hf --outfile /content/qwen25-f16.gguf --outtype f16")
        sh(f"/content/llama.cpp/build/bin/llama-quantize /content/qwen25-f16.gguf {base_gguf} Q4_K_M")
        sh("rm -f /content/qwen25-f16.gguf")

    # Benchmark Lapis 1: 8 sampel identik dari eval_heldout_200.jsonl
    rows = [json.loads(l) for l in Path("/content/datasets/eval_heldout_200.jsonl").read_text().splitlines() if l.strip()]
    by_exp = {}
    for r in rows:
        by_exp.setdefault(r["expert"], []).append(r)
    experts = ["expert_1_accounting", "expert_2_audit", "expert_3_tax_id", "expert_4_agentic"]
    test_8 = [r for exp in experts for r in by_exp[exp][:2]]

    base_pass, base_det = run_server_eval(base_gguf, test_8, 8091, python_mode=False)
    planc_pass, planc_det = run_server_eval(plan_c_gguf, test_8, 8092, python_mode=False)

    # Benchmark Lapis 2: 12 sampel unseen run_python_calc (1 per domain kalkulasi)
    py_rows = [json.loads(l) for l in Path("/content/datasets/eval_python_calc_24.jsonl").read_text().splitlines() if l.strip()]
    py_12 = py_rows[:12]
    py_pass, py_det = run_server_eval(plan_c_gguf, py_12, 8093, python_mode=True)

    summary = {
        "total_std": len(test_8),
        "base_qwen25_coder_3b": {"passed": base_pass, "details": base_det},
        "plan_c_unified_3b": {"passed": planc_pass, "details": planc_det},
        "plan_c_python_exec_eval": {"passed": py_pass, "total": len(py_12), "details": py_det},
    }
    Path("/content/benchmark_results_plan_c.json").write_text(json.dumps(summary, indent=2))
    print("PLAN_C_BENCHMARK:", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
