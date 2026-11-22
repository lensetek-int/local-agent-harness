# 📚 Complete Guide: Ingesting SOP Documents into Lensetek Edge AI via Local RAG (Zero Retraining Required)

This guide provides step-by-step instructions for adding **SOPs (Standard Operating Procedures)**, factory machinery operation manuals, technical work instructions, or clinical guidelines into **Lensetek Edge AI**.

> [!IMPORTANT]
> **Your AI Model is Fixed & Production-Ready (`lensetek-edge-loop-3b-q4_k_m.gguf`).**  
> You **DO NOT NEED** to retrain, fine-tune, or modify the AI model weights when adding or updating SOP documents. Domain knowledge is injected dynamically using **EdgeRAG (Retrieval-Augmented Generation)** powered by a self-contained local SQLite vector engine.

---

## 🌟 Why RAG Instead of Model Retraining?

1. **Instant Ingestion (< 2 Seconds)**: Once uploaded, the model can answer questions regarding the new SOP immediately.
2. **Zero-Hallucination & Calibrated Abstention**: Lensetek-Edge-Loop-3B is specifically aligned to cite only verified local document text and refuse speculation if information is unindexed.
3. **Effortless Updates & Maintenance**: When an SOP is revised (e.g., version 2026 to 2027), simply delete the old file and upload the new one—no expensive GPU training hours required.
4. **100% Private & Air-Gapped**: All documents are stored and processed strictly on your local device (`knowledge_rag.db`), with zero data transmitted to the cloud.

---

## 📄 Supported SOP Document Formats

The built-in text extraction engine automatically handles:
* **Digital Documents**: `.pdf` (Official printed SOPs, equipment operating manuals)
* **Microsoft Word**: `.docx` (Office SOP drafts and procedures)
* **Plain Text & Markdown**: `.txt`, `.md` (Technical checklists, work instructions)
* **Structured Data & Tables**: `.csv`, `.json`, `.log` (Sensor thresholds, machine fault codes)

---

## 🛠️ 3 Methods to Add SOP Documents

```
                      ┌──────────────────────────────────────────────┐
                      │          CHOOSE YOUR INGESTION METHOD        │
                      └──────────────────────┬───────────────────────┘
                                             │
             ┌───────────────────────────────┼───────────────────────────────┐
             ▼                               ▼                               ▼
     [ METHOD 1: VISUAL ]            [ METHOD 2: TERMINAL ]          [ METHOD 3: REST API ]
     Open Studio Web UI              Use py ingest_sop.py            Send to REST Endpoint
     Click 'Dokumen RAG'             Batch ingest whole folders      Automate from factory ERP
     Drag & Drop Files               Fast for dozens of files        Backend system integration
```

---

### METHOD 1: Via Web Studio UI (Recommended for Operators)

1. **Start the Application**:
   Double-click `start.bat` (or execute `py app.py` in your terminal).
2. **Open Browser**:
   Navigate to [`http://localhost:3000`](http://localhost:3000).
3. **Open RAG Knowledge Base**:
   On the top header bar, click the green button **`📚 Dokumen RAG`**.
4. **Upload Your SOP File**:
   * Drag and drop your `.pdf`, `.docx`, or `.txt` file into the upload zone, or click to browse files.
5. **Automatic Processing**:
   * The system chunks the text semantically, generates vector embeddings, and stores them in `knowledge_rag.db`.
   * A confirmation badge `✓ Berhasil diindeks` will display with total character and chunk counts.
6. **Query the Model**:
   * Close the modal, ensure the RAG toggle button near the chat box shows **`✓ Aktif`**.
   * Ask your question, for example:  
     *"What are the boiler operating pressure limits for unit GEN-09 according to the SOP?"*  
     The model will ground its answer directly on your uploaded SOP!

---

### METHOD 2: Via Command-Line Script (`py ingest_sop.py`)

Ideal for power users and batch ingestion of multiple manuals:

#### 1. Ingest a Single SOP File
```bash
py ingest_sop.py SOP_Boiler_GEN09.pdf
```

#### 2. Ingest an Entire Folder of SOPs (Batch Mode)
Place all your SOP files into a folder (e.g., `./my_sops`), then run:
```bash
py ingest_sop.py --folder ./my_sops
```
*Sample Output:*
```text
[INFO] Found 6 SOP files in 'C:\...\my_sops'...
  [✓] Indexed: SOP_Boiler_GEN09.pdf (12 chunks)
  [✓] Indexed: Factory_Safety_Protocol.docx (8 chunks)
  [✓] Indexed: Emergency_Clinical_Triage.pdf (15 chunks)
[✓] Complete: 6/6 files successfully indexed into RAG!
```

#### 3. View Currently Indexed Documents
```bash
py ingest_sop.py --list
```

#### 4. Test Semantic Search Directly (Without Booting LLM)
```bash
py ingest_sop.py --search "boiler pressure limits"
```

#### 5. Clear All Documents from Knowledge Base
```bash
py ingest_sop.py --clear
```

---

### METHOD 3: Via REST API (`/api/rag/upload`)

Ideal for integrating with existing factory MES, ERP, or internal web portals:

* **Endpoint**: `POST http://localhost:3000/api/rag/upload`
* **Content-Type**: `application/json`

#### Ingest Plain Text SOP:
```bash
curl -X POST http://localhost:3000/api/rag/upload \
  -H "Content-Type: application/json" \
  -d '{"filename": "SOP_Turbine_Limits.txt", "text": "Bearing temperature must not exceed 75°C under continuous load."}'
```

#### Ingest Base64 Encoded PDF / Word Document:
```json
{
  "filename": "SOP_Medical_Protocol.pdf",
  "content_base64": "data:application/pdf;base64,JVBERi0xLjQKJ..."
}
```

---

## 🔍 How RAG Works with Lensetek-Edge-Loop-3B

```
┌─────────────────────────────────┐
│ User Query:                     │
│ "What is the boiler max limit?" │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐       Sub-millisecond NumPy Vector Search
│    EdgeRAG Search Engine        │ ◄────────────────────────────────────────┐
└────────────────┬────────────────┘                                          │
                 │ Retrieved chunk: "Max safe pressure is 42 bar (SOP-09)"   │
                 ▼                                                           │
┌─────────────────────────────────┐                                          │
│ Augmented Context Injection:    │                               ┌──────────┴────────┐
│ [VERIFIED LOCAL SOP CONTEXT]    │                               │  knowledge_rag.db │
│ Section 4: Safe limit = 42 bar. │                               │  (Local SQLite)   │
└────────────────┬────────────────┘                               └───────────────────┘
                 │
                 ▼
┌───────────────────────────────────────────────┐
│  🧠 Model: lensetek-edge-loop-3b-q4_k_m.gguf  │
│  (Pure CPU Inference, RAM 2.49 GB)            │
└────────────────┬──────────────────────────────┘
                 │
                 ▼
┌───────────────────────────────────────────────┐
│ Grounded & Precise Output:                    │
│ "According to SOP GEN-09 Section 4, the safe  │
│  operating limit is 42 bar."                  │
└───────────────────────────────────────────────┘
```

---

## 🔄 Updating (Revising) SOP Documents

When factory regulations or operational guidelines are updated:
1. Open the **`📚 Dokumen RAG`** modal in the Web Studio.
2. Click the **Delete** icon next to the outdated SOP.
3. Upload the newly revised SOP file.
4. **Done!** The AI model immediately references the revised standard with zero server downtime.
