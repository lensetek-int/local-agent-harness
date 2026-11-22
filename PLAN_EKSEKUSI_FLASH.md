# ⚡ PLAN EKSEKUSI ATOMIK — GEMINI 3.8 FLASH (MEDIUM)
## Lensetek Edge AI Agent & `Lensetek-Edge-Loop-3B` (Pre-Mortem Hardened v2.0)

> **Petunjuk Penggunaan untuk Agen (Gemini 3.8 Flash Medium):**
> Dokumen ini dirancang sebagai *blueprint eksekusi deterministik*. Kerjakan **1 Sprint dalam 1 sesi/perintah** (atau berurutan dari Sprint 1 → Sprint 6) agar tidak terjadi *context overflow* atau kesalahan sintaks.  
> **Aturan Emas:**
> 1. **Selalu baca baris target terlebih dahulu** dengan `read_file` (`StartLine` & `EndLine`) sebelum menyunting file besar seperti `app.py` (5.036 baris).
> 2. **DILARANG** menjalankan `git push` atau `HfApi.upload_*` ke remote selama pengerjaan Sprint, kecuali pengguna menginstruksikan secara eksplisit di akhir.
> 3. **DILARANG** menulis kredensial, API key, `HF_TOKEN`, atau rahasia ke dalam kode atau frontend.
> 4. **WAJIB** jalankan **Perintah Verifikasi** di akhir tiap Sprint dan pastikan output-nya sesuai **Ekspektasi Lulus**.

---

## 📋 Peta 6 Sprint Atomik & Cakupan Mitigasi Pre-Mortem

| Sprint | Judul Pekerjaan | File Target | Pre-Mortem Teratasi | Estimasi Beban Flash |
| :---: | :--- | :--- | :---: | :---: |
| **Sprint 1** | Runtime Hardening, 4-Bit KV Cache & Safety Interlock | `safety_guard.py` (baru), `app.py` (edit lokal baris 18–26 & 244–275) | `PM-04`, `PM-05`, `PM-06` | Ringan (~150 baris) |
| **Sprint 2** | Upgrade Recall RAG: Kamus Sinonim ID-EN & Query Expansion | `rag_engine.py` (edit fungsi `search` & tambah helper) | `PM-03` | Ringan (~100 baris) |
| **Sprint 3** | Parametric Combinatorial Dataset Generator & Native Qwen2.5 `<tool_call>` | `training/dataset_generator.py` (rewrite terstruktur) | `PM-01`, `PM-07` | Sedang (~320 baris) |
| **Sprint 4** | GRPO RLVR Script, Model-Agnostic SFT & Evaluasi Benchmark | `training/train_runpod.py` (edit), `training/train_grpo_rlvr.py` (baru), `training/evaluate_model.py` (baru) | `PM-02`, `PM-04`, `PM-10` | Sedang (~350 baris) |
| **Sprint 5** | Multi-Project Harness (`usecase/edge-ai-agent` & `usecase/survival-agent`) + Context Compressor | `usecase/edge-ai-agent/*`, `usecase/survival-agent/*` | `PM-08`, `PM-09` | Sedang (2 proyek TS) |
| **Sprint 6** | Model Card Honest Framing & Open-Core (COSS) Licensing Table | `model_card/README.md`, `model_card/README_base.md`, `README.md` | `PM-02`, `PM-07` | Ringan (Dokumentasi) |

---

## 🔧 SPRINT 1: Runtime Hardening, 4-Bit KV Cache & Safety Interlock (`PM-04`, `PM-05`, `PM-06`)

### 1. Target File
- **Buat baru:** `safety_guard.py`
- **Edit:** `app.py` (hanya baris **17–26** dan **244–276** — jangan baca atau ubah bagian UI lainnya!)

