#!/usr/bin/env python3
"""
Lensetek Edge-Loop-3B: Cloud Fine-Tuning Script for RunPod (RTX 4090 / A100 / H100)
Utilizes Unsloth for 2x faster training and 70% less memory usage.

Budget Estimation:
- Hardware: RunPod RTX 4090 (24 GB VRAM) @ ~$0.34/hour
- Training duration for 3,000 samples: ~1.5 - 2.0 hours
- Total cost: ~$0.68 - $1.00 USD!
"""

import os
import sys
import torch

def main():
    print("=" * 65)
    print(" 🚀 LENSETEK EDGE-LOOP-3B: UNSLOTH RUNPOD TRAINING PIPELINE")
    print("=" * 65)

    # Check for Hugging Face Token
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("[WARNING] 'HF_TOKEN' environment variable is not set.")
        print("          You will be prompted before pushing checkpoints to Hugging Face.")
    else:
        print("[INFO] HF_TOKEN detected from environment.")

    try:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import load_dataset
        from unsloth.chat_templates import get_chat_template
    except ImportError:
        print("[ERROR] Unsloth or dependencies not found.")
        print("Run the following installation command first:")
        print("pip install --no-deps \"unsloth[cu121-ampere-torch240] @ git+https://github.com/unslothai/unsloth.git\"")
        print("pip install datasets trl bitsandbytes transformers accelerate")
        sys.exit(1)

    max_seq_length = 4096
    dtype = None # Auto detect: Float16 or Bfloat16
    load_in_4bit = True # 4-bit QLoRA for fast training in 24GB VRAM

    print(f"\n[1/5] Loading Base Model: Qwen/Qwen2.5-3B-Instruct (4-bit QLoRA)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="Qwen/Qwen2.5-3B-Instruct",
        max_seq_length=max_seq_length,
        dtype=dtype,
        load_in_4bit=load_in_4bit,
    )

    print("\n[2/5] Configuring LoRA Adapters for Looped Reasoning...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=32,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    print("\n[3/5] Formatting Dataset with ChatML Template...")
    tokenizer = get_chat_template(
        tokenizer,
        chat_template="qwen-2.5",
    )

    dataset_path = os.environ.get("DATASET_PATH", "lensetek_edge_loop_3000.jsonl")
    if not os.path.exists(dataset_path):
        print(f"[ERROR] Dataset file not found at: {dataset_path}")
        sys.exit(1)

    dataset = load_dataset("json", data_files=dataset_path, split="train")

    def formatting_prompts_func(examples):
        convos = examples["messages"]
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convos]
        return {"text": texts}

    dataset = dataset.map(formatting_prompts_func, batched=True)

    print("\n[4/5] Starting SFT Training (Estimated: ~1.5 hours on RTX 4090)...")
    training_args = TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=15,
        max_steps=350, # Sufficient for 3,000 trajectories convergence
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        output_dir="outputs_lensetek_edge_loop",
        report_to="none"
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        dataset_num_proc=2,
        packing=False,
        args=training_args,
    )

    trainer_stats = trainer.train()
    print(f"\n[INFO] Training finished in {trainer_stats.metrics['train_runtime']:.2f} seconds.")

    print("\n[5/5] Exporting & Uploading Checkpoints to Hugging Face...")

    # Step A: Save & Push 16-bit Full Precision Safetensors
    base_repo = "lensetek/lensetek-edge-loop-3b"
    print(f" -> Merging LoRA into 16-bit Safetensors and pushing to {base_repo}...")
    try:
        model.push_to_hub_merged(
            base_repo,
            tokenizer,
            save_method="merged_16bit",
            token=hf_token
        )
        print(f" [SUCCESS] Uploaded 16-bit Safetensors to {base_repo}!")
    except Exception as e:
        print(f" [WARNING] Could not push 16-bit merged weights directly: {e}")
        print(" Saving locally to './lensetek_edge_loop_3b_safetensors' instead...")
        model.save_pretrained_merged("lensetek_edge_loop_3b_safetensors", tokenizer, save_method="merged_16bit")

    # Step B: Export & Push 4-bit Q4_K_M GGUF for Edge Inference
    gguf_repo = "lensetek/lensetek-edge-loop-3b-GGUF"
    print(f" -> Quantizing to Q4_K_M GGUF and pushing to {gguf_repo}...")
    try:
        model.push_to_hub_gguf(
            gguf_repo,
            tokenizer,
            quantization_method="q4_k_m",
            token=hf_token
        )
        print(f" [SUCCESS] Uploaded Q4_K_M GGUF to {gguf_repo}!")
    except Exception as e:
        print(f" [WARNING] Could not push GGUF directly: {e}")
        print(" Saving GGUF locally to './lensetek_edge_loop_3b_gguf' instead...")
        model.save_pretrained_gguf("lensetek_edge_loop_3b_gguf", tokenizer, quantization_method="q4_k_m")

    print("\n" + "=" * 65)
    print(" 🎉 TRAINING & EXPORT COMPLETED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    main()
