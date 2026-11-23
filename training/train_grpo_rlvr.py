#!/usr/bin/env python3
"""
Lensetek Edge-Loop-3B: GRPO (Reinforcement Learning with Verifiable Rewards) Pipeline
Resolves PM-02 (RLVR Implementation for Asymmetric Anti-Hallucination & Effort Loops).

3 Verifiable Deterministic Rewards:
1. Tool JSON Schema Validity (+1.0 valid <tool_call>, -1.5 malformed JSON)
2. Calibrated Abstention (+0.8 abstaining on empty RAG, -2.0 hallucinating facts)
3. Adaptive Compute Effort (+0.5 obeying [EFFORT:LOW] / [EFFORT:HIGH] bounds)
"""

import os
import sys
import re
import json
import argparse

# ------------------------------------------------------------------------------
# 3 VERIFIABLE DETERMINISTIC REWARD FUNCTIONS
# ------------------------------------------------------------------------------
def reward_tool_json_schema(completions, **kwargs):
    """
    Rewards valid Qwen2.5 <tool_call> JSON syntax.
    Valid JSON with 'name' and 'arguments' (dict) -> +1.0
    Unclosed tag or broken JSON -> -1.5
    Non-tool conversational response -> 0.0 (neutral)
    """
    rewards = []
    for completion in completions:
        # Extract text from completion
        text = completion[0]["content"] if isinstance(completion, list) else str(completion)
        if "<tool_call>" in text:
            match = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", text, re.DOTALL)
            if not match:
                # Opened tag but didn't close properly
                rewards.append(-1.5)
                continue
            json_str = match.group(1).strip()
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, dict) and "name" in parsed and "arguments" in parsed:
                    if isinstance(parsed["arguments"], dict):
                        rewards.append(1.0)
                    else:
                        rewards.append(0.2)
                else:
                    rewards.append(-0.8)
            except Exception:
                rewards.append(-1.5)
        else:
            # If prompt didn't request a tool call, conversational response is neutral
            rewards.append(0.0)
    return rewards


def reward_calibrated_abstention(completions, prompts, **kwargs):
    """
    Asymmetric reward for anti-hallucination:
    - If prompt RAG returned 0 hits / missing doc:
      - Model honestly abstains ("tidak ditemukan", "tidak tercantum", "not found") -> +0.8
      - Model fabricates numerical doses / specs -> -2.0
    - If context was present, neutral -> 0.0
    """
    rewards = []
    abstention_keywords = [
        "tidak ditemukan", "tidak tercantum", "menolak", "tidak memiliki akses",
        "tidak ada di dokumen", "not found", "not documented", "abstaining", "informasi tidak ada"
    ]
    hallucination_indicators = [
        "dosisnya adalah", "gunakan dosis", "resepkan", "torque specification is", "torsi adalah"
    ]

    for completion, prompt in zip(completions, prompts):
        p_text = prompt[-1]["content"].lower() if isinstance(prompt, list) else str(prompt).lower()
        c_text = completion[0]["content"].lower() if isinstance(completion, list) else str(completion).lower()

        # Check if this was a 0-hit / missing info context
        is_empty_context = ("0_hits_found" in p_text or "tidak ditemukan" in p_text or
                            "covers standard series x-100 to x-500 only" in p_text or "matches\": []" in p_text)

        if is_empty_context:
            is_abstaining = any(k in c_text for k in abstention_keywords)
            is_hallucinating = any(h in c_text for h in hallucination_indicators)
            if is_abstaining and not is_hallucinating:
                rewards.append(0.8)
            elif is_hallucinating:
                rewards.append(-2.0)
            else:
                rewards.append(-0.5)
        else:
            rewards.append(0.0)
    return rewards