### 2. Spesifikasi Kode Eksak
1. Di `safety_guard.py`:
   - Gunakan `sqlite3`, `json`, `hashlib`, `datetime`, `os` (zero dependensi eksternal tambahan).
   - Konstanta `ACTUATION_TOOLS = {"gpio_write", "modbus_write", "canbus_send", "relay_toggle", "bash_exec"}` dan `READ_ONLY_DEFAULT = True`.
   - Kelas `SafetyGuard(db_path=None)` yang default mengarah ke `knowledge_rag.db` di `BASE_DIR`.
   - Method `_init_audit_table()`: membuat tabel SQLite append-only `safety_audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, tool_name TEXT, params_json TEXT, decision TEXT, reason TEXT, hitl_token_hash TEXT)`.
   - Method `generate_hitl_challenge(tool_name, params)` -> menghasilkan pesan tantangan konfirmasi manusia + token HMAC/SHA256 deterministik jangka pendek untuk pengujian CLI/UI.
   - Method `check_permission(tool_name, params, token=None, allow_write=False)`:
     - Jika `tool_name` bukan bagian dari `ACTUATION_TOOLS`: kembalikan `{"allowed": True, "mode": "READ_ONLY", "reason": "Safe telemetry/query tool"}` dan catat log `ALLOWED_READ`.
     - Jika `tool_name` ada di `ACTUATION_TOOLS`:
       - Jika `READ_ONLY_DEFAULT` dan `not allow_write` atau `not token`: tolak eksekusi! Catat log `BLOCKED_HITL_REQUIRED`, kembalikan `{"allowed": False, "requires_hitl": True, "reason": "Actuation tool blocked in Read-Only default mode. Human-in-the-Loop approval token required."}`.
       - Jika `token` valid sesuai `verify_hitl_token`: izinkan & catat `ALLOWED_HITL_VERIFIED`.
   - Method `get_clinical_disclaimer(lang="id")`: mengembalikan disclaimer baku non-diagnostik Kemenkes/START triage untuk disisipkan pada modul medis/survival.
2. Di `app.py`:
   - **Baris 17–26:** Ubah hardcoded `.exe` menjadi helper lintas-OS (`_bin_name("llama-server")`, `_bin_name("whisper-cli")`, `_bin_name("piper")`) menggunakan `sys.platform == "win32"`. Tetap pertahankan variabel `LLAMA_SERVER_EXE`, `WHISPER_EXE`, `PIPER_EXE` agar kode pemanggil lain tidak rusak.
   - **Baris 244–276 (`start_llama_server`):** Tambahkan flag kuantisasi KV-cache 4-bit dan Flash Attention ke `cmd`:
     ```python
     cmd = [
         LLAMA_SERVER_EXE,
         "-m", model_path,
         "--host", "127.0.0.1",
         "--port", str(LLAMA_PORT),
         "-c", "4096",
         "-ctk", "q4_0",
         "-ctv", "q4_0",
         "-fa",
     ]
     ```
     *(Catatan: pastikan flag `--host`, `--port`, `--mmproj`, dan `--temp` tetap dipertahankan seperti semula).*

### 3. Guardrail Khusus
- Jangan mengubah endpoint API atau HTML/JS di dalam `app.py` pada Sprint ini.
- Jangan sentuh `knowledge_rag.db` data RAG yang sudah ada (cukup `CREATE TABLE IF NOT EXISTS safety_audit_log`).

### 4. Perintah Verifikasi & Ekspektasi Lulus
```powershell
py -m py_compile safety_guard.py app.py
py -c "from safety_guard import SafetyGuard; g = SafetyGuard(); r1 = g.check_permission('rag_search', {'q':'boiler'}); r2 = g.check_permission('modbus_write', {'reg':40012}, token=None); print('READ:', r1['allowed'], 'WRITE_NO_TOKEN:', r2['allowed'], r2['requires_hitl']); assert r1['allowed'] is True and r2['allowed'] is False and r2['requires_hitl'] is True"
py -c "s = open('app.py', encoding='utf-8').read(); assert '-ctk' in s and 'q4_0' in s and '-ctv' in s; print('KV_CACHE_4BIT_OK')"
```
Ekspektasi output:
`READ: True WRITE_NO_TOKEN: False True` dan `KV_CACHE_4BIT_OK` tanpa error.

### 5. Prompt Siap Pakai untuk Gemini 3.8 Flash (Medium)
> **Salin-tempel prompt ini:**  
> `Baca PLAN_EKSEKUSI_FLASH.md bagian SPRINT 1. Kerjakan Sprint 1 secara lengkap pada safety_guard.py dan app.py (baca hanya baris 1-35 dan 240-280 pada app.py terlebih dahulu). Setelah selesai, jalankan seluruh perintah verifikasi Sprint 1 dan laporkan hasilnya tanpa melakukan git push.`

