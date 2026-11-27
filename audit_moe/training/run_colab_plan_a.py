"""Skrip end-to-end Plan A untuk dieksekusi di Google Colab T4 via `colab exec -f`."""

import gc
import json
import os
from pathlib import Path
import random
import shutil
import subprocess


def sh(cmd: str) -> None:
    print(f"\n>>> {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True)


def main() -> None:
    sh("nvidia-smi")
    try:
        import unsloth  # noqa: F401
        import mergekit  # noqa: F401
    except ImportError:
        sh("pip install -q unsloth trl peft accelerate bitsandbytes datasets mergekit pyyaml huggingface_hub")

    from unsloth import FastLanguageModel
    import torch
    from datasets import Dataset, load_dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )
    from trl import SFTConfig, SFTTrainer
    import yaml

    experts = [
        "expert_1_accounting",
        "expert_2_audit",
        "expert_3_tax_id",
        "expert_4_agentic",
    ]

    # 1. Train 4 Experts
    for expert_name in experts:
        merged_out = f"/content/experts/{expert_name}"
        lora_out = f"/content/loras/{expert_name}"
        if os.path.exists(merged_out):
            print(f"[SKIP] {expert_name} sudah ada", flush=True)
            continue

        print(f"\n=== TRAINING {expert_name} ===", flush=True)
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name="unsloth/Qwen3-1.7B-unsloth-bnb-4bit",
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

        ds = load_dataset("json", data_files=f"/content/datasets/{expert_name}.jsonl", split="train")

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
                warmup_steps=15,
                num_train_epochs=2,
                learning_rate=2e-4,
                fp16=not torch.cuda.is_bf16_supported(),
                bf16=torch.cuda.is_bf16_supported(),
                logging_steps=25,
                output_dir=f"/content/outputs/{expert_name}",
                save_strategy="no",
            ),
        )
        trainer.train()

        model.save_pretrained(lora_out)
        model.save_pretrained_merged(merged_out, tokenizer, save_method="merged_16bit")
        shutil.rmtree(f"/content/outputs/{expert_name}", ignore_errors=True)

        del model, trainer, ds
        gc.collect()
        torch.cuda.empty_cache()

    # 2. MergeKit MoE
    moe_cfg = {
        "base_model": "/content/experts/expert_1_accounting",
        "gate_mode": "cheap_embed",
        "lazy_unpickle": True,
        "dtype": "float16",
        "experts_per_token": 2,
        "experts": [
            {
                "source_model": "/content/experts/expert_1_accounting",
                "positive_prompts": [
                    "Buat jurnal umum dan jurnal penyesuaian sesuai SAK, SAK-EP, atau PSAP BUMD.",
                    "Petakan setoran LPP loket dan rekap DRD tagihan air ke Chart of Accounts (CoA).",
                    "Buat jurnal majemuk pembayaran jasa konsultan termasuk PPN Masukan dan potongan PPh 23.",
                    "Susun Neraca Lajur, Buku Besar, Laba Rugi, Neraca, dan Arus Kas.",
                ],
            },
            {
                "source_model": "/content/experts/expert_2_audit",
                "positive_prompts": [
                    "Hitung EBITDA, EBITDA Margin, dan prosedur audit substantif aset tetap.",
                    "Susun analisis varians RKAP pendapatan dan beban operasional.",
                    "Buat proyeksi keuangan proforma, rekonsiliasi bank, Current Ratio, DER, dan DSCR.",
                    "Tetapkan Materialitas Audit SA 320 dan buat Kertas Kerja Audit (KKA).",
                ],
            },
            {
                "source_model": "/content/experts/expert_3_tax_id",
                "positive_prompts": [
                    "Hitung PPN non-mewah tarif 12% atas DPP Nilai Lain 11/12 sesuai PMK 131/2024.",
                    "Tentukan tarif dan pemotongan PPh Pasal 23, PPh 22, PPh 4(2) Final, dan PPh 21 TER.",
                    "Susun rekonsiliasi koreksi fiskal positif dan negatif untuk PPh Badan 22%.",
                    "Lakukan ekualisasi omzet SPT PPh Badan terhadap DPP SPT Masa PPN.",
                ],
            },
            {
                "source_model": "/content/experts/expert_4_agentic",
                "positive_prompts": [
                    "Scan daftar file keuangan klien dan inspeksi template Excel (.xls/.xlsx).",
                    "Tulis jurnal ke template Excel baru tanpa merusak rumus dan jalankan balance gate.",
                    "Baca DOCX/PDF/OCR, jalankan query SQLite3 SELECT, dan hitung pakai run_python_calc.",
                    "Bangun dashboard non-HTML dan jalankan RWED file aman dalam sandbox.",
                ],
            },
        ],
    }
    Path("/content/mergekit_moe_3b.yaml").write_text(yaml.safe_dump(moe_cfg, allow_unicode=True), encoding="utf-8")
    if not os.path.exists("/content/audit_moe_merged"):
        sh("mergekit-moe /content/mergekit_moe_3b.yaml /content/audit_moe_merged --copy-tokenizer --allow-crimes")
    else:
        print("[SKIP] /content/audit_moe_merged sudah ada", flush=True)

    # 3. Router Calibration (train mlp.gate.weight only)
    print("\n=== ROUTER CALIBRATION ===", flush=True)
    calib_samples = []
    for exp in experts:
        rows = [json.loads(line) for line in Path(f"/content/datasets/{exp}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        calib_samples.extend(rows[:150])
    random.Random(2026).shuffle(calib_samples)

    tok = AutoTokenizer.from_pretrained("/content/audit_moe_merged")
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def tokenize_fn(row):
        txt = tok.apply_chat_template(row["messages"], tokenize=False, add_generation_prompt=False)
        enc = tok(txt, truncation=True, max_length=384)
        enc["labels"] = enc["input_ids"].copy()
        return enc

    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    calib_ds = Dataset.from_list(calib_samples).map(tokenize_fn, remove_columns=["messages"])
    moe_model = AutoModelForCausalLM.from_pretrained(
        "/content/audit_moe_merged",
        torch_dtype=torch.float16,
        device_map="auto",
        max_memory={0: "11GiB", "cpu": "12GiB"},
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

    router_trainer = Trainer(
        model=moe_model,
        args=TrainingArguments(
            output_dir="/content/router_calib_out",
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            num_train_epochs=1,
            learning_rate=5e-4,
            fp16=True,
            logging_steps=15,
            save_strategy="no",
        ),
        train_dataset=calib_ds,
        data_collator=DataCollatorForLanguageModeling(tok, mlm=False),
    )
    router_trainer.train()
    for name, param in moe_model.named_parameters():
        if name.endswith("mlp.gate.weight"):
            param.data = param.data.half()
    moe_model.save_pretrained("/content/audit_moe_calibrated")
    tok.save_pretrained("/content/audit_moe_calibrated")

    del moe_model, router_trainer, calib_ds
    gc.collect()
    torch.cuda.empty_cache()

    # 4. Build llama.cpp & Convert -> Quantize GGUF
    if not os.path.exists("/content/llama.cpp"):
        sh("git clone --depth 1 https://github.com/ggml-org/llama.cpp /content/llama.cpp")
    sh("cmake -B /content/llama.cpp/build /content/llama.cpp && cmake --build /content/llama.cpp/build --target llama-quantize llama-cli -j4")
    sh("python3 /content/llama.cpp/convert_hf_to_gguf.py /content/audit_moe_calibrated --outfile /content/asadeltek-indo-tax-moe-5b-f16.gguf --outtype f16")
    sh("/content/llama.cpp/build/bin/llama-quantize /content/asadeltek-indo-tax-moe-5b-f16.gguf /content/asadeltek-indo-tax-moe-5b.gguf Q4_K_M")
    sh("rm -f /content/asadeltek-indo-tax-moe-5b-f16.gguf")
    sh('/content/llama.cpp/build/bin/llama-cli -m /content/asadeltek-indo-tax-moe-5b.gguf -p "Hitung PPN non-mewah PMK 131/2024 atas DPP Rp 100.000.000 dalam JSON:" -n 160 --single-turn')
    print("\n=== PLAN A SELESAI ===", flush=True)


if __name__ == "__main__":
    main()
