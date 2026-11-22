---
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

</div>

<a id="english"></a>
# 🇬🇧 English

A self-contained local AI workspace featuring text inference, vision understanding, and **Realtime Hands-Free Voice with Barge-In (Interruption)** capability. It includes a built-in **OpenAI-Compatible API Server (`/v1/chat/completions`)** designed for autonomous AI agents (**LangChain, CrewAI, AutoGen, OpenAI Python/Node SDK, Cursor, and Continue.dev**).

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

Download your preferred GGUF and Voice models directly using the interactive downloader:

```bash
# Interactive menu:
py download_models.py

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
| **Tier 1: Low Edge (4 GB – 8 GB RAM)** | **SBCs**: Raspberry Pi 5 (4GB/8GB), Orange Pi 5, Rock 5B.<br>**Mini PCs**: Intel N95/N100 (Beelink Mini S12, GMKTec G3, Minisforum UN100). | Intel Core i3 / Celeron, AMD Ryzen 3, 4GB–8GB RAM. | **🪶 Ultra-Light**: `Qwen 2.5 0.5B`<br>• RAM footprint: **~1.15 GB**<br>• Speed: **35–50 tok/s** |
| **Tier 2: Mid Edge (8 GB – 16 GB RAM) ⭐** | **Mini PCs**: Intel N100/N200/Core i3-N305 (Beelink EQ12, ASUS NUC, LattePanda 3 Delta).<br>**AI SBCs**: NVIDIA Jetson Orin Nano (8GB), Orange Pi 5 Plus (16GB). | Acer Aspire, ASUS Vivobook, Lenovo IdeaPad, HP Pavilion (AMD Ryzen 5/7, Intel i5/i7, 8GB–16GB RAM). | **🤖 Agentic Fast (3B)**: `Qwen 2.5 3B`<br>• RAM footprint: **~3.80 GB**<br>• Speed: **18–35 tok/s**<br>• Vision: `SmolVLM 500M` |
| **Tier 3: High Edge (16 GB – 32 GB RAM) 👑** | **Workstation Mini PCs**: AMD Ryzen 7/9 APUs (Beelink SER6/SER8, Minisforum UM790 Pro, Morefine M600, Apple Mac Mini M1/M2/M4).<br>**Industrial Edge**: LattePanda Sigma, Jetson Orin NX (16GB). | Acer Aspire/Swift, Lenovo ThinkPad/Legion, ASUS TUF/Zenbook, Dell XPS, MacBook (16GB–32GB RAM). | **🧠 Agentic Pro (7B)**: `Qwen 2.5 7B`<br>• RAM footprint: **~6.80 GB**<br>• Speed: **8–18 tok/s**<br>• Multi-Agent reasoning & complex chains |

<br>
<hr>

<a id="bahasa-indonesia"></a>
# 🇮🇩 Bahasa Indonesia

Aplikasi AI lokal mandiri (*self-contained*) untuk teks, multimodal visual (vision), dan percakapan suara **Realtime Hands-Free Voice dengan fitur Sela Bicara (Barge-In)**. Dilengkapi **OpenAI-Compatible API Server (`/v1/chat/completions`)** agar dapat langsung dihubungkan ke berbagai framework AI Agent (**LangChain, CrewAI, AutoGen, OpenAI Python/Node SDK, Cursor, dan Continue.dev**).

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

Unduh model GGUF dan Audio langsung menggunakan modul interaktif:

```bash
# Menu interaktif visual:
py download_models.py

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
| **Tier 1: Low Edge (RAM 4 GB – 8 GB)** | **SBC (Single Board Computer)**: Raspberry Pi 5 (4GB/8GB), Orange Pi 5.<br>**Mini PC Hemat**: Beelink Mini S12 Pro, GMKTec G3, Minisforum UN100 (Prosesor Intel N95 / N100). | Laptop standar, Intel Celeron/Core i3, AMD Ryzen 3, RAM 4GB–8GB. | **🪶 Ultra-Light**: `Qwen 2.5 0.5B`<br>• Beban RAM: **~1.15 GB**<br>• Kecepatan: **35–50 tok/s** |
| **Tier 2: Mid Edge (RAM 8 GB – 16 GB) ⭐** | **Mini PC Office / Lab**: Beelink EQ12, ASUS NUC, LattePanda 3 Delta, Lenovo ThinkCentre Tiny (Intel N100/N200/i3-N305).<br>**AI Edge SBC**: NVIDIA Jetson Orin Nano (8GB), Orange Pi 5 Plus (16GB). | Acer Aspire, ASUS Vivobook, Lenovo IdeaPad, HP Pavilion (AMD Ryzen 5/7, Intel i5/i7, RAM 8GB–16GB). | **🤖 Agentic Fast (3B)**: `Qwen 2.5 3B`<br>• Beban RAM: **~3.80 GB**<br>• Kecepatan: **18–35 tok/s**<br>• Model Vision: `SmolVLM 500M` |
| **Tier 3: High Edge (RAM 16 GB – 32 GB) 👑** | **Mini PC Workstation**: Beelink SER6/SER8, Minisforum UM790 Pro, Morefine M600 (AMD Ryzen 7/9 APU), Apple Mac Mini (M1/M2/M4).<br>**Industrial Edge**: LattePanda Sigma, Jetson Orin NX (16GB). | Acer Aspire/Swift, Lenovo ThinkPad/Legion, ASUS TUF/Zenbook, Dell XPS, HP Omen, MacBook (RAM 16GB–32GB). | **🧠 Agentic Pro (7B)**: `Qwen 2.5 7B`<br>• Beban RAM: **~6.80 GB**<br>• Kecepatan: **8–18 tok/s**<br>• Cocok untuk Multi-Agent & rantai tugas kompleks |

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