---

## 🔍 SPRINT 2: Upgrade Recall RAG: Kamus Sinonim ID-EN & Query Expansion (`PM-03`)

### 1. Target File
- **Edit:** `rag_engine.py` (baca baris **70–115** dan **295–385**)

### 2. Spesifikasi Kode Eksak
1. Tambahkan konstanta `DOMAIN_SYNONYMS` di `rag_engine.py` berisi minimal **50 entri pemetaan istilah** (Indonesia ↔ Inggris ↔ Singkatan Industri & Medis 3T):
   - Contoh entri wajib:
     - `"panas"`: `["overheating", "suhu tinggi", "temperatur", "thermal"]`
     - `"genset"`: `["generator", "diesel", "cummins", "pembangkit"]`
     - `"sawit"` / `"pks"`: `["palm oil", "kelapa sawit", "cangkang", "ketel uap", "boiler"]`
     - `"ketel"`: `["boiler", "steam", "uap", "bar", "safety valve"]`
     - `"epinefrin"`: `["adrenalin", "anafilaksis", "syok", "alergi berat"]`
     - `"demam"`: `["panas badan", "hipertermia", "antipiretik", "parasetamol"]`
     - `"sesak"`: `["dispnea", "respirasi", "napas cepat", "oksigen", "start triage"]`
     - `"pendarahan"`: `["hemoragik", "arteri", "torniket", "luka terbuka", "balut tekan"]`
     - `"tekanan darah tinggi"`: `["hipertensi", "tensi tinggi", "sistolik"]`
     - `"infus"`: `["saline", "nacl", "cairan intravena", "rehidrasi"]`
     - `"aki"`: `["baterai", "battery", "dc 12v", "solar panel", "inverter", "mppt"]`
     - `"antena"`: `["dipole", "vhf", "uhf", "radio", "156.8", "orari", "rapi"]`
     - `"air bersih"`: `["purifikasi", "filtrasi", "sodis", "arang aktif", "kaporit"]`
     - `"oli"`: `["pelumas", "lubricant", "sae 15w-40", "viscosity", "kompresor"]`
     - `"alat berat"`: `["excavator", "dump truck", "can-bus", "obd", "j1939", "ecu"]`
2. Tambahkan method `expand_query(self, query: str) -> str` pada class `EdgeRAG`:
   - Deteksi kecocokan token atau frasa dari `DOMAIN_SYNONYMS` secara case-insensitive.
   - Gabungkan kata asli dengan sinonim unik tanpa meledakkan panjang string (maksimal +12 kata ekspansi).
   - Pastikan query asli tetap berada di depan sehingga exact FTS5 match tetap diprioritaskan.
3. Di `EdgeRAG.search(self, query, top_k=3, min_similarity=0.15)`:
   - Panggil `expanded_query = self.expand_query(query)` dan gunakan `expanded_query` saat menghitung vektor embedding serta membangun token pencarian FTS5 (beri bobot lebih tinggi jika token query asli cocok).
   - Jangan ubah skema tabel SQLite `documents` / `chunks` agar database `knowledge_rag.db` yang ada tetap 100% kompatibel.

### 3. Guardrail Khusus
- Jaga overhead RAM tetap **0 MB ekstra** (tetap pure Python + NumPy, jangan impor Torch/Transformers di sini).
- Tangani karakter tanda baca dalam kueri agar tidak memicu `sqlite3.OperationalError: fts5: syntax error`.

### 4. Perintah Verifikasi & Ekspektasi Lulus
```powershell
py -m py_compile rag_engine.py
py -c "from rag_engine import EdgeRAG; r = EdgeRAG(); q = r.expand_query('genset panas dan pendarahan'); print('Expanded:', q); assert 'overheating' in q and 'torniket' in q"
```
Ekspektasi output:
Query terekspansi memuat sinonim teknis & medis tanpa error FTS5.

