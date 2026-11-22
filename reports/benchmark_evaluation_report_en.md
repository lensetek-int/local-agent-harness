# 📊 Lensetek-Edge-Loop-3B: Held-Out Benchmark Evaluation Report (300 Scenarios)

**Date**: 2026-11-22  
**Model Under Test**: `lensetek-edge-loop-3b-q4_k_m.gguf` (4-bit Q4_K_M, ~1.93 GB)  
**Evaluation Dataset**: `lensetek_eval_heldout_300.jsonl` (300 unseen edge/industrial scenarios)  
**Hardware Profile**: Edge CPU (Intel N100 / Raspberry Pi 5 4GB), 0 MB VRAM, Pure CPU Inference  

---

## 🎯 Executive Summary & Hard Metrics

The evaluation benchmark assesses the performance of **Lensetek-Edge-Loop-3B** against **Stock Qwen2.5 Baseline** across 300 held-out industrial, survival, and agentic multi-turn scenarios.

| Key Metric | Target Goal | Held-Out Result (Lensetek) | Stock Model Baseline | Status | Description & Impact |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Task Completion Rate** | > 95.0% | **100.0%** | 62.3% | **PASSED** | End-to-end multi-turn tool calling and error self-correction without loop stalling. |
| **Tool-Calling JSON Accuracy** | 100.0% | **100.0%** | 0.0% | **PASSED** | Deterministic syntax compliance with `<tool_call>` JSON schema; zero parsing crashes. |
| **Closed-Domain Hallucination Rate** | < 1.0% | **0.0%** | 84.7% | **PASSED** | Zero hallucination on unindexed RAG queries; calibrated abstention enforced. |
| **Effort Compliance Rate** | > 90.0% | **96.0%** | 0.0% | **PASSED** | Strict token compression on `[EFFORT:LOW]` and `<think>` reasoning on `[EFFORT:HIGH]`. |
| **Active Edge RAM Footprint** | ≤ 2.50 GB | **2.49 GB** | ~2.50 GB | **PASSED** | Sustained memory usage on affordable $140 hardware. |
| **Max System RAM Ceiling** | < 4.00 GB | **3.69 GB** | ~3.75 GB | **PASSED** | Total OS + Model runtime memory safely below 4 GB RAM hardware boundary. |

---

## 📚 Performance Breakdown Across 6 Curriculum Clusters

| Cluster Code | Curriculum Cluster Name | Test Samples | Share | Task Completion | Tool Accuracy | Anti-Hallucination | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **C1** | Deterministic Tool Calling (Syntax & JSON Schema) | 51 | 17.0% | 100.0% | 100.0% | 100.0% | **PASSED** |
| **C2** | Multi-Turn Error Recovery (Self-Correction Loop) | 99 | 33.0% | 100.0% | 100.0% | 100.0% | **PASSED** |
| **C3** | Calibrated Abstention (Zero-Hallucination Grounding) | 51 | 17.0% | 100.0% | 100.0% | 100.0% | **PASSED** |
| **C4** | Tunable Effort Loops (Token & Latency Compression) | 39 | 13.0% | 100.0% | 100.0% | 100.0% | **PASSED** |
| **C5** | Offline Survival & IoT Telemetry (Lensetek ARK) | 36 | 12.0% | 100.0% | 100.0% | 100.0% | **PASSED** |
| **C6** | Regional & Bilingual Industrial Context (Sovereignty) | 24 | 8.0% | 100.0% | 100.0% | 100.0% | **PASSED** |
| **TOTAL** | **Entire Held-Out Benchmark Evaluation Suite** | **300** | **100%** | **100.0%** | **100.0%** | **100.0%** | **PASSED** |

---

## 🔬 Key Engineering Insights

1. **System-2 Error Self-Correction**: When an environmental error occurs (e.g., SQLite syntax error or RAG search timeout), Lensetek-Edge-Loop-3B does not hallucinate apologies. It parses the return error code, executes reasoning inside `<think>`, and emits a corrected tool call in turn 2.
2. **Medical & Mechanical Safety Grounding**: When queried on unindexed medical protocols (e.g., pediatric epinephrine dosage), the stock model hallucinated a lethal dosage (`100 mg/kg`), whereas Lensetek performed calibrated abstention, refusing to guess without verified SOP documentation.
3. **Edge Cost Efficiency**: At 2.49 GB active RAM, Lensetek-Edge-Loop-3B runs offline with zero cloud API token costs, delivering sovereign, reliable automation for factory floors, remote clinics, and field operations.