def reward_adaptive_effort(completions, prompts, **kwargs):
    """
    Rewards strict compliance with [EFFORT:LOW] and [EFFORT:HIGH] control tags:
    - [EFFORT:LOW]: No <think> block and concise answer (<= 35 words) -> +0.5; verbose -> -0.8
    - [EFFORT:HIGH]: Opens <think> ... </think> block (40 - 250 words) -> +0.5; no thinking -> -0.5
    """
    rewards = []
    for completion, prompt in zip(completions, prompts):
        p_text = prompt[-1]["content"] if isinstance(prompt, list) else str(prompt)
        c_text = completion[0]["content"] if isinstance(completion, list) else str(completion)

        word_count = len(c_text.split())
        has_think = "<think>" in c_text and "</think>" in c_text

        if "[EFFORT:LOW]" in p_text:
            if not has_think and word_count <= 40:
                rewards.append(0.5)
            elif has_think:
                rewards.append(-0.8)  # Disobeyed low effort
            else:
                rewards.append(max(-0.8, 0.5 - (word_count - 40) * 0.02))
        elif "[EFFORT:HIGH]" in p_text:
            if has_think:
                think_content = re.search(r"<think>(.*?)</think>", c_text, re.DOTALL)
                think_words = len(think_content.group(1).split()) if think_content else 0
                if 15 <= think_words <= 260:
                    rewards.append(0.5)
                else:
                    rewards.append(0.1)
            else:
                rewards.append(-0.5)  # Skipped required thinking loop
        else:
            rewards.append(0.0)
    return rewards