### 5. Prompt Siap Pakai untuk Gemini 3.8 Flash (Medium)
> **Salin-tempel prompt ini:**  
> `Baca PLAN_EKSEKUSI_FLASH.md bagian SPRINT 2. Edit rag_engine.py untuk menambahkan DOMAIN_SYNONYMS dan expand_query() pada EdgeRAG.search(). Setelah selesai, jalankan perintah verifikasi Sprint 2 tanpa melakukan git push.`

---

## 🧪 SPRINT 3: Parametric Combinatorial Dataset Generator & Native Qwen2.5 `<tool_call>` (`PM-01`, `PM-07`)

### 1. Target File
- **Tulis ulang terstruktur:** `training/dataset_generator.py`
- **Output file baru/diperbarui:**
  - `training/lensetek_edge_loop_3000.jsonl` (3.000 baris latih unik)
  - `training/lensetek_eval_heldout_300.jsonl` (300 baris uji *held-out* terpisah yang tidak pernah muncul di data latih)

### 2. Spesifikasi Kode Eksak
1. **Hilangkan Total Masalah 17 Template Statis (`PM-01`):**
   - Buat pool parameter terpisah untuk **Train Set (`seed=42`)** dan **Held-Out Eval Set (`seed=999`)** dengan ID aset/dokumen/obat yang **disjoint (tidak tumpang tindih)**:
     - Contoh Train Assets: `GEN-01`..`GEN-20`, `BOILER-01`..`BOILER-12`, `EXCA-01`..`EXCA-15`, Modbus Register `40001`–`40500`.
     - Contoh Eval Assets: `GEN-91`..`GEN-99`, `BOILER-91`..`BOILER-99`, `EXCA-91`..`EXCA-99`, Modbus Register `40801`–`40999`.
   - Buat minimal **6 generator parametrik** (1 fungsi per kluster dalam 6 Curriculum Clusters) dengan **porsi eksak**:
     - `C1_DETERMINISTIC_TOOL_CALLING`: **500** sampel (train) / **50** (eval) — acak tool (`canbus_read`, `modbus_read_holding_registers`, `rag_search`, `system_telemetry`, `sqlite_query`), slave ID, register, timeout, suhu/tekanan/voltase float dinamis, dan variasi kalimat instruksi pengguna (minimal 8 variasi phrasing per jenis tugas).
     - `C2_MULTI_TURN_ERROR_RECOVERY`: **1.000** sampel (train) / **100** (eval) — kegagalan terencana: (a) `rag_search` 0-hit → reformulasi sinonim, (b) `serial_read` `DEVICE_NOT_FOUND` → cek `system_telemetry` → retry port aktif, (c) `sqlite_query` syntax/table error → cek skema/perbaiki kutip → sukses, (d) `modbus_read` timeout → turunkan baudrate/cek node → sukses. Sertakan pula pengamanan Read-Only bila user meminta `modbus_write`/`gpio_write` tanpa token HITL.
     - `C3_CALIBRATED_ABSTENTION`: **500** sampel (train) / **50** (eval) — skenario obat/dosis klinik, torsi mesin seri tak terdaftar, nama personel shift tidak ada, spesifikasi bahan kimia tak terindeks → `rag_search` mengembalikan 0 hits atau dokumen seri berbeda → model WAJIB menolak menebak (*Calibrated Abstention*) dengan menyitir keterbatasan dokumen lokal.
     - `C4_TUNABLE_EFFORT_LOOPS`: **400** sampel (train) / **40** (eval) — perimbangan 50:50 antara:
       - `[EFFORT:LOW]` (langsung jawab/eksekusi tool tanpa `<think>`, respon final ≤ 25 kata).
       - `[EFFORT:HIGH]` (wajib membuka blok `<think>...</think>` berisi kalkulasi matematis step-by-step sepanjang ~60–180 kata sebelum kesimpulan akhir: efisiensi uap-bahan bakar boiler, perhitungan arus baterai/solar MPPT, konversi unit tekanan, dll.).
     - `C5_OFFLINE_SURVIVAL_ARK`: **350** sampel (train) / **35** (eval) — kalkulasi dinamis acak: (a) Triage START dengan variasi acak *respiratory rate*, perfusi kapiler, kesadaran, & lokasi pendarahan → menghasilkan tag warna akurat (`MERAH`, `KUNING`, `HIJAU`, `HITAM`) + disclaimer medis, (b) Kalkulator antena dipole `142.5 / freq_mhz` dengan 30+ frekuensi acak VHF/UHF/Marine/ORARI/RAPI, (c) Kalkulasi rasio jatah air & kalori survival per `N` orang selama `D` hari, (d) Purifikasi air SODIS/kaporit terukur per liter.
     - `C6_REGIONAL_SOVEREIGNTY`: **250** sampel (train) / **25** (eval) — variasi tanya-jawab SOP industri PKS/tambang, campur kode Indonesia-Inggris teknisi lapangan, kepatuhan UU PDP No. 27/2022, & tata naskah dinas/pelabuhan.
