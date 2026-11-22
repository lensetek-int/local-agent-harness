#!/usr/bin/env python3
"""
Lensetek Edge-Loop-3B: Cloud Fine-Tuning Pipeline for RunPod (v2.0)
Model-Agnostic SFT + QLoRA (Supports Qwen2.5, Llama 3.2, Gemma 2).
Features:
- train_on_responses_only mask (prevents loss penalty on system prompts)
- CLI argument parsing for dataset, base-model, max-steps
- Safe local save and auto-push to Hugging Face
"""

import os
import sys
import argparse
import torch

def parse_args():
    parser = argparse.ArgumentParser(description="Lensetek Cloud Training Pipeline")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-3B-Instruct", help="Hugging Face base model ID")
    parser.add_argument("--dataset", type=str, default="lensetek_edge_loop_3000.jsonl", help="Dataset filename or path")
    parser.add_argument("--max-steps", type=int, default=400, help="Max SFT training steps")
    parser.add_argument("--batch-size", type=int, default=2, help="Per device batch size")
    parser.add_argument("--grad-accum", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--skip-push", action="store_true", help="Skip pushing to Hugging Face (local export only)")
    return parser.parse_args()

def main():
    args = parse_args()

    print("=" * 65)
    print(" 🚀 LENSETEK EDGE-LOOP: SFT TRAINING PIPELINE (v2.0)")
    print(f" -> Base Model: {args.base_model}")
    print(f" -> Dataset   : {args.dataset}")
    print(f" -> Max Steps : {args.max_steps}")
    print("=" * 65)

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token and not args.skip_push:
        print("[WARNING] 'HF_TOKEN' not set. Checkpoints will be saved locally.")

    try:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import load_dataset
        from unsloth.chat_templates import get_chat_template, train_on_responses_only
    except ImportError:
        print("[ERROR] Unsloth dependencies not found.")
        print("Run: pip install --no-deps \"unsloth[cu121-ampere-torch240] @ git+https://github.com/unslothai/unsloth.git\"")
        print("     pip install datasets trl bitsandbytes transformers accelerate")
        sys.exit(1)

    max_seq_length = 4096
    dtype = None
    load_in_4bit = True

    print(f"\n[1/5] Loading Base Model: {args.base_model} (4-bit QLoRA)...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=max_seq_length,
        dtype=dtype,
        load_in_4bit=load_in_4bit,
    )

    print("\n[2/5] Configuring LoRA Adapters...")
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

    print("\n[3/5] Formatting Dataset with Native Template...")
    template_type = "qwen-2.5" if "qwen" in args.base_model.lower() else "llama-3.1"
    tokenizer = get_chat_template(
        tokenizer,
        chat_template=template_type,
    )

    dataset_path = args.dataset
    if not os.path.exists(dataset_path):
        cur_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.dataset)
        if os.path.exists(cur_dir_path):
            dataset_path = cur_dir_path
        else:
            print(f"[ERROR] Dataset file not found: {args.dataset}")
            sys.exit(1)

    dataset = load_dataset("json", data_files=dataset_path, split="train")

    def formatting_prompts_func(examples):
        convos = examples["messages"]
        texts = [tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False) for convo in convos]
        return {"text": texts}

    dataset = dataset.map(formatting_prompts_func, batched=True)

    print("\n[4/5] Starting SFT Training...")
    training_args = TrainingArguments(
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_steps=15,
        max_steps=args.max_steps,
        learning_rate=args.lr,
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

    # Mask prompts so loss is only calculated on assistant responses
    try:
        trainer = train_on_responses_only(
            trainer,
            instruction_part="<|im_start|>user\n",
            response_part="<|im_start|>assistant\n",
        )
        print(" [INFO] train_on_responses_only applied successfully.")
    except Exception as e:
        print(f" [NOTE] train_on_responses_only skipped: {e}")

    trainer_stats = trainer.train()
    print(f"\n[INFO] SFT Training completed in {trainer_stats.metrics.get('train_runtime', 0):.2f}s.")

    print("\n[5/5] Exporting Model Checkpoints...")
    base_repo = "lensetek/lensetek-edge-loop-3b"
    gguf_repo = "lensetek/lensetek-edge-loop-3b-GGUF"

    # Save Safetensors
    if hf_token and not args.skip_push:
        print(f" -> Pushing merged 16-bit Safetensors to {base_repo}...")
        try:
            model.push_to_hub_merged(base_repo, tokenizer, save_method="merged_16bit", token=hf_token)
            print(f" [SUCCESS] 16-bit Safetensors uploaded to {base_repo}!")
        except Exception as e:
            print(f" [WARNING] Push failed: {e}. Saving locally...")
            model.save_pretrained_merged("lensetek_edge_loop_3b_safetensors", tokenizer, save_method="merged_16bit")
    else:
        print(" -> Saving merged 16-bit Safetensors locally...")
        model.save_pretrained_merged("lensetek_edge_loop_3b_safetensors", tokenizer, save_method="merged_16bit")

    # Save GGUF Q4_K_M
    if hf_token and not args.skip_push:
        print(f" -> Quantizing to Q4_K_M GGUF and pushing to {gguf_repo}...")
        try:
            model.push_to_hub_gguf(gguf_repo, tokenizer, quantization_method="q4_k_m", token=hf_token)
            print(f" [SUCCESS] Q4_K_M GGUF uploaded to {gguf_repo}!")
        except Exception as e:
            print(f" [WARNING] GGUF Push failed: {e}. Saving locally...")
            model.save_pretrained_gguf("lensetek_edge_loop_3b_gguf", tokenizer, quantization_method="q4_k_m")
    else:
        print(" -> Saving Q4_K_M GGUF locally...")
        model.save_pretrained_gguf("lensetek_edge_loop_3b_gguf", tokenizer, quantization_method="q4_k_m")

    print("\n" + "=" * 65)
    print(" 🎉 TRAINING & EXPORT FINISHED SUCCESSFULLY!")
    print("=" * 65)

if __name__ == "__main__":
    main()