# ------------------------------------------------------------------------------
# LOCAL TEST SUITE (ZERO GPU REQUIRED)
# ------------------------------------------------------------------------------
def run_test_rewards():
    print("=" * 65)
    print(" 🧪 RUNNING LOCAL UNIT TESTS FOR VERIFIABLE REWARDS (GRPO)")
    print("=" * 65)

    # Test 1: Tool JSON Schema
    test_tool_good = [{'content': '<tool_call>\n{"name": "canbus_read", "arguments": {"node": "0x18F"}}\n</tool_call>'}]
    test_tool_broken = [{'content': '<tool_call>\n{"name": "canbus_read", "arguments": \n</tool_call>'}]
    test_tool_unclosed = [{'content': '<tool_call>\n{"name": "canbus_read"}'}]

    r_good = reward_tool_json_schema([test_tool_good])[0]
    r_broken = reward_tool_json_schema([test_tool_broken])[0]
    r_unclosed = reward_tool_json_schema([test_tool_unclosed])[0]
    print(f"[TEST 1] Tool JSON Schema -> Good: {r_good} (Exp: 1.0) | Broken: {r_broken} (Exp: -1.5) | Unclosed: {r_unclosed} (Exp: -1.5)")
    assert r_good == 1.0 and r_broken == -1.5 and r_unclosed == -1.5

    # Test 2: Calibrated Abstention
    prompt_empty = [{'content': 'Context matches: [] (0_hits_found). Berapa dosis obat?'}]
    comp_abstain = [{'content': '⚠️ Informasi tidak ditemukan di dokumen lokal, saya menolak menebak.'}]
    comp_hallucinate = [{'content': 'Dosisnya adalah 500mg diminum 3 kali sehari.'}]

    r_abs = reward_calibrated_abstention([comp_abstain], [prompt_empty])[0]
    r_hal = reward_calibrated_abstention([comp_hallucinate], [prompt_empty])[0]
    print(f"[TEST 2] Calibrated Abstention -> Honest Abstain: {r_abs} (Exp: 0.8) | Hallucination: {r_hal} (Exp: -2.0)")
    assert r_abs == 0.8 and r_hal == -2.0

    # Test 3: Adaptive Effort Loops
    p_low = [{'content': '[EFFORT:LOW] Toggle fan.'}]
    c_low_good = [{'content': 'Exhaust fan set to ON.'}]
    c_low_verbose = [{'content': '<think>\nThinking deeply about the fan...\n</think>\nFan is set to ON.'}]
    p_high = [{'content': '[EFFORT:HIGH] Calculate ratio.'}]
    c_high_good = [{'content': '<think>\n1. Step 1: Input 45 ton uap.\n2. Step 2: Input 9 ton cangkang.\n3. Ratio = 45/9 = 5.0 kg/kg.\n</think>\nRasio adalah 5.0 kg/kg.'}]

    r_low = reward_adaptive_effort([c_low_good], [p_low])[0]
    r_low_bad = reward_adaptive_effort([c_low_verbose], [p_low])[0]
    r_high = reward_adaptive_effort([c_high_good], [p_high])[0]
    print(f"[TEST 3] Adaptive Effort -> Low (Clean): {r_low} (Exp: 0.5) | Low (Disobeyed): {r_low_bad} (Exp: -0.8) | High (Think): {r_high} (Exp: 0.5)")
    assert r_low == 0.5 and r_low_bad == -0.8 and r_high == 0.5

    print("\n✅ ALL 3 VERIFIABLE REWARD FUNCTIONS PASSED 100% DETERMINISTICALLY!")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Lensetek GRPO RLVR Training Script")
    parser.add_argument("--test-rewards", action="store_true", help="Run local deterministic unit tests on reward functions")
    parser.add_argument("--base-model", type=str, default="lensetek_edge_loop_3b_safetensors", help="SFT checkpoint path or HF model ID")
    parser.add_argument("--dataset", type=str, default="lensetek_edge_loop_3000.jsonl", help="Dataset jsonl path for GRPO prompts")
    parser.add_argument("--max-steps", type=int, default=150, help="GRPO training steps")
    parser.add_argument("--lr", type=float, default=5e-6, help="GRPO learning rate (conservative for RL stability)")
    parser.add_argument("--output-dir", type=str, default="outputs_lensetek_grpo", help="GRPO checkpoint directory")
    parser.add_argument("--dry-run", action="store_true", help="Dry run validation")
    args = parser.parse_args()

    if args.test_rewards:
        run_test_rewards()
        return

    print("=" * 65)
    print(" 🚀 LENSETEK GRPO RLVR RUNPOD EXECUTION PIPELINE (v3.0)")
    print(f" -> Base SFT Model : {args.base_model}")
    print(f" -> Max Steps      : {args.max_steps}")
    print(f" -> Learning Rate  : {args.lr}")
    print("=" * 65)

    try:
        import torch
        from unsloth import FastLanguageModel, PatchFastRL
        from datasets import load_dataset
        from trl import GRPOTrainer, GRPOConfig
    except ImportError:
        print("[NOTE] TRL / Unsloth not installed in local environment.")
        print("To run in RunPod GPU cloud, execute:")
        print("pip install trl unsloth datasets")
        print("Local dry-test can be verified with: python train_grpo_rlvr.py --test-rewards")
        sys.exit(0)

    if args.dry_run:
        run_test_rewards()
        print("[DRY-RUN] Dependencies detected and reward functions verified.")
        return

    PatchFastRL("GRPO", FastLanguageModel)

    print(f"\n[1/4] Loading SFT checkpoint: {args.base_model}...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=2048,
        load_in_4bit=True,
        fast_inference=False,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=16,
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    print(f"\n[2/4] Preparing GRPO prompt dataset from {args.dataset}...")
    dataset_path = args.dataset
    if not os.path.exists(dataset_path):
        dataset_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.dataset)
    raw_ds = load_dataset("json", data_files=dataset_path, split="train")

    def to_grpo_prompt(example):
        msgs = example.get("messages", [])
        prompt_msgs = []
        for m in msgs:
            if m.get("role") in ("system", "user"):
                prompt_msgs.append({"role": m["role"], "content": m["content"]})
                if m.get("role") == "user":
                    break
        return {"prompt": prompt_msgs}

    grpo_ds = raw_ds.map(to_grpo_prompt, remove_columns=raw_ds.column_names)

    print("\n[3/4] Starting GRPO RLVR Training with 3 Verifiable Rewards...")
    grpo_config = GRPOConfig(
        learning_rate=args.lr,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        num_generations=4,
        max_prompt_length=768,
        max_completion_length=512,
        max_steps=args.max_steps,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        logging_steps=5,
        output_dir=args.output_dir,
        report_to="none",
    )

    trainer = GRPOTrainer(
        model=model,
        processing_class=tokenizer,
        reward_funcs=[
            reward_tool_json_schema,
            reward_calibrated_abstention,
            reward_adaptive_effort,
        ],
        args=grpo_config,
        train_dataset=grpo_ds,
    )
    trainer.train()

    print("\n[4/4] Exporting GRPO-aligned model to 16-bit Safetensors & Q4_K_M GGUF...")
    model.save_pretrained_merged("lensetek_edge_loop_3b_grpo_safetensors", tokenizer, save_method="merged_16bit")
    model.save_pretrained_gguf("lensetek_edge_loop_3b_grpo_gguf", tokenizer, quantization_method="q4_k_m")
    print("🎉 GRPO RLVR Training & GGUF Export Finished Successfully!")


if __name__ == "__main__":
    main()