使用内置的交互式下载脚本直接从 Hugging Face 获取所需的 GGUF 及语音模型：

```bash
# 启动交互式下载菜单:
py download_models.py

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
| **第一梯队：轻量边缘 (RAM 4 GB – 8 GB)** | **单板计算机 (SBC)**: 树莓派 5 (Raspberry Pi 5 4GB/8GB)、香橙派 5 (Orange Pi 5)。<br>**入门 Mini PC**: 零刻 (Beelink Mini S12 Pro)、极摩客 (GMKTec G3)、铭凡 (Minisforum UN100)（Intel N95/N100 处理器）。 | 普通办公笔记本，Intel 赛扬/酷睿 i3、AMD 锐龙 3，4GB–8GB 内存。 | **🪶 超轻量模型**: `Qwen 2.5 0.5B`<br>• 内存占用: **约 1.15 GB**<br>• 生成速率: **35–50 tokens/s** |
| **第二梯队：中端边缘 (RAM 8 GB – 16 GB) ⭐** | **商用/工控 Mini PC**: 零刻 EQ12、华硕 NUC、LattePanda 3 Delta、联想 ThinkCentre Tiny（Intel N100/N200/i3-N305）。<br>**AI 边缘开发板**: 英伟达 Jetson Orin Nano (8GB)、香橙派 5 Plus (16GB)。 | 宏碁 (Acer Aspire)、华硕 (Vivobook)、联想 (IdeaPad)、惠普 (Pavilion)（AMD 锐龙 5/7、Intel 酷睿 i5/i7，8GB–16GB 内存）。 | **🤖 极速 Agent (3B)**: `Qwen 2.5 3B`<br>• 内存占用: **约 3.80 GB**<br>• 生成速率: **18–35 tokens/s**<br>• 视觉模型: `SmolVLM 500M` |
| **第三梯队：高性能边缘 (RAM 16 GB – 32 GB) 👑** | **高性能工作站 Mini PC**: 零刻 (SER6/SER8)、铭凡 (UM790 Pro)、摩方 M600（AMD 锐龙 7/9 APU）、苹果 Mac Mini (M1/M2/M4)。<br>**工业级边缘端**: LattePanda Sigma、Jetson Orin NX (16GB)。 | 宏碁 (Acer Aspire/Swift)、联想 (ThinkPad/Legion)、华硕 (TUF/Zenbook)、戴尔 (XPS)、苹果 MacBook (16GB–32GB 统一内存)。 | **🧠 深度推理 Agent (7B)**: `Qwen 2.5 7B`<br>• 内存占用: **约 6.80 GB**<br>• 生成速率: **8–18 tokens/s**<br>• 适合复杂多 Agent 协同与长链推理 |