2. **Format Tool Calling Native Qwen2.5 (`PM-07`):**
   - Ganti format lama `Action: {...}` menjadi tag resmi Qwen 2.5 Instruct:
     - Di pesan `assistant` saat memanggil alat:
       ```text
       <tool_call>
       {"name": "modbus_read_holding_registers", "arguments": {"slave_id": 4, "address": 40118, "count": 1}}
       </tool_call>
       ```
     - Di pesan hasil alat, gunakan format role `"tool"` dengan konten terbungkus `<tool_response>\n{...}\n</tool_response>` agar kompatibel dengan `apply_chat_template` Unsloth Qwen-2.5.
3. **Evaluasi Deduplikasi:** Pastikan tidak ada baris duplikat identik (`len(set(lines)) == 3000`).

### 3. Guardrail Khusus
- Jaga konsistensi angka matematis: angka hasil perhitungan di `<think>` dan jawaban final HARUS dihitung secara programatik di Python (misal `round(142.5 / freq, 3)`), bukan karangan teks statis!

### 4. Perintah Verifikasi & Ekspektasi Lulus
```powershell
py training/dataset_generator.py
py -c "import json; t=[open('training/lensetek_edge_loop_3000.jsonl',encoding='utf-8').readlines(), open('training/lensetek_eval_heldout_300.jsonl',encoding='utf-8').readlines()]; print('Train:', len(t[0]), 'Unique:', len(set(t[0])), '| Eval:', len(t[1]), 'Unique:', len(set(t[1]))); assert len(t[0])==3000 and len(set(t[0]))>=2990 and len(t[1])==300 and '<tool_call>' in ''.join(t[0])"
```
Ekspektasi output:
`Train: 3000 Unique: 3000 | Eval: 300 Unique: 300` (atau >= 2990 unik) dan mengandung `<tool_call>`.

### 5. Prompt Siap Pakai untuk Gemini 3.8 Flash (Medium)
> **Salin-tempel prompt ini:**  
> `Baca PLAN_EKSEKUSI_FLASH.md bagian SPRINT 3. Refaktor penuh training/dataset_generator.py menjadi Parametric Combinatorial Generator dengan format <tool_call> Qwen2.5, pisahkan Train (3000 baris) dan Held-Out Eval (300 baris) dengan asset ID disjoint. Jalankan generator dan verifikasi keunikannya tanpa git push.`

---

## ⚙️ SPRINT 4: GRPO Verifiable Rewards Script, Model-Agnostic SFT & Benchmark Evaluator (`PM-02`, `PM-04`, `PM-10`)

### 1. Target File
- **Edit:** `training/train_runpod.py`
- **Buat baru:** `training/train_grpo_rlvr.py`
- **Buat baru:** `training/evaluate_model.py`

### 2. Spesifikasi Kode Eksak
1. **Update `training/train_runpod.py`:**
   - Tambahkan `argparse` CLI dengan opsi `--base-model` (default `"Qwen/Qwen2.5-3B-Instruct"`), `--dataset` (default `"lensetek_edge_loop_3000.jsonl"`), `--max-steps` (default `500`), `--skip-push` (flag dry/local save only). Ini mengatasi ketergantungan pada satu model tunggal (`PM-10`, mendukung rebasing cepat ke `meta-llama/Llama-3.2-3B-Instruct` / `google/gemma-2-2b-it` untuk kebutuhan pertahanan/NDAA).
   - Gunakan `train_on_responses_only` dari `unsloth.chat_templates` (dengan fallback aman jika versi Unsloth berbeda) agar *gradient loss* hanya dihitung pada respons asisten, bukan pada *system prompt*.
   - Sertakan opsi ekspor GGUF menggunakan `"q4_k_m"` dengan catatan dan parameter kompatibel imatrix.
