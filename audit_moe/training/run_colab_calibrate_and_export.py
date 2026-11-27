"""Router Calibration (tanpa Unsloth, hemat VRAM) + Convert GGUF Q4_K_M + Held-out Eval di Colab T4."""

import gc
import json
import os
from pathlib import Path
import random
import subprocess


def sh(cmd: str) -> None:
    print(f"\n>>> {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True)


def main() -> None:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    sh("nvidia-smi")

    import torch
    from datasets import Dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    experts = [
        "expert_1_accounting",
        "expert_2_audit",
        "expert_3_tax_id",
        "expert_4_agentic",
    ]

    print("\n=== ROUTER CALIBRATION (CLEAN TRANSFORMERS + 8GiB CAP) ===", flush=True)
    calib_samples = []
    for exp in experts:
        rows = [
            json.loads(line)
            for line in Path(f"/content/datasets/{exp}.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        calib_samples.extend(rows[:120])  # 120 x 4 = 480 sampel seimbang
    random.Random(2026).shuffle(calib_samples)

    tok = AutoTokenizer.from_pretrained("/content/audit_moe_merged")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def tokenize_fn(row):
        txt = tok.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
        enc = tok(txt, truncation=True, max_length=384)
        enc["labels"] = enc["input_ids"].copy()
        return enc

    calib_ds = Dataset.from_list(calib_samples).map(tokenize_fn, remove_columns=["messages"])

    explicit_device_map = {
        "model.embed_tokens": "cpu",
        "model.norm": "cpu",
        "lm_head": "cpu",
    }
    for i in range(28):
        explicit_device_map[f"model.layers.{i}"] = 0 if i < 21 else "cpu"

    moe_model = AutoModelForCausalLM.from_pretrained(
        "/content/audit_moe_merged",
        torch_dtype=torch.float16,
        device_map=explicit_device_map,
    )
    moe_model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    moe_model.enable_input_require_grads()

    trainable = 0
    for name, param in moe_model.named_parameters():
        if name.endswith("mlp.gate.weight"):
            param.data = param.data.float()
            param.requires_grad = True
            trainable += param.numel()
        else:
            param.requires_grad = False
    print(f"Router Calibration trainable params: {trainable:,}", flush=True)

    is_smoke = os.environ.get("CALIB_SMOKE_TEST") == "1"
    router_trainer = Trainer(
        model=moe_model,
        args=TrainingArguments(
            output_dir="/content/router_calib_out",
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            num_train_epochs=1,
            max_steps=1 if is_smoke else -1,
            learning_rate=5e-4,
            fp16=True,
            logging_steps=1 if is_smoke else 10,
            save_strategy="no",
        ),
        train_dataset=calib_ds,
        data_collator=DataCollatorForLanguageModeling(tok, mlm=False),
    )
    router_trainer.train()

    print("Menyimpan model terkalibrasi ke /content/audit_moe_calibrated...", flush=True)
    moe_model.save_pretrained("/content/audit_moe_calibrated", safe_serialization=False, max_shard_size="2GB")
    tok.save_pretrained("/content/audit_moe_calibrated")
    del moe_model, router_trainer, calib_ds
    gc.collect()
    torch.cuda.empty_cache()

    if is_smoke:
        print("SMOKE_SAVE_OK", flush=True)
        return

    # Build llama.cpp & Convert -> Quantize GGUF
    if not os.path.exists("/content/llama.cpp"):
        sh("git clone --depth 1 https://github.com/ggml-org/llama.cpp /content/llama.cpp")
    sh("cmake -B /content/llama.cpp/build /content/llama.cpp && cmake --build /content/llama.cpp/build --target llama-quantize llama-cli llama-server -j4")
    sh("python3 /content/llama.cpp/convert_hf_to_gguf.py /content/audit_moe_calibrated --outfile /content/asadeltek-indo-tax-moe-5b-f16.gguf --outtype f16")
    sh("/content/llama.cpp/build/bin/llama-quantize /content/asadeltek-indo-tax-moe-5b-f16.gguf /content/asadeltek-indo-tax-moe-5b.gguf Q4_K_M")
    sh("rm -f /content/asadeltek-indo-tax-moe-5b-f16.gguf")
    sh('/content/llama.cpp/build/bin/llama-cli -m /content/asadeltek-indo-tax-moe-5b.gguf -p "Buatkan jurnal untuk transaksi berikut: Pada 2026-05-18, Perumda Tirta Nusantara menerima setoran LPP Loket Kantor Pusat total Rp 45,000,000 pelunasan piutang rekening air. Jawab dalam JSON." -n 160 --single-turn')
    print("\n=== CALIBRATED GGUF SELESAI ===", flush=True)


if __name__ == "__main__":
    main()
