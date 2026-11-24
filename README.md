---
title: Lensetek Edge AI Agent Harness
emoji: ⚡
colorFrom: blue
colorTo: green
sdk: static
pinned: false
license: mit
tags:
- llama.cpp
- openai-compatible
- ai-agents
- langchain
- crewai
- voice-assistant
- edge-tts
- whisper
- kokoro
---

<div align="center">

# lensetek-edge-ai-agent
### Self-Contained Local Edge AI Studio & OpenAI-Compatible API for AI Agents

🌐 **Language Navigation / Navigasi Bahasa / 语言导航**:  
[English](#-english) • [Bahasa Indonesia](#-bahasa-indonesia) • [简体中文](#-chinese-简体中文)

---

### 🌐 Official Ecosystem Navigation / Navigasi Repositori Terkait

| Repository | Role & Description | Format & Target Hardware | Direct Link |
| :--- | :--- | :--- | :---: |
| **🧠 [`lensetek-edge-loop-3b-GGUF`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF)** | **Edge Quantized Model (Ready-to-Run)**<br>Specialized 4-bit edge weights with 100% tool accuracy & zero-hallucination. | 4-Bit `Q4_K_M` GGUF (~1.93 GB)<br>Runs on Mini PC / SBC / CPU (RAM < 2.5 GB) | [**⬇️ Direct Download (~1.93 GB)**](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF/resolve/main/lensetek-edge-loop-3b-q4_k_m.gguf?download=true) • [Model Repo](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF) |
| **🔬 [`lensetek-edge-loop-3b`](https://huggingface.co/lensetek/lensetek-edge-loop-3b)** | **Base 16-Bit Model (Safetensors)**<br>Full-precision weights for GPU inference (vLLM/SGLang) and domain fine-tuning. | 16-Bit BF16 Safetensors (~6 GB)<br>*(Status: Queued / Dalam Antrean Unggah)* | [**Inspect Repo**](https://huggingface.co/lensetek/lensetek-edge-loop-3b) |
| **🛠️ [`lensetek-edge-ai-agent`](https://huggingface.co/lensetek/lensetek-edge-ai-agent)** *(Current Repo)* | **Application Hub & Edge Studio**<br>Self-contained workspace with Web UI, air-gapped SQLite RAG, and agent harnesses. | Application Code & Multi-Project Suite<br>(`usecase/edge-ai-agent` & `survival-agent`) | [**Explore Code Hub**](https://huggingface.co/lensetek/lensetek-edge-ai-agent) |

---

> 🔄 **Custom Quantization & WebGPU Conversion**: Need a custom variant (WebGPU ONNX, Apple Silicon MLX, or specialized GGUF)? Check out our [**Model Converter Toolkit**](converter/README.md) or launch the free [**Colab Self-Converter**](converter/lensetek_converter_colab.ipynb).

---

</div>

<a id="english"></a>
# 🇬🇧 English

A self-contained local AI workspace featuring text inference, vision understanding, and **Realtime Hands-Free Voice with Barge-In (Interruption)** capability. It includes a built-in **OpenAI-Compatible API Server (`/v1/chat/completions`)** designed for autonomous AI agents (**LangChain, CrewAI, AutoGen, OpenAI Python/Node SDK, Cursor, and Continue.dev**).

---

### ⚡ 0. LENSETEK LEAN AGENT HARNESS (CLI & Universal MCP Orchestrator)

> 🚀 **Interactive Web Landing Page**: Open [`docs/index.html`](docs/index.html) (or `index.html`) in your browser to test interactive terminal commands and view one-click installation snippets!

The **LENSETEK LEAN AGENT HARNESS** (`cli-agent/`) is a dedicated autonomous agent harness running locally on top of edge GGUF models (3B / 7B) on commodity 4-core CPUs (AMD Ryzen 3 5300U) with RAM &lt; 2.5 GB.

#### 📦 One-Liner Quick Installation

| Package / Method | Command | Description |
| :--- | :--- | :--- |
| **PowerShell (Windows)** | `irm https://raw.githubusercontent.com/lensetek/local-llm/main/install.ps1 \| iex` | One-liner auto installer & launcher |
| **curl (Linux / macOS)** | `curl -fsSL https://raw.githubusercontent.com/lensetek/local-llm/main/install.sh \| bash` | Headless auto-install to `~/.lensetek-agent` |
| **git & local run** | `git clone https://github.com/lensetek/local-llm.git && cd local-llm/cli-agent && run_agent.bat` | Standard developer repository workflow |
| **pip** | `pip install -r cli-agent/requirements.txt && py cli-agent/main.py` | Direct Python launch with `prompt_toolkit` |

#### 🛠️ Key Agentic Features:
- **Universal MCP Orchestrator**: Manage and connect Stdio MCP servers dynamically via `/mcp` (`fetch`, `playwright-headless`, etc.).
- **Headless Web Search**: Built-in Bing & Google headless search via `/search <query>` and native `web_search` tool without external API keys.
- **230+ Skills Auto-Discovery**: Detects and parses prompt guides across local and global skill catalogs (`~/.agents/skills`, `~/.claude/skills`, `~/.gemini/`).
- **Interactive Autocomplete**: Powered by `prompt_toolkit` with `Tab` completion that auto-fills commands/skills and closes the popup list.
- **Autonomous /goal & /loop**: Multi-step goal planner (up to 20 steps) with context resilience and recurring task loops.
- **Multilingual System**: Persistent `/language <en|id|cn>` setting (English, Bahasa Indonesia, Chinese).
- **Safety Modes**: `/strict` [y/N], `/auto-approve`, and `/yolo` (unattended).

---

### 📥 1. Quickstart & Installation

This repository contains lightweight application code only (~200 KB) without multi-gigabyte model weights.

```bash
# Clone the repository
git clone https://huggingface.co/lensetek/lensetek-edge-ai-agent
cd lensetek-edge-ai-agent

# Install dependencies
pip install -r requirements.txt
```

---

### 📦 2. Downloading Models on Demand

Download your preferred GGUF and Voice models directly using the interactive downloader or dedicated CLI commands:

| Model Name & Profile | Format & Size | Hugging Face Source | One-Click Download Command |
| :--- | :---: | :---: | :--- |
| **🧠 Lensetek Edge-Loop 3B** *(Flagship Agent)* | **~1.93 GB** (`Q4_K_M`) | [`lensetek/lensetek-edge-loop-3b-GGUF`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF) | `py download_models.py --loop`<br>[**⬇️ Direct Download GGUF**](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF/resolve/main/lensetek-edge-loop-3b-q4_k_m.gguf?download=true) |
| **🪶 Qwen 2.5 0.5B Instruct** *(Ultra-Light)* | ~491 MB (`Q4_K_M`) | [`Qwen/Qwen2.5-0.5B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) | `py download_models.py --default` |
| **⭐ Qwen 2.5 3B Instruct** *(General Agent)* | ~2.04 GB (`Q4_K_M`) | [`Qwen/Qwen2.5-3B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF) | `py download_models.py --agent` |
| **👑 Qwen 2.5 7B Instruct** *(Deep Reasoning)* | ~4.68 GB (`Q4_K_M`) | [`bartowski/Qwen2.5-7B-Instruct-GGUF`](https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF) | `py download_models.py --model qwen2.5-7b` |
| **👁️ SmolVLM 500M** *(Vision & Image)* | ~545 MB (`Q8_0`) | [`HuggingFaceTB/SmolVLM-500M-Instruct-GGUF`](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct-GGUF) | `py download_models.py --model smolvlm-500m` |
| **🎙️ Whisper Base / Small** *(STT Voice)* | 147 MB / 487 MB | [`ggerganov/whisper.cpp`](https://huggingface.co/ggerganov/whisper.cpp) | `py download_models.py --model whisper-base` |
| **🔊 Kokoro-82M** *(Studio TTS Voice)* | ~337 MB (ONNX) | [`hexgrad/Kokoro-82M`](https://huggingface.co/hexgrad/Kokoro-82M) | `py download_models.py --model kokoro-82m` |

```bash
# Interactive menu:
py download_models.py

# Download Flagship Lensetek Edge-Loop 3B (~1.93 GB):
py download_models.py --loop

# Download default package (Qwen 2.5 0.5B + Whisper Base ~638 MB):
py download_models.py --default

# Download AI Agent recommended model (Qwen 2.5 3B ~2.0 GB):
py download_models.py --agent

# Check installed models:
py download_models.py --status
```

---

### 🔌 3. OpenAI-Compatible API for AI Agents

The server exposes standard OpenAI endpoints at port `3000`:
- **Base URL**: `http://localhost:3000/v1`
- **Chat Completions**: `POST http://localhost:3000/v1/chat/completions`
- **Models List**: `GET http://localhost:3000/v1/models`
- **API Key**: `sk-local` (or any dummy token if not set in `.env`)
- **⚡ Auto-Start**: Automatically boots the model when an agent request arrives!
- **🌊 Streaming**: Full SSE chunk streaming (`stream: true`) and non-streaming support.

#### Python (OpenAI SDK):
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local"
)

response = client.chat.completions.create(
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    messages=[
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "Hello! Introduce yourself."}
    ],
    temperature=0.7,
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

#### LangChain & CrewAI:
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local",
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    temperature=0.7
)

print(llm.invoke("What is a Multi-Agent system?").content)
```

#### cURL:
```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

---

### 📚 4. Built-in Lightweight Edge RAG (SQLite3 + Pure NumPy)
A zero-daemon, embedded Retrieval-Augmented Generation (RAG) system tailored specifically for Edge Computers and low-power devices:
- **0 MB Idle Overhead**: Uses a single local SQLite database (`knowledge_rag.db`) with zero background daemon or service processes.
- **Sub-2ms SIMD Search**: High-speed cosine similarity calculation powered by pure NumPy SIMD matrix vectorization.
- **Multi-Format Extraction**: Ingests **PDF** (`pypdf`), **Word** (`.docx`), **Markdown** (`.md`), **TXT**, **CSV**, and **JSON** without external cloud dependencies.
- **Transparent Prompt Augmentation**: Relevant document chunks are automatically retrieved and injected into both the Web UI and the `/v1/chat/completions` API endpoint for connected AI agents.

---

### 🎙️ 5. Realtime Hands-Free Voice & Barge-In
- **⚡ Auto-Sela (Voice Barge-In)**: Speak while the AI is talking to immediately cut off speech and seamlessly take over (*Full-Duplex*).
- **✋ Manual Interruption**: Tap the orange **Sela AI** button or the **Voice Orb** to stop speech instantly.
- **🌐 3 TTS Engines**: Edge-TTS (Ultra-Natural Cloud), Kokoro-82M (100% Offline StyleTTS2), and Piper TTS (100% Offline Fast).

---

### 🚀 6. Running the Local Server
```bash
# Windows 1-Click Launch:
start.bat

# Or terminal:
py app.py
```
Open **`http://localhost:3000`** in your browser.

---

### 🖥️ 7. Edge & Local Hardware Compatibility Guide

This project is optimized with 4-bit Medium K-quantization (`Q4_K_M`) to run smoothly on edge computers and everyday laptops without requiring a dedicated discrete GPU:

| Hardware Tier | Recommended Edge Hardware & Brands | Laptop / PC Specs | Supported Model Category |
| :--- | :--- | :--- | :--- |
| **Tier 1: Low Edge (4 GB – 8 GB RAM) ⭐** | **SBCs**: Raspberry Pi 5 (4GB/8GB), Orange Pi 5, Rock 5B.<br>**Mini PCs**: Intel N95/N100 (Beelink Mini S12, GMKTec G3, Minisforum UN100). | Intel Core i3 / Celeron, AMD Ryzen 3, 4GB–8GB RAM. | **🔥 Flagship Edge Agent**: [`Lensetek-Edge-Loop-3B`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF)<br>• RAM footprint: **~2.49 GB** (System ≤ 3.69 GB)<br>• Speed: **18–35 tok/s** (Pure CPU, 0 MB VRAM)<br>• *Looped Reasoning, Error Recovery & Anti-Hallucination*<br><br>**🪶 Ultra-Light**: `Qwen 2.5 0.5B`<br>• RAM footprint: **~1.15 GB** • Speed: **35–50 tok/s** |
| **Tier 2: Mid Edge (8 GB – 16 GB RAM)** | **Mini PCs**: Intel N100/N200/Core i3-N305 (Beelink EQ12, ASUS NUC, LattePanda 3 Delta).<br>**AI SBCs**: NVIDIA Jetson Orin Nano (8GB), Orange Pi 5 Plus (16GB). | Acer Aspire, ASUS Vivobook, Lenovo IdeaPad, HP Pavilion (AMD Ryzen 5/7, Intel i5/i7, 8GB–16GB RAM). | **🤖 Stock General Agent**: `Qwen 2.5 3B`<br>• RAM footprint: **~3.80 GB** • Speed: **18–35 tok/s**<br>• Vision: `SmolVLM 500M` (~2.0 GB RAM) |
| **Tier 3: High Edge (16 GB – 32 GB RAM) 👑** | **Workstation Mini PCs**: AMD Ryzen 7/9 APUs (Beelink SER6/SER8, Minisforum UM790 Pro, Morefine M600, Apple Mac Mini M1/M2/M4).<br>**Industrial Edge**: LattePanda Sigma, Jetson Orin NX (16GB). | Acer Aspire/Swift, Lenovo ThinkPad/Legion, ASUS TUF/Zenbook, Dell XPS, MacBook (16GB–32GB RAM). | **🧠 Agentic Pro (7B)**: `Qwen 2.5 7B`<br>• RAM footprint: **~6.80 GB** • Speed: **8–18 tok/s**<br>• Multi-Agent reasoning & complex chains |

---

### 🛡️ 8. Security Architecture & Actuation Interlock (PM-06)

Lensetek Edge enforces rigorous industrial safety boundaries:
- **Read-Only Default Access**: All telemetry tools, sensor polls, Modbus registers, and database queries operate in strict Read-Only mode by default.
- **Hardware-in-the-Loop (HITL) Actuation Gates**: Writing to physical relays, PLC coils, or medical actuator endpoints requires an explicit physical operator verification token (`hitl_token` matching format `HITL-CONFIRM-XXXX`). Without this token, actuation calls are strictly blocked and logged to the append-only `safety_audit_log` in SQLite.
- **Zero Credential Exposure**: No API keys, passwords, or bearer tokens are stored in client-side code, frontend bundles, or tracked git repositories.
- **Air-Gapped Data Sovereignty**: Operates 100% offline with zero cloud telemetry, ensuring full compliance with national data sovereignty laws (Indonesian UU PDP No. 27/2022).

---

### ⚖️ 9. Licensing & Open-Core Architecture (Commercial Open-Source / COSS)

Lensetek operates under a transparent **Commercial Open-Source (COSS)** model, separating community-accessible open weights from proprietary turnkey enterprise hardware and connectors:

| Capability Tier | License | Target Audience | Included Components |
| :--- | :--- | :--- | :--- |
| **Community Open-Core & Weights** | **Apache-2.0 / MIT** | Developers, Researchers, Hobbyists, SMEs | • `Lensetek-Edge-Loop-3B` SLM Weights (GGUF & Safetensors)<br>• Self-Contained Edge Studio Web UI & OpenAI-compatible API Server<br>• Local SQLite RAG Engine (Zero standby RAM, SIMD cosine search)<br>• Basic Agent Harness & Context Compressor |
| **Enterprise Connectors & Compliance** | **Commercial Enterprise** | Factory Operators, Healthcare Clinics, Mining Enterprises | • Certified Field Connectors: Modbus RTU/TCP, CAN J1939, OPC-UA, HL7/DICOM<br>• SQLCipher At-Rest Encryption & Role-Based Access Control (RBAC)<br>• Multi-Node Fleet Telemetry & Central Over-The-Air (OTA) Dashboard<br>• Custom Enterprise SOP Fine-Tuning & GRPO RLVR Data Flywheel |
| **Lensetek ARK Rugged Turnkey** | **Turnkey Hardware + Commercial** | Disaster Response, Maritime, Defense & Off-Grid Infrastructure | • Mil-Spec IP67 Ruggedized Edge Compute Box with Integrated Lithium Iron Phosphate (LiFePO4) Battery<br>• Pre-flashed Air-Gapped Survival Agent HUD<br>• Dual VHF/UHF Field Antenna Interface & Hardware Kill Switch |

---

### 🏆 10. Lensetek-Edge-Loop-3B: Evaluation Benchmark & Head-to-Head Comparison

Our specialized model **`lensetek-edge-loop-3b-q4_k_m.gguf`** has been formally benchmarked against 300 held-out industrial & survival scenarios, evaluated alongside the original stock base model (*Qwen2.5-3B-Instruct*):

#### Hard-Metrics Scorecard (300 Held-Out Scenarios):
| Metric Dimension | Target Benchmark | Evaluated Result | Verdict | Technical Notes |
| :--- | :---: | :---: | :---: | :--- |
| **Task Completion Rate** | > 95.0% | **100.0%** | **PASSED** | Zero stuck loops; autonomous self-correction across multi-turn failures. |
| **Tool-Calling JSON Accuracy** | 100.0% | **100.0%** | **PASSED** | Strict adherence to native `<tool_call>` schema with zero unescaped syntax errors. |
| **Closed-Domain Hallucination Rate** | < 1.0% | **0.0%** | **PASSED** | Calibrated abstention: strictly refuses to guess when local context is absent. |
| **Effort Compliance Rate** | > 90.0% | **96.0%** | **PASSED** | Instant execution on `[EFFORT:LOW]` (<35 tokens) vs deep `<think>` on `[EFFORT:HIGH]`. |
| **Active Edge RAM Footprint** | ≤ 2.50 GB | **~2.49 GB** | **PASSED** | Active model weights + 4-bit KV cache running on low-cost $140 Mini PC / Pi 5. |

#### Head-to-Head Comparison (Stock Base vs Lensetek):
| Capability Dimension | Stock Qwen2.5-3B-Instruct | Lensetek-Edge-Loop-3B | Operational Advantage |
| :--- | :--- | :--- | :--- |
| **Tool Execution Format** | Often emits conversational filler text; ~15% schema failures. | **100% pure `<tool_call>` emitted on turn 1**. | Zero pipeline syntax crashes. |
| **Error Recovery** | Apologizes or halts when SQL/sensor fails. | **Parses error in `<think>`, modifies syntax, and retries**. | Autonomous multi-turn task completion. |
| **Data Absence Reaction** | Hallucinates plausible doses/torques (~28%). | **Disciplined abstention ("Not found in local SOP")**. | Zero-risk for medical and OT safety. |
| **Context Specialization** | Generic web knowledge. | **Indonesian industrial SOPs, PKS boilers, ARK disaster triage**. | Full sovereign domain grounding. |

> 📄 **Multilingual Evaluation Deliverables & Head-to-Head Test Logs**:
> - **English**: [Benchmark Evaluation Report (.md)](reports/benchmark_evaluation_report_en.md) • [Head-to-Head Comparison Log (.md)](reports/head_to_head_test_log_en.md)
> - **Indonesian**: [Laporan Evaluasi Benchmark (.md)](reports/benchmark_evaluation_report_id.md) • [Log Uji Riil Head-to-Head (.md)](reports/head_to_head_test_log_id.md)
> - **Chinese**: [基准评估报告 (.md)](reports/benchmark_evaluation_report_cn.md) • [实测直接对比日志 (.md)](reports/head_to_head_test_log_cn.md)
> - **Data & Matrix**: [300 Held-Out Scenarios Excel Matrix](reports/Hasil_Evaluasi_Benchmark_300_Skenario_Lensetek.xlsx) • [Scorecard JSON](training/eval_scorecard.json)

---

### 🆕 11. Revision v3.0 Changelog — Previous Issues & Fixes (`2026-11-23`)

#### ⚠️ Previous Issues Identified in v1/v2
1. **Catastrophic Forgetting on General Indonesian & Basic Math**: Training exclusively on 100% synthetic domain templates with an aggressive `lr=2e-4` and `< 1 epoch` caused the 3B model to degrade on casual Indonesian conversation, simple arithmetic, and general RAG summaries, occasionally outputting garbled tokens or reversing `[EFFORT:LOW/HIGH]` definitions.
2. **Model Identity Drift**: Because conversational identity samples were absent, the model occasionally introduced itself using base pretraining residue names instead of **Lensetek**.
3. **4-Bit KV Cache Corruption (`-ctk q4_0 -ctv q4_0`) & Zombie Processes**: Quantizing KV cache to `q4_0` on Qwen2.5-3B (which only has 2 KV heads) corrupted attention logits and produced incoherent word salad; orphaned `llama-server.exe` processes also held port `8080` across restarts.
4. **RAG Query Pollution & Raw Markdown UI**: `[EFFORT:HIGH]` tags leaked into `rag_engine.search()`, causing unrelated chunks containing that tag to match, while chat bubbles displayed raw Markdown (`**`, `*`) without a loading indicator.

#### ✅ Fixes Applied in Revision v3.0 (`2026-11-23`)
* **Model Weights v3.0 Replaced (Old v1/v2 Weights Removed)**:
  * Added **30% General Conversational Replay (`C7`)** to `lensetek_edge_loop_3000.jsonl` & `lensetek_eval_heldout_300.jsonl` plus **Lensetek** identity alignment.
  * Retrained with conservative `lr=8e-5`, `lora_alpha=16`, `2 full epochs`, cosine scheduler, and verified live on Indonesian identity, arithmetic (`1 + 15 = 16`), and 0-hit medical anti-hallucination before exporting the new `Q4_K_M` GGUF.
  * Implemented full `GRPOTrainer` + `GRPOConfig` loop and GGUF export in `training/train_grpo_rlvr.py`.
* **Edge Studio UI & Runtime Fixes (`app.py`)**:
  * Removed `-ctk q4_0 -ctv q4_0`, switched to `-fa auto`, added Qwen2.5 stop tokens (`<|im_end|>`, `<|endoftext|>`), `repeat_penalty=1.1`, and automatic zombie `llama-server.exe` cleanup on Windows.
  * Added **XSS-safe Markdown Renderer** (with collapsible `<think>` blocks), **animated loading bubble**, **RAG `[EFFORT:...]` tag stripping**, **1-click Project Folder Auto-Indexer (`/api/rag/index_project`)**, `➕ New Chat`, `🔇 Suara: OFF/ON` toggle, Effort selector (`OFF / LOW / HIGH`), and `🦙 Llama.cpp WebUI ↗` link.

<br>
<hr>

<a id="bahasa-indonesia"></a>
# 🇮🇩 Bahasa Indonesia

Aplikasi AI lokal mandiri (*self-contained*) untuk teks, multimodal visual (vision), dan percakapan suara **Realtime Hands-Free Voice dengan fitur Sela Bicara (Barge-In)**. Dilengkapi **OpenAI-Compatible API Server (`/v1/chat/completions`)** agar dapat langsung dihubungkan ke berbagai framework AI Agent (**LangChain, CrewAI, AutoGen, OpenAI Python/Node SDK, Cursor, dan Continue.dev**).

---

### ⚡ 0. LENSETEK LEAN AGENT HARNESS (CLI & Universal MCP Orchestrator)

> 🚀 **Halaman Web Interaktif (Landing Page)**: Buka [`docs/index.html`](docs/index.html) (atau `index.html`) di browser Anda untuk melihat demo terminal interaktif dan tombol 1-klik salin perintah instalasi!

**LENSETEK LEAN AGENT HARNESS** (`cli-agent/`) adalah harness agen AI otonom khusus yang berjalan 100% lokal di atas model edge GGUF (3B / 7B) pada prosesor 4-core hemat daya (AMD Ryzen 3 5300U) dengan penggunaan RAM &lt; 2.5 GB.

#### 📦 Perintah Cepat Instalasi 1-Baris

| Metode / Manajer Paket | Perintah Terminal | Keterangan |
| :--- | :--- | :--- |
| **PowerShell (Windows)** | `irm https://raw.githubusercontent.com/lensetek/local-llm/main/install.ps1 \| iex` | Pemasangan otomatis & launcher global |
| **curl (Linux / macOS)** | `curl -fsSL https://raw.githubusercontent.com/lensetek/local-llm/main/install.sh \| bash` | Pemasangan headless ke `~/.lensetek-agent` |
| **git & local run** | `git clone https://github.com/lensetek/local-llm.git && cd local-llm/cli-agent && run_agent.bat` | Alur kerja lokal pengembang |
| **pip** | `pip install -r cli-agent/requirements.txt && py cli-agent/main.py` | Jalankan langsung via Python & prompt_toolkit |

#### 🛠️ Fitur-Fitur Utama Agen:
- **Universal MCP Orchestrator**: Pasang dan operasikan server MCP secara dinamis via `/mcp` (`fetch`, `playwright-headless`, dll.).
- **Pencarian Web Headless**: Fitur pencarian Bing & Google tanpa API key melalui `/search <kueri>` dan tool bawaan `web_search`.
- **Deteksi 230+ Skills Otomatis**: Mendeteksi panduan skill lokal dan global dari Antigravity, Claude, Codex, dan Research Agent.
- **Autocomplete Interaktif**: Didukung `prompt_toolkit` dengan tombol `Tab` yang otomatis melengkapi nama perintah/skill dan menutup popup suggestion.
- **Otonom /goal & /loop**: Penyelesaian misi multi-langkah (hingga 20 langkah) dengan *pinned goal* yang kebal pemangkasan konteks, serta pengulangan tugas berkala.
- **Multi-Bahasa**: Pilihan bahasa aktif yang tersimpan permanen via `/language <en|id|cn>`.
- **Mode Keamanan**: `/strict` [y/N], `/auto-approve`, dan `/yolo` (unattended).

---

### 📥 1. Panduan Cepat & Pemasangan

Repository ini hanya memuat kode aplikasi (~200 KB) tanpa file bobot model besar.

```bash
# Clone repositori
git clone https://huggingface.co/lensetek/lensetek-edge-ai-agent
cd lensetek-edge-ai-agent

# Pasang dependensi
pip install -r requirements.txt
```

---

### 📦 2. Mengunduh Model Sesuai Kebutuhan

Unduh model GGUF dan Audio langsung menggunakan modul interaktif atau perintah langsung CLI:

| Nama Model & Profil | Format & Ukuran | Sumber Hugging Face | Perintah Unduh Langsung |
| :--- | :---: | :---: | :--- |
| **🧠 Lensetek Edge-Loop 3B** *(Flagship Agent)* | **~1.93 GB** (`Q4_K_M`) | [`lensetek/lensetek-edge-loop-3b-GGUF`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF) | `py download_models.py --loop`<br>[**⬇️ Unduh Langsung GGUF**](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF/resolve/main/lensetek-edge-loop-3b-q4_k_m.gguf?download=true) |
| **🪶 Qwen 2.5 0.5B Instruct** *(Ultra-Light)* | ~491 MB (`Q4_K_M`) | [`Qwen/Qwen2.5-0.5B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) | `py download_models.py --default` |
| **⭐ Qwen 2.5 3B Instruct** *(General Agent)* | ~2.04 GB (`Q4_K_M`) | [`Qwen/Qwen2.5-3B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF) | `py download_models.py --agent` |
| **👑 Qwen 2.5 7B Instruct** *(Deep Reasoning)* | ~4.68 GB (`Q4_K_M`) | [`bartowski/Qwen2.5-7B-Instruct-GGUF`](https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF) | `py download_models.py --model qwen2.5-7b` |
| **👁️ SmolVLM 500M** *(Vision & Gambar)* | ~545 MB (`Q8_0`) | [`HuggingFaceTB/SmolVLM-500M-Instruct-GGUF`](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct-GGUF) | `py download_models.py --model smolvlm-500m` |
| **🎙️ Whisper Base / Small** *(STT Suara)* | 147 MB / 487 MB | [`ggerganov/whisper.cpp`](https://huggingface.co/ggerganov/whisper.cpp) | `py download_models.py --model whisper-base` |
| **🔊 Kokoro-82M** *(Studio TTS Suara)* | ~337 MB (ONNX) | [`hexgrad/Kokoro-82M`](https://huggingface.co/hexgrad/Kokoro-82M) | `py download_models.py --model kokoro-82m` |

```bash
# Menu interaktif visual:
py download_models.py

# Unduh Flagship Lensetek Edge-Loop 3B (~1.93 GB):
py download_models.py --loop

# Unduh paket default (Qwen 2.5 0.5B + Whisper Base ~638 MB):
py download_models.py --default

# Unduh model rekomendasi AI Agent (Qwen 2.5 3B ~2.0 GB):
py download_models.py --agent

# Cek status model yang terpasang:
py download_models.py --status
```

---

### 🔌 3. OpenAI-Compatible API untuk AI Agents

Server otomatis menyediakan endpoint standar OpenAI pada port `3000`:
- **Base URL**: `http://localhost:3000/v1`
- **Chat Completions**: `POST http://localhost:3000/v1/chat/completions`
- **Models List**: `GET http://localhost:3000/v1/models`
- **API Key**: `sk-local` (Bebas / Dummy jika belum diset di `.env`)
- **⚡ Auto-Start**: Otomatis menyalakan model jika ada request dari agent!
- **🌊 Streaming**: Mendukung penuh SSE streaming (`stream: true`) dan non-streaming.

#### Python (OpenAI SDK Resmi):
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local"
)

response = client.chat.completions.create(
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    messages=[
        {"role": "system", "content": "Kamu adalah asisten AI yang ramah."},
        {"role": "user", "content": "Halo! Jelaskan siapa namamu."}
    ],
    temperature=0.7,
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

#### LangChain & CrewAI:
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local",
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    temperature=0.7
)

print(llm.invoke("Jelaskan apa itu Multi-Agent System!").content)
```

---

### 📚 4. RAG Dokumen Ringan untuk Edge Computing (SQLite3 + NumPy)
Sistem *Retrieval-Augmented Generation* (RAG) mandiri tanpa daemon background, dirancang khusus untuk komputer Edge dan perangkat hemat daya:
- **0 MB Beban RAM saat Standby**: Memakai satu berkas database lokal (`knowledge_rag.db`) berbasis SQLite3 bawaan Python tanpa server vektor pihak ketiga yang rakus memori.
- **Pencarian SIMD < 2 ms**: Vektorisasi embedding dinormalisasi L2 dan dihitung menggunakan perkalian matriks SIMD NumPy secepat kilat pada CPU Edge.
- **Mendukung Berbagai Format Dokumen**: Mampu mengekstrak **PDF** (`pypdf`), **Word** (`.docx`), **Markdown** (`.md`), **TXT**, **CSV**, dan **JSON**.
- **Injeksi Konteks Otomatis**: Konteks dokumen internal otomatis disisipkan ke prompt percakapan Web Studio dan endpoint `/v1/chat/completions` untuk seluruh framework AI Agent.

---

### 🎙️ 5. Mode Realtime Hands-Free Voice & Sela Bicara
- **⚡ Auto-Sela (Voice Barge-In)**: Cukup bersuara saat AI sedang bicara, sistem otomatis memotong audio AI (*Full-Duplex*).
- **✋ Sela Manual**: Klik tombol oranye **Sela AI** atau ketuk **Voice Orb** untuk berhenti seketika.
- **🌐 3 Mesin Suara**: Edge-TTS (Hybrid Cloud Super Alami), Kokoro-82M (100% Offline StyleTTS2), dan Piper TTS (100% Offline Cepat).

---

### 🚀 6. Menjalankan Server Lokal
```bash
# Windows 1-Klik:
start.bat

# Atau via terminal:
py app.py
```
Akses di browser: **`http://localhost:3000`**.

---

### 🖥️ 7. Panduan Spesifikasi Edge Computer & Komputer Lokal

Proyek ini telah dioptimalkan dengan kuantisasi 4-bit medium (`Q4_K_M`) agar dapat berjalan dingin, cepat, dan stabil di berbagai komputer *Edge* serta laptop lokal tanpa membutuhkan kartu grafis (GPU) diskrit mahal:

| Kategori Perangkat | Tipe, Merk & Seri Edge Computer yang Didukung | Spesifikasi Laptop / PC Lokal | Rekomendasi Model yang Dapat Dipakai |
| :--- | :--- | :--- | :--- |
| **Tier 1: Low Edge (RAM 4 GB – 8 GB) ⭐** | **SBC (Single Board Computer)**: Raspberry Pi 5 (4GB/8GB), Orange Pi 5.<br>**Mini PC Hemat**: Beelink Mini S12 Pro, GMKTec G3, Minisforum UN100 (Prosesor Intel N95 / N100). | Laptop standar, Intel Celeron/Core i3, AMD Ryzen 3, RAM 4GB–8GB. | **🔥 Flagship Edge Agent**: [`Lensetek-Edge-Loop-3B`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF)<br>• Beban RAM: **~2.49 GB** (Sistem ≤ 3.69 GB)<br>• Kecepatan: **18–35 tok/s** (CPU murni, 0 MB VRAM)<br>• *Looped Reasoning, Self-Recovery & Anti-Halusinasi*<br><br>**🪶 Ultra-Light**: `Qwen 2.5 0.5B`<br>• Beban RAM: **~1.15 GB** • Kecepatan: **35–50 tok/s** |
| **Tier 2: Mid Edge (RAM 8 GB – 16 GB)** | **Mini PC Office / Lab**: Beelink EQ12, ASUS NUC, LattePanda 3 Delta, Lenovo ThinkCentre Tiny (Intel N100/N200/i3-N305).<br>**AI Edge SBC**: NVIDIA Jetson Orin Nano (8GB), Orange Pi 5 Plus (16GB). | Acer Aspire, ASUS Vivobook, Lenovo IdeaPad, HP Pavilion (AMD Ryzen 5/7, Intel i5/i7, RAM 8GB–16GB). | **🤖 Model Umum**: `Qwen 2.5 3B`<br>• Beban RAM: **~3.80 GB** • Kecepatan: **18–35 tok/s**<br>• Model Vision: `SmolVLM 500M` (~2.0 GB RAM) |
| **Tier 3: High Edge (RAM 16 GB – 32 GB) 👑** | **Mini PC Workstation**: Beelink SER6/SER8, Minisforum UM790 Pro, Morefine M600 (AMD Ryzen 7/9 APU), Apple Mac Mini (M1/M2/M4).<br>**Industrial Edge**: LattePanda Sigma, Jetson Orin NX (16GB). | Acer Aspire/Swift, Lenovo ThinkPad/Legion, ASUS TUF/Zenbook, Dell XPS, HP Omen, MacBook (RAM 16GB–32GB). | **🧠 Agentic Pro (7B)**: `Qwen 2.5 7B`<br>• Beban RAM: **~6.80 GB** • Kecepatan: **8–18 tok/s**<br>• Cocok untuk Multi-Agent & rantai tugas kompleks |

---

### 🛡️ 8. Arsitektur Keselamatan & Interlock Akuasi Fisik (PM-06)

Lensetek Edge menerapkan batas keselamatan industri yang ketat:
- **Akses Bawaan Hanya-Baca (Read-Only Default)**: Seluruh tool telemetri, polling sensor, register Modbus, dan kueri database beroperasi dalam mode Read-Only secara default.
- **Gerbang Persetujuan Operator (HITL Actuation Interlock)**: Setiap perintah penulisan fisik ke relay, koil PLC, atau aktuator medis wajib menyertakan token otorisasi operator fisik (`hitl_token` berformat `HITL-CONFIRM-XXXX`). Tanpa token yang valid, aksi fisik langsung diblokir dan dicatat ke tabel append-only `safety_audit_log` di SQLite.
- **Bebas Kebocoran Kredensial**: Tidak ada kunci API, password, atau rahasia yang terekspos di kode client-side, bundle frontend, maupun repositori git.
- **Kedaulatan Data Penuh (Air-Gapped)**: Beroperasi 100% offline tanpa internet, patuh penuh terhadap Undang-Undang Perlindungan Data Pribadi (UU PDP No. 27/2022).

---

### ⚖️ 9. Lisensi & Arsitektur Open-Core (Commercial Open-Source / COSS)

Lensetek menerapkan model **Commercial Open-Source (COSS)** yang transparan, memisahkan secara tegas antara bobot terbuka untuk komunitas riset dengan solusi turnkey enterprise:

| Tingkatan (Tier) | Lisensi | Sasaran Pengguna | Komponen yang Disertakan |
| :--- | :--- | :--- | :--- |
| **Community Open-Core & Bobot Model** | **Apache-2.0 / MIT** | Pengembang, Peneliti, Komunitas, UMKM | • Bobot SLM `Lensetek-Edge-Loop-3B` (GGUF & Safetensors)<br>• Edge Studio Web UI & Server API OpenAI-compatible mandiri<br>• Mesin RAG lokal SQLite (0 MB RAM standby, pencarian kosinus SIMD)<br>• Harness agen dasar & Context Compressor 4K |
| **Enterprise Connectors & Kepatuhan** | **Commercial Enterprise** | Pabrik Manufaktur, Klinik 3T, Perusahaan Tambang & Energi | • Konektor Industri Tersertifikasi: Modbus RTU/TCP, CAN J1939, OPC-UA, HL7/DICOM<br>• Enkripsi At-Rest SQLCipher & Kontrol Akses Berbasis Peran (RBAC)<br>• Dashboard Armada Multi-Node & Pembaruan OTA Terpusat<br>• Flywheel Pelatihan Kustom SOP Pabrik dengan GRPO RLVR |
| **Lensetek ARK Turnkey Hardware** | **Turnkey Hardware + Commercial** | Penanggulangan Bencana, Maritim, Pertahanan & Daerah Terpencil | • Kotak komputasi rugged mil-spec IP67 dengan baterai LiFePO4 terintegrasi<br>• Sistem operasi darurat air-gapped Survival Agent HUD pra-instalasi<br>• Antarmuka antena radio VHF/UHF lapangan & Hardware Kill Switch fisik |

---

### 🏆 10. Rapor Evaluasi Benchmark Model & Perbandingan Head-to-Head

Model khusus **`lensetek-edge-loop-3b-q4_k_m.gguf`** telah diuji secara formal menggunakan 300 skenario held-out independen dan dibandingkan langsung dengan model dasar aslinya (*Qwen2.5-3B-Instruct Stock*):

#### Rapor Hard-Metrics (300 Skenario Held-Out):
| Dimensi Metrik | Target Pitch Deck | Hasil Evaluasi Nyata | Status Kelulusan | Catatan Teknis & Kesiapan Lapangan |
| :--- | :---: | :---: | :---: | :--- |
| **Task Completion Rate** | > 95.0% | **100.0%** | **PASSED** | Alur multi-langkah tuntas tanpa stuck loop berkat self-correction mandiri. |
| **Tool-Calling JSON Accuracy** | 100.0% | **100.0%** | **PASSED** | Skema sintaks `<tool_call>` valid 100% tanpa error tanda kutip/format. |
| **Closed-Domain Hallucination Rate** | < 1.0% | **0.0%** | **PASSED** | Disiplin menolak (*Calibrated Abstention*) saat dokumen SOP lokal nihil. |
| **Effort Compliance Rate** | > 90.0% | **96.0%** | **PASSED** | Respons instan pada `[EFFORT:LOW]` (<35 kata) vs mendalam pada `[EFFORT:HIGH]`. |
| **Active Edge RAM Footprint** | ≤ 2.50 GB | **~2.49 GB** | **PASSED** | Beban memori aktif model + 4-bit KV cache pada Mini PC / SBC RAM 4 GB. |

#### Tabel Head-to-Head: Model Asli vs Lensetek-Edge-Loop-3B:
| Dimensi Kemampuan | Model Asli (*Stock Qwen2.5-3B*) | Model Lensetek (*Lensetek-Edge-Loop-3B*) | Keunggulan Operasional |
| :--- | :--- | :--- | :--- |
| **Format Pemanggilan Tool** | Sering mencampur teks basa-basi; error skema ~15%. | **100% format `<tool_call>` murni sejak giliran pertama**. | Backend tidak pernah crash akibat format salah. |
| **Pemulihan saat Error** | Meminta maaf ke pengguna atau berhenti saat error. | **Menganalisis error di `<think>`, perbaiki sintaks, panggil ulang**. | Tugas selesai otomatis tanpa campur tangan teknisi. |
| **Sikap saat Data Kosong** | Mengarang angka dosis/torsi fiktif (~28%). | **Disiplin menolak (*"Data tidak tercantum dalam SOP"*).** | Nol resiko keselamatan di fasilitas medis dan pabrik. |
| **Spesialisasi Konteks** | Data umum web internasional. | **SOP industri Indonesia, boiler sawit, triage bencana ARK**. | Kedaulatan data dan operasional lokal offline. |

> 📄 **Berkas Evaluasi Multibahasa & Log Pengujian Nyata**:
> - **Bahasa Indonesia**: [Laporan Evaluasi Benchmark (.md)](reports/benchmark_evaluation_report_id.md) • [Log Uji Riil Head-to-Head (.md)](reports/head_to_head_test_log_id.md)
> - **English**: [Benchmark Evaluation Report (.md)](reports/benchmark_evaluation_report_en.md) • [Head-to-Head Comparison Log (.md)](reports/head_to_head_test_log_en.md)
> - **简体中文**: [基准评估报告 (.md)](reports/benchmark_evaluation_report_cn.md) • [实测直接对比日志 (.md)](reports/head_to_head_test_log_cn.md)
> - **Data & Matriks**: [Matriks Excel 300 Skenario Held-Out](reports/Hasil_Evaluasi_Benchmark_300_Skenario_Lensetek.xlsx) • [Scorecard JSON](training/eval_scorecard.json)

---

### 🆕 11. Catatan Revisi v3.0 — Permasalahan Sebelumnya & Perbaikannya (`2026-11-23`)

#### ⚠️ Permasalahan yang Ditemukan pada Versi Sebelumnya (v1/v2)
1. ***Catastrophic Forgetting* pada Bahasa Indonesia & Logika Dasar**: Pelatihan sebelumnya memakai 100% template sintetis tanpa sampel obrolan umum dengan `lr=2e-4` (< 1 epoch), sehingga model 3B kehilangan keluwesan Bahasa Indonesia, keliru pada hitungan sederhana, dan sempat bingung/membalik definisi `[EFFORT:LOW/HIGH]`.
2. **Pergeseran Identitas Model**: Karena belum ada sampel penguatan identitas, model sempat memperkenalkan diri menggunakan residu nama model dasar, bukan **Lensetek**.
3. **Korupsi KV Cache 4-Bit (`-ctk q4_0 -ctv q4_0`) & Proses Zombie**: Kompresi KV Cache `q4_0` pada arsitektur Qwen2.5-3B (2 KV Heads) merusak matriks *attention* sehingga memicu keluaran kata acak (*word salad*), ditambah proses zombie `llama-server.exe` yang tetap menahan port `8080`.
4. **Pencemaran Kueri RAG & Tampilan Raw Markdown**: Tag `[EFFORT:HIGH]` ikut terbawa ke pencarian `rag_engine.search()` sehingga menarik potongan dokumen yang tidak relevan, sementara balasan chat masih tampil mentah (`**`, `*`) tanpa indikator loading.

#### ✅ Perbaikan pada Revisi v3.0 (`2026-11-23`)
* **Pembaruan Bobot Model v3.0 (Bobot Lama v1/v2 Dihapus & Diganti)**:
  * Menambahkan **30% General Conversational Replay (`Cluster C7`)** ke dataset `lensetek_edge_loop_3000.jsonl` & `lensetek_eval_heldout_300.jsonl` beserta penyelarasan identitas **Lensetek**.
  * Dilatih ulang dengan `lr=8e-5`, `lora_alpha=16`, `2 epoch penuh`, *cosine scheduler*, dan telah lulus uji *live* (identitas Lensetek, aritmatika `1 + 15 = 16`, serta penolakan anti-halusinasi medis 0 hits) sebelum diekspor ke GGUF `Q4_K_M` baru.
  * Mengimplementasikan loop penuh `GRPOTrainer` + `GRPOConfig` di `training/train_grpo_rlvr.py`.
* **Perbaikan Edge Studio & Runtime (`app.py`)**:
  * Menghapus `-ctk q4_0 -ctv q4_0`, beralih ke `-fa auto`, menambahkan stop tokens Qwen2.5 (`<|im_end|>`, `<|endoftext|>`), `repeat_penalty=1.1`, dan pembersih otomatis proses zombie `llama-server.exe`.
  * Menambahkan **Render Markdown XSS-safe** (dengan blok `<think>` yang bisa dilipat), **indikator loading animasi**, **pembersihan tag `[EFFORT:...]` sebelum pencarian RAG**, **Indeks Folder Proyek otomatis (`/api/rag/index_project`)**, tombol `➕ New Chat`, toggle `🔇 Suara: OFF/ON`, selector Effort (`OFF / LOW / HIGH`), dan tautan `🦙 Llama.cpp WebUI ↗`.

<br>
<hr>

<a id="chinese"></a>
# 🇨🇳 简体中文 (Chinese)

一个独立的本地边缘 AI 工作空间，支持文本推理、视觉图像理解以及具有**打断功能 (Barge-In) 的实时免提语音对话**。内置兼容 **OpenAI 标准的 API 服务端 (`/v1/chat/completions`)**，可直接无缝接入主流 AI Agent 框架（如 **LangChain、CrewAI、AutoGen、OpenAI Python/Node SDK、Cursor 和 Continue.dev**）。

---

### 📥 1. 快速克隆与安装

本项目仓库仅包含轻量级核心代码（约 200 KB），不包含多吉字节（GB）的沉重模型权重文件。

```bash
# 克隆仓库
git clone https://huggingface.co/lensetek/lensetek-edge-ai-agent
cd lensetek-edge-ai-agent

# 安装运行依赖
pip install -r requirements.txt
```

---

### 📦 2. 按需下载模型

使用内置的交互式下载脚本或专属命令行直接从 Hugging Face 获取所需的 GGUF 及语音模型：

| 模型名称与画像 | 格式与体积 | Hugging Face 官方来源 | 一键下载指令 |
| :--- | :---: | :---: | :--- |
| **🧠 Lensetek Edge-Loop 3B** *(旗舰智能体)* | **~1.93 GB** (`Q4_K_M`) | [`lensetek/lensetek-edge-loop-3b-GGUF`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF) | `py download_models.py --loop`<br>[**⬇️ 直接下载 GGUF 权重**](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF/resolve/main/lensetek-edge-loop-3b-q4_k_m.gguf?download=true) |
| **🪶 Qwen 2.5 0.5B Instruct** *(超轻量)* | ~491 MB (`Q4_K_M`) | [`Qwen/Qwen2.5-0.5B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) | `py download_models.py --default` |
| **⭐ Qwen 2.5 3B Instruct** *(通用 Agent)* | ~2.04 GB (`Q4_K_M`) | [`Qwen/Qwen2.5-3B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF) | `py download_models.py --agent` |
| **👑 Qwen 2.5 7B Instruct** *(长链推理)* | ~4.68 GB (`Q4_K_M`) | [`bartowski/Qwen2.5-7B-Instruct-GGUF`](https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF) | `py download_models.py --model qwen2.5-7b` |
| **👁️ SmolVLM 500M** *(多模态视觉)* | ~545 MB (`Q8_0`) | [`HuggingFaceTB/SmolVLM-500M-Instruct-GGUF`](https://huggingface.co/HuggingFaceTB/SmolVLM-500M-Instruct-GGUF) | `py download_models.py --model smolvlm-500m` |
| **🎙️ Whisper Base / Small** *(语音转文字)* | 147 MB / 487 MB | [`ggerganov/whisper.cpp`](https://huggingface.co/ggerganov/whisper.cpp) | `py download_models.py --model whisper-base` |
| **🔊 Kokoro-82M** *(离线语音合成)* | ~337 MB (ONNX) | [`hexgrad/Kokoro-82M`](https://huggingface.co/hexgrad/Kokoro-82M) | `py download_models.py --model kokoro-82m` |

```bash
# 启动交互式下载菜单:
py download_models.py

# 下载旗舰模型 Lensetek Edge-Loop 3B (~1.93 GB):
py download_models.py --loop

# 下载默认轻量级组合 (Qwen 2.5 0.5B + Whisper Base 约 638 MB):
py download_models.py --default

# 下载推荐的 AI Agent 模型 (Qwen 2.5 3B 约 2.0 GB):
py download_models.py --agent

# 检查本地已安装的模型状态:
py download_models.py --status
```

---

### 🔌 3. 兼容 OpenAI 格式的 AI Agent API 接口

本地服务端在 `3000` 端口上提供标准的 OpenAI 兼容端点：
- **Base URL**: `http://localhost:3000/v1`
- **Chat Completions**: `POST http://localhost:3000/v1/chat/completions`
- **Models List**: `GET http://localhost:3000/v1/models`
- **API Key**: `sk-local`（未在 `.env` 中设置时接受任意虚拟密钥）
- **⚡ 自动唤醒 (Auto-Start)**: 收到 AI Agent 请求时自动启动对应模型！
- **🌊 流式传输 (Streaming)**: 完整支持 SSE 数据块流式传输 (`stream: true`) 和非流式响应。

#### Python (OpenAI 官方 SDK):
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local"
)

response = client.chat.completions.create(
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    messages=[
        {"role": "system", "content": "你是一个热心且专业的AI助手。"},
        {"role": "user", "content": "你好！请简要介绍你自己。"}
    ],
    temperature=0.7,
    stream=True
)

for chunk in response:
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

#### LangChain 与 CrewAI:
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="http://localhost:3000/v1",
    api_key="sk-local",
    model="qwen2.5-0.5b-instruct-q4_k_m.gguf",
    temperature=0.7
)

print(llm.invoke("简述多智能体系统（Multi-Agent System）的核心优势！").content)
```

#### cURL 请求:
```bash
curl http://localhost:3000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-local" \
  -d '{
    "model": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
    "messages": [{"role": "user", "content": "你好！"}],
    "stream": false
  }'
```

---

### 📚 4. 内置边缘轻量级知识库检索增强 (Edge RAG - SQLite3 + NumPy)
专为边缘计算与低功耗嵌入式设备量身定制的零后台进程知识库检索系统：
- **0 MB 待机常驻内存**：使用本地嵌入式单文件数据库 (`knowledge_rag.db`)，无需安装庞大的外部向量数据库服务。
- **低于 2ms 的 SIMD 极速向量搜索**：基于 Pure NumPy SIMD 矩阵加速计算余弦相似度，在普通边缘 CPU 上瞬间完成匹配。
- **全格式文档解析**：支持 **PDF** (`pypdf`)、**Word** (`.docx`)、**Markdown** (`.md`)、**TXT**、**CSV** 与 **JSON** 文档一键拖拽解析与向量化切片。
- **无感上下文自动注入**：Web Studio 聊天与 `/v1/chat/completions` API 均会自动检索内部文档并无缝注入上下文，直接赋能各类 AI Agent。

---

### 🎙️ 5. 实时免提语音与语音打断 (Barge-In)
- **⚡ 自动打断 (Auto Barge-In)**: 在 AI 发声时直接开口说话，系统自动检测人声并立即停止 AI 播放 (*全双工对话*)。
- **✋ 手动打断**: 点击橙色 **Sela AI** 按钮或点击 **Voice Orb** 立即切断播放。
- **🌐 3 款高质语音引擎**: Edge-TTS (微软云端超自然拟真语音)、Kokoro-82M (100% 离线 StyleTTS2 录音室级音质) 与 Piper TTS (100% 离线极速轻量)。

---

### 🚀 6. 启动本地服务
```bash
# Windows 单击启动:
start.bat

# 或命令行运行:
py app.py
```
在浏览器中打开：**`http://localhost:3000`**。

---

### 🖥️ 7. 边缘计算设备与本地电脑硬件适配指南

本项目全面采用 4 位中等精度量化 (`Q4_K_M`)，可在无独立 GPU 的普通本地笔记本电脑以及边缘计算硬件（Edge Computer）上流畅、冷静、低功耗运行：

| 硬件梯队 | 支持的边缘硬件类型、品牌与型号 | 适用的本地笔记本 / PC 配置 | 推荐运行模型类别 |
| :--- | :--- | :--- | :--- |
| **第一梯队：轻量边缘 (RAM 4 GB – 8 GB) ⭐** | **单板计算机 (SBC)**: 树莓派 5 (Raspberry Pi 5 4GB/8GB)、香橙派 5 (Orange Pi 5)。<br>**入门 Mini PC**: 零刻 (Beelink Mini S12 Pro)、极摩客 (GMKTec G3)、铭凡 (Minisforum UN100)（Intel N95/N100 处理器）。 | 普通办公笔记本，Intel 赛扬/酷睿 i3、AMD 锐龙 3，4GB–8GB 内存。 | **🔥 旗舰专用模型**: [`Lensetek-Edge-Loop-3B`](https://huggingface.co/lensetek/lensetek-edge-loop-3b-GGUF)<br>• 运行内存: **约 2.49 GB** (整机 ≤ 3.69 GB)<br>• 推理速度: **18–35 tokens/s** (纯 CPU, 0 MB 显存)<br>• *循环推理、自主纠错自愈与闭域零幻觉*<br><br>**🪶 超轻量模型**: `Qwen 2.5 0.5B`<br>• 内存占用: **约 1.15 GB** • 生成速率: **35–50 tokens/s** |
| **第二梯队：中端边缘 (RAM 8 GB – 16 GB)** | **商用/工控 Mini PC**: 零刻 EQ12、华硕 NUC、LattePanda 3 Delta、联想 ThinkCentre Tiny（Intel N100/N200/i3-N305）。<br>**AI 边缘开发板**: 英伟达 Jetson Orin Nano (8GB)、香橙派 5 Plus (16GB)。 | 宏碁 (Acer Aspire)、华硕 (Vivobook)、联想 (IdeaPad)、惠普 (Pavilion)（AMD 锐龙 5/7、Intel 酷睿 i5/i7，8GB–16GB 内存）。 | **🤖 原生通用 Agent**: `Qwen 2.5 3B`<br>• 内存占用: **约 3.80 GB** • 生成速率: **18–35 tokens/s**<br>• 视觉模型: `SmolVLM 500M` (约 2.0 GB) |
| **第三梯队：高性能边缘 (RAM 16 GB – 32 GB) 👑** | **高性能工作站 Mini PC**: 零刻 (SER6/SER8)、铭凡 (UM790 Pro)、摩方 M600（AMD 锐龙 7/9 APU）、苹果 Mac Mini (M1/M2/M4)。<br>**工业级边缘端**: LattePanda Sigma、Jetson Orin NX (16GB)。 | 宏碁 (Acer Aspire/Swift)、联想 (ThinkPad/Legion)、华硕 (TUF/Zenbook)、戴尔 (XPS)、苹果 MacBook (16GB–32GB 统一内存)。 | **🧠 深度推理 Agent (7B)**: `Qwen 2.5 7B`<br>• 内存占用: **约 6.80 GB** • 生成速率: **8–18 tokens/s**<br>• 适合复杂多 Agent 协同与长链推理 |

---

### 🛡️ 8. 安全架构与物理执行机构联锁机制 (PM-06)

Lensetek Edge 实施严格的工业安全边界防护：
- **默认只读访问 (Read-Only Default)**：所有传感器轮询、Modbus 寄存器读取及数据库检索默认以严格只读模式运行。
- **人工干预确认联锁 (HITL Actuation Interlock)**：向物理继电器、PLC 寄存器或医疗执行端写入控制指令时，必须附带操作员现场确认令牌（`hitl_token`，格式如 `HITL-CONFIRM-XXXX`）。未提供有效令牌时系统严格拦截，并将拦截记录追加入 SQLite `safety_audit_log` 审计表。
- **凭据零泄露 (Zero Credential Exposure)**：前端代码及版本库中杜绝任何公网 API 密钥与敏感凭据。
- **脱网数据主权保障**：100% 离线脱网运行，满足各项数据安全合规要求。

---

### ⚖️ 9. 许可证与开放核心架构 (Open-Core / COSS)

Lensetek 采用清晰透明的**商业开源（COSS）**架构，严格区分开源社区开放权重与企业级闭源套件：

| 授权层级 | 许可证 | 目标客群 | 包含组件 |
| :--- | :--- | :--- | :--- |
| **社区开源核心 (Open-Core & Weights)** | **Apache-2.0 / MIT** | 开发者、研究人员、极客与中小企业 | • `Lensetek-Edge-Loop-3B` SLM 权重（GGUF 及 Safetensors）<br>• 独立 Edge Studio Web UI 及 OpenAI 兼容 API 服务端<br>• 本地 SQLite RAG 引擎（0 MB 待机内存，SIMD 向量余弦搜索）<br>• 基础智能体运行底座与 4K 上下文压缩器 |
| **企业级工业连接器与合规套件** | **商业企业授权 (Commercial)** | 现代化工厂、医疗机构、矿山及能源集团 | • 认证工业连接器：Modbus RTU/TCP、CAN J1939、OPC-UA、HL7/DICOM<br>• SQLCipher 静态数据落盘加密与基于角色的权限控制 (RBAC)<br>• 多节点集群统一监控与 OTA 固件下发看板<br>• 专属企业标准作业程序 (SOP) 微调与 GRPO 数据飞轮 |
| **Lensetek ARK 应急军工级硬件终端** | **硬件整机 + 商业授权** | 应急救援、海事巡防、边防哨所及极限野外场景 | • IP67 军工级三防加固边缘计算整机，内置磷酸铁锂（LiFePO4）应急电池组<br>• 预装离线脱网 Survival Agent 救援仪表板<br>• 双频 VHF/UHF 野战天线接口与物理硬件断网自毁保护开关 |

---

### 🏆 10. 模型基准评测报告与原生基座横向对比 (Head-to-Head)

专用模型 **`lensetek-edge-loop-3b-q4_k_m.gguf`** 已通过 300 条独立保留测试集的严格评测，并与原生基座模型（*Qwen2.5-3B-Instruct*）进行了直接对比：

#### 核心硬指标成绩单（300 条独立测试集）：
| 评测维度 | 目标基准 | 实测结果 | 达标状态 | 技术说明 |
| :--- | :---: | :---: | :---: | :--- |
| **任务闭环完成率 (Task Completion)** | > 95.0% | **100.0%** | **PASSED (通过)** | 零死循环，多轮执行故障时具备完全自主纠错能力。 |
| **工具调用 JSON 精度** | 100.0% | **100.0%** | **PASSED (通过)** | 严格遵循原生 `<tool_call>` 语法规范，无格式断裂。 |
| **闭域文档幻觉率** | < 1.0% | **0.0%** | **PASSED (通过)** | 标定如实拒答：本地上下文未命中时坚决不编造数据。 |
| **思考循环合规率 (Effort)** | > 90.0% | **96.0%** | **PASSED (通过)** | `[EFFORT:LOW]` 极速响应（<35 字）与 `[EFFORT:HIGH]` 深度推理严格对应。 |
| **边缘整机活跃内存** | ≤ 2.50 GB | **~2.49 GB** | **PASSED (通过)** | 4-bit KV Cache 优化，在低成本 4GB 内存硬件上极速流畅运行。 |

#### 原生模型 vs Lensetek 横向能力对比表：
| 关键能力维度 | 原生基座模型 (*Stock Qwen2.5-3B*) | 专用模型 (*Lensetek-Edge-Loop-3B*) | 实际业务工程优势 |
| :--- | :--- | :--- | :--- |
| **工具调用格式规范** | 常夹杂自然语言客套话；JSON 格式报错率 ~15%。 | **首轮 100% 纯净输出 `<tool_call>` 机器指令**。 | 智能体调度管道零语法崩溃。 |
| **遭遇故障自主恢复** | 输出道歉声明或直接中断停止。 | **在 `<think>` 中解析错误码，自主修正参数重试**。 | 无需工程师现场干预，任务自主闭环。 |
| **知识库无命中时的表现** | 凭空猜测编造虚假参数与剂量（~28%）。 | **严谨标定拒答（如实提示“本地 SOP 未检索到”）**。 | 杜绝工控与医疗急救场景的致命风险。 |
| **本地领域知识对齐** | 泛化的互联网公域知识。 | **对齐印尼与区域工业标准、锅炉遥测与野外救援**。 | 边缘断网离线环境下的数据与运营主权。 |

> 📄 **多语言完整基准评测报告与实测日志下载**：
> - **简体中文**: [基准评估报告 (.md)](reports/benchmark_evaluation_report_cn.md) • [实测直接对比日志 (.md)](reports/head_to_head_test_log_cn.md)
> - **English**: [Benchmark Evaluation Report (.md)](reports/benchmark_evaluation_report_en.md) • [Head-to-Head Comparison Log (.md)](reports/head_to_head_test_log_en.md)
> - **Bahasa Indonesia**: [Laporan Evaluasi Benchmark (.md)](reports/benchmark_evaluation_report_id.md) • [Log Uji Riil Head-to-Head (.md)](reports/head_to_head_test_log_id.md)
> - **评测数据与矩阵**: [300 条测试集评测 Excel 矩阵](reports/Hasil_Evaluasi_Benchmark_300_Skenario_Lensetek.xlsx) • [Scorecard JSON](training/eval_scorecard.json)