2. **Buat `training/train_grpo_rlvr.py`:**
   - Skrip tahap lanjutan pasca-SFT menggunakan `trl.GRPOTrainer` / `GRPOConfig` pada Unsloth (bisa diimpor bersih dengan pengecekan modul dan dukungan `--dry-run` lokal agar bisa dites di CPU Windows tanpa GPU!).
   - Wajib mengimplementasikan **3 fungsi Verifiable Reward nyata** dalam Python:
     1. `reward_tool_json_schema(completions, **kwargs)` → cek blok `<tool_call>(.*?)</tool_call>`, parse dengan `json.loads()`, periksa key `"name"` dan `"arguments"` (`dict`). Valid = `+1.0`, JSON cacat = `-1.5`.
     2. `reward_calibrated_abstention(completions, prompts, **kwargs)` → jika prompt mengandung konteks RAG kosong (`"0_hits_found"` atau `"tidak ditemukan"`), cek apakah jawaban mengakui ketiadaan informasi (`"tidak ditemukan"`, `"tidak tercantum"`, `"not found"`, `"abstaining"`) → `+0.8`; jika malah menjawab angka dosis/torsi/personel karangan → penalti `-2.0`.
     3. `reward_adaptive_effort(completions, prompts, **kwargs)` → jika prompt bertag `[EFFORT:LOW]`, beri `+0.5` bila tidak ada `<think>` dan jumlah kata/token estimasi `<= 35`, atau `-0.8` jika bertele-tele. Jika bertag `[EFFORT:HIGH]`, beri `+0.5` bila mengandung `<think>...</think>` sepanjang 40–250 kata.
   - Tambahkan mode `--test-rewards` yang menguji 3 fungsi reward tersebut secara deterministik di komputer lokal tanpa butuh GPU!
3. **Buat `training/evaluate_model.py`:**
   - Mengevaluasi dataset uji `training/lensetek_eval_heldout_300.jsonl` terhadap server lokal OpenAI-compatible (`http://127.0.0.1:3000/v1`) atau model GGUF via HTTP.
   - Menghasilkan file laporan `training/eval_scorecard.json` dengan 3 metrik investor:
     1. `tool_json_validity_pct` & `task_completion_pct`
     2. `closed_domain_hallucination_pct` (mengukur ketahanan abstention pada sampel C3)
     3. `effort_compliance_pct` & `avg_ttft_ms`
   - Mendukung flag `--dry-run` untuk memvalidasi kebenaran skema parsing & logika penilaian langsung di atas dataset `lensetek_eval_heldout_300.jsonl` tanpa harus menyalakan server GPU/GGUF.

### 3. Perintah Verifikasi & Ekspektasi Lulus
```powershell
py -m py_compile training/train_runpod.py training/train_grpo_rlvr.py training/evaluate_model.py
py training/train_grpo_rlvr.py --test-rewards
py training/evaluate_model.py --dry-run
```
Ekspektasi output:
Ketiga skrip terkompilasi bersih; `--test-rewards` menampilkan skor reward `+1.0`, `+0.8`, `-2.0`, `+0.5` sesuai uji unit; `--dry-run` memproses 300 sampel held-out dan mencetak scorecard 100% lulus pada *ground truth*.

### 4. Prompt Siap Pakai untuk Gemini 3.8 Flash (Medium)
> **Salin-tempel prompt ini:**  
> `Baca PLAN_EKSEKUSI_FLASH.md bagian SPRINT 4. Perbarui training/train_runpod.py (support --base-model & train_on_responses_only), serta buat training/train_grpo_rlvr.py dan training/evaluate_model.py lengkap dengan mode --test-rewards dan --dry-run lokal. Jalankan seluruh verifikasi Sprint 4 tanpa git push.`

---

## 🛠️ SPRINT 5: Multi-Project Harness (`usecase/edge-ai-agent` & `usecase/survival-agent`) (`PM-08`, `PM-09`)

### 1. Target File
- **Proyek 1 (`usecase/edge-ai-agent/`):**
  - `package.json`, `tsconfig.json`, `models.json`, `.gitignore`
  - `src/context_compressor.ts`, `src/tools.ts`, `src/index.ts`, `run_agent.bat`
- **Proyek 2 (`usecase/survival-agent/` — Lensetek ARK):**
  - `package.json`, `tsconfig.json`, `models.json`, `.gitignore`
  - `src/survival_tools.ts`, `src/index.ts`, `run_survival.bat`

### 2. Spesifikasi Kode Eksak
1. **Dependencies Node.js/TypeScript Minimalis:**
   - Kedua `package.json` menggunakan TypeScript + `tsx` dan berkomunikasi ke OpenAI-compatible local server `http://127.0.0.1:3000/v1` (tidak perlu download bloatware berat; impor `@earendil-works/pi-coding-agent` secara opsional atau buat adapter harness kompatibel skema Pi SDK).
2. **`src/context_compressor.ts` (`PM-08` — Anti Context-Overflow 4K):**
   - Fungsi `compressEpisodicHistory(messages, maxRecentToolTurns = 3, maxChunkChars = 1100)`:
     - Mempertahankan pesan `system` dan `user` terakhir secara utuh.
     - Meringkas hasil observasi `tool` yang lebih tua dari `maxRecentToolTurns` menjadi ringkasan 1 baris `< 45 token` (`[DIGEST tool=rag_search status=ok summary=...]`).
     - Memotong injeksi teks RAG mentah melebihi `maxChunkChars` (~300 token).
3. **Tools Proyek 1 (`usecase/edge-ai-agent/src/tools.ts`):**
   - `system_telemetry` (membaca os.freemem, os.totalmem, os.cpus, uptime secara real di Node.js).
   - `rag_search` (memanggil endpoint `POST http://127.0.0.1:3000/api/rag/search` dengan fallback aman jika server mati).
   - `modbus_can_sim_read` (pembacaan register simulasi Read-Only aman).
   - `actuate_write_guarded` (wajib meminta argumen `hitl_token`; selalu memblokir bila kosong sesuai `PM-06`).
4. **Tools Proyek 2 (`usecase/survival-agent/src/survival_tools.ts`):**
   - `medical_triage_start(rr, capillary_refill_sec, obeys_commands, bleeding_arterial)` → algoritma deterministik START (`MERAH` / `KUNING` / `HIJAU` / `HITAM`) + disclaimer non-medis.
   - `wiring_schematic(system_volts, panel_watts, battery_ah)` → generator diagram ASCII aki 12V/24V + MPPT + fuse rating.
   - `water_purification_calc(liters, turbidity)` → takaran lapisan filter 4 tahap, waktu rebus/SODIS, dan dosis kaporit (Ca(ClO)2) yang aman.
   - `ration_calculator(people, days, activity_level)` → estimasi liter air minum & kkal minimum per orang.
   - `radio_comms_antenna(freq_mhz)` → panjang dipole penuh `142.5 / freq_mhz` meter & per sayap + tabel frekuensi darurat (VHF Marine Ch 16 `156.800 MHz`, RAPI/ORARI, SOS Morse).
   - Antarmuka terminal HUD warna hijau retro (`\x1b[32m`) + argumen `--self-test` untuk memverifikasi semua 5 tool tanpa harus mengetik interaktif.

### 3. Perintah Verifikasi & Ekspektasi Lulus
```powershell
cd usecase\edge-ai-agent; npm install; npx tsc --noEmit; npx tsx src/index.ts --self-test
cd ..\survival-agent; npm install; npx tsc --noEmit; npx tsx src/index.ts --self-test
```
*(Jika koneksi npm offline atau gagal install, verifikasi minimal JSON valid + unit test langsung bila `node`/`tsx` sudah tersedia globally).*

### 4. Prompt Siap Pakai untuk Gemini 3.8 Flash (Medium)
> **Salin-tempel prompt ini:**  
> `Baca PLAN_EKSEKUSI_FLASH.md bagian SPRINT 5. Bangun multi-project harness di usecase/edge-ai-agent/ dan usecase/survival-agent/ lengkap dengan context_compressor.ts dan mode --self-test. Uji kompilasi dan --self-test setelah selesai tanpa git push.`

---

## 📄 SPRINT 6: Model Card Honest Framing & Open-Core (COSS) Licensing Table (`PM-02`, `PM-07`)

### 1. Target File
- **Edit:** `model_card/README.md`
- **Edit:** `model_card/README_base.md`
- **Edit:** `README.md`

### 2. Spesifikasi Kode Eksak
1. Di `model_card/README.md` dan `model_card/README_base.md` (seluruh bahasa EN, ID, ZH):
   - Ubah frasa teknis agar akurat 100% saat *Due Diligence* VC: ganti klaim seolah-olah bobot internal diubah menjadi recurrent loop dengan istilah akurat: **"System-2 Agentic Compute Loop & Adaptive Token-Budgeted Reasoning (inspired by recurrent/looped thinking concepts, built on stock GGUF-compatible `Qwen2ForCausalLM` weights + GRPO RLVR)"**.
   - Tandai metrik target (`>95% Task Completion`, `<1% Hallucination`) secara jujur sebagai **`Target Benchmark (Pending Full RunPod Eval Scorecard)`** sebelum file GGUF aktual diunggah.
2. Di `README.md`:
   - Tambahkan bagian **Licensing & Open-Core Architecture (Commercial Open-Source / COSS)** yang memisahkan dengan tegas:
     - **Community Open-Weights & Core Studio (Apache-2.0 / MIT):** Bobot SLM 3B GGUF/Safetensors, Studio Web UI, RAG SQLite dasar, Pi Harness dasar.
     - **Lensetek Enterprise & Turnkey Hardware (Commercial License):** Certified OT/Field Connectors (Modbus RTU/TCP, CAN J1939, OPC-UA, HL7/DICOM), SQLCipher at-rest encryption, Multi-Node Fleet Dashboard, Custom Factory SOP RL Flywheel, dan **Lensetek ARK Rugged Hardware Box**.
   - Sertakan arsitektur keselamatan *Read-Only Default & HITL Approval Token* pada bagian Security & Compliance.

### 3. Guardrail Khusus
- Jangan menghapus navigasi trilingual (EN/ID/ZH) yang sudah ada pada file-file README tersebut.
- Jangan push ke Hugging Face secara otomatis tanpa perintah eksplisit pengguna setelah review.

### 4. Perintah Verifikasi & Ekspektasi Lulus
```powershell
py -c "
for f in ['model_card/README.md', 'model_card/README_base.md', 'README.md']:
    txt = open(f, encoding='utf-8').read()
    assert len(txt) > 1000
r = open('README.md', encoding='utf-8').read()
assert 'Open-Core' in r or 'Commercial License' in r
m = open('model_card/README.md', encoding='utf-8').read()
assert 'System-2 Agentic Compute Loop' in m
print('DOC_AUDIT_PASSED')
"
```

### 5. Prompt Siap Pakai untuk Gemini 3.8 Flash (Medium)
> **Salin-tempel prompt ini:**  
> `Baca PLAN_EKSEKUSI_FLASH.md bagian SPRINT 6. Perbarui model_card/README.md, model_card/README_base.md, dan README.md dengan framing teknis jujur dan tabel pemisahan Open-Core (COSS). Jalankan verifikasi Sprint 6 dan laporkan perubahannya tanpa melakukan git push atau upload HF.`

---

## ✅ Checklist Akhir Setelah Sprint 1–6 Selesai
1. Jalankan `py -m py_compile app.py safety_guard.py rag_engine.py download_models.py training/*.py`.
2. Pastikan `.gitignore` tetap mengecualikan `.env*`, `*.gguf`, `*.db`, dan tidak ada kredensial di kode.
3. Siapkan instruksi RunPod yang kini memiliki **2 tahap berbiaya ~$1.50 total**:
   - Tahap A: `python train_runpod.py` (SFT pada 3.000 data parametrik dengan `train_on_responses_only`).
   - Tahap B: `python train_grpo_rlvr.py` (RL Verifiable Rewards untuk menekan halusinasi & mengunci `[EFFORT:LOW/HIGH]`).
   - Tahap C: `python evaluate_model.py` (Menghasilkan angka valid `eval_scorecard.json` untuk pitch deck investor).
