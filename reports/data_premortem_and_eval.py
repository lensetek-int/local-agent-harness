"""
Data evaluasi 8 dimensi dan 10 Skenario Pre-Mortem + Solusi Arsitektural
berdasarkan audit langsung terhadap plan_edge_ai_agent.md dan codebase lokal
(app.py, rag_engine.py, training/dataset_generator.py, training/train_runpod.py).
"""

EVALUATION_8_DIMENSIONS = [
    {
        "dimensi": "1. Arsitektur Edge Runtime & Anggaran Memori (RAM <= 4 GB)",
        "skor_sekarang": 4.0,
        "skor_target_pasca_fix": 4.8,
        "status": "KUAT (Perlu Koreksi Flag Runtime)",
        "audit_fakta_codebase": (
            "Model 3B Q4_K_M (~2.05 GB) + app.py (~30 MB) + SQLite RAG (0 MB idle) terbukti efisien. "
            "NAMUN inspeksi app.py baris 252-258 menunjukkan llama-server.exe diluncurkan HANYA dengan '-c 4096' "
            "tanpa flag '-ctk q4_0 -ctv q4_0' (KV cache masih FP16 ~580 MB, bukan ~140 MB). "
            "Selain itu baris 19-21 hardcode '.exe' untuk Windows IoT yang OS-nya sendiri memakan ~1.8 GB RAM."
        ),
        "rekomendasi_perbaikan": (
            "Tambahkan flag '-ctk q4_0 -ctv q4_0 -fa' pada cmd app.py, buat deteksi path binary lintas-OS (Linux/ARM64/Windows), "
            "dan prioritaskan target OS Headless Linux (Debian/Alpine ~350 MB RAM) untuk perangkat 4 GB."
        ),
    },
    {
        "dimensi": "2. Metodologi Training & Kualitas Dataset (training/dataset_generator.py)",
        "skor_sekarang": 1.8,
        "skor_target_pasca_fix": 4.6,
        "status": "KRITIS (Wajib Diperbaiki Sebelum RunPod)",
        "audit_fakta_codebase": (
            "Inspeksi training/dataset_generator.py menemukan hanya ada 17 template statis "
            "(C1=4, C2=3, C3=3, C4=2, C5=3, C6=2) yang diduplikasi secara acak hingga 3.000 baris. "
            "Setiap sampel diulang ~176 kali. Jika dilatih 350 steps di RunPod, model akan menghafal angka statis "
            "(mis. '98.4 C', 'GEN-04', '14 Oktober 2026') dan gagal total pada prompt baru."
        ),
        "rekomendasi_perbaikan": (
            "Ubah generator menjadi Parametric Combinatorial Synthesis (ratusan asset ID, register Modbus acak, "
            "nilai sensor dinamis, variasi bahasa/parafrase) + pipeline SFT ('train_on_responses_only') dilanjutkan GRPO RLVR."
        ),
    },
    {
        "dimensi": "3. Keaslian Arsitektur & Klaim 'Looped Transformer' (train_runpod.py)",
        "skor_sekarang": 2.4,
        "skor_target_pasca_fix": 4.5,
        "status": "RISIKO KREDIBILITAS DEEP-TECH",
        "audit_fakta_codebase": (
            "Plan & Model Card menyebut inspirasi Thinking Machines Lab 'Inkling' (weight-tied recurrent middle layers), "
            "namun train_runpod.py melatih bobot Qwen/Qwen2.5-3B-Instruct standar dengan SFTTrainer biasa dan "
            "belum menyertakan script GRPO (+1.0 / +0.8 / -2.0 reward) sebagaimana diklaim."
        ),
        "rekomendasi_perbaikan": (
            "Ubah terminologi teknis agar jujur 100%: 'System-2 Agentic Compute Loop & Token-Budgeted Reasoning' "
            "yang kompatibel penuh dengan GGUF llama.cpp standar, dan implementasikan training/train_grpo_rlvr.py nyata."
        ),
    },
    {
        "dimensi": "4. Mesin RAG Lokal & Akurasi Pengambilan Dokumen (rag_engine.py)",
        "skor_sekarang": 3.4,
        "skor_target_pasca_fix": 4.5,
        "status": "BAIK (Perlu Ekspansi Sinonim/ONNX Opsional)",
        "audit_fakta_codebase": (
            "EdgeRAG di rag_engine.py brilian dalam efisiensi (SQLite3 + FTS5 + NumPy MD5/SHA256 trigram projection 256-dim, "
            "<2 ms latency, 0 MB download). Namun hashing trigram bukan semantic embedding sejati—kata sinonim tanpa "
            "kemiripan huruf (mis. 'tekanan darah tinggi' vs 'hipertensi') memiliki cosine similarity mendekati nol."
        ),
        "rekomendasi_perbaikan": (
            "Tambahkan kamus ekspansi sinonim domain industri/medis Indonesia di rag_engine.py, optimalkan agentic query-rewriting loop, "
            "dan sediakan opsi pluggable micro-embedder ONNX INT8 (~22 MB RAM) untuk klien dengan kebutuhan semantik tinggi."
        ),
    },
    {
        "dimensi": "5. Keandalan Tool-Calling 4-Bit & Keselamatan Eksekusi",
        "skor_sekarang": 2.8,
        "skor_target_pasca_fix": 4.7,
        "status": "PERLU INTERLOCK KESELAMATAN",
        "audit_fakta_codebase": (
            "Dataset saat ini memakai format 'Action: {...}' dengan role 'tool', padahal Qwen2.5-Instruct menggunakan "
            "tag native '<tool_call>' dan '<tool_response>'. Selain itu belum ada GBNF Grammar constraint dan "
            "Human-in-the-Loop (HITL) safety gate untuk tools fisik (gpio_write, modbus_write) dan medis (triage)."
        ),
        "rekomendasi_perbaikan": (
            "Selaraskan template dataset dengan tag <tool_call> Qwen2.5, aktifkan GBNF JSON Schema decoding di llama-server, "
            "terapkan Read-Only Default + cryptographic HITL confirmation token untuk aktuasi fisik."
        ),
    },
    {
        "dimensi": "6. Strategi Multi-Proyek & Segmentasi Pasar (Industrial + ARK)",
        "skor_sekarang": 4.2,
        "skor_target_pasca_fix": 4.7,
        "status": "SANGAT MENARIK (Perlu Fokus Bertahap)",
        "audit_fakta_codebase": (
            "Visi 6 sektor (Mining CAN-bus, PKS Boiler, Klinik 3T UU PDP, Manufaktur, Maritim, dan Lensetek ARK Survival OS) "
            "memiliki pain-point nyata tanpa kompetitor cloud. Namun bagi investor B2B, menjalankan 6 vertikal sekaligus "
            "berisiko memecah fokus tim R&D."
        ),
        "rekomendasi_perbaikan": (
            "Terapkan Dual-Engine GTM terfokus: (1) Jalur cepat cashflow via Lensetek ARK Box & DevKit (Crowdfunding/Komunitas), "
            "(2) Jalur B2B enterprise fokus ke 2 pantai utama terlebih dahulu: Agro-Mining (PKS/Alat Berat) & Klinik 3T Air-Gapped."
        ),
    },
    {
        "dimensi": "7. Model Bisnis Open-Source & Daya Tangkap Nilai (Monetization)",
        "skor_sekarang": 3.0,
        "skor_target_pasca_fix": 4.6,
        "status": "RENTAN FREE-RIDER",
        "audit_fakta_codebase": (
            "Model GGUF & Safetensors dirilis berlisensi Apache-2.0 dan aplikasi MIT di Hugging Face. Tanpa batas Open-Core "
            "yang tegas, perusahaan sistem integrator bisa mengkloning seluruh stack secara gratis."
        ),
        "rekomendasi_perbaikan": (
            "Terapkan strategi Commercial Open-Source (COSS): Model 3B & Studio dasar gratis sebagai baji adopsi (community wedge), "
            "monetisasi melalui Enterprise Field Connectors (OPC-UA/CAN/DICOM bersertifikat), Custom SOP RL Flywheel, dan Appliance Hardware."
        ),
    },
    {
        "dimensi": "8. Kesiapan Ekosistem Hugging Face & Eksekusi Produk Awal",
        "skor_sekarang": 4.4,
        "skor_target_pasca_fix": 4.8,
        "status": "EKSEKUSI CEPAT & SOLID",
        "audit_fakta_codebase": (
            "Tiga repositori HF sudah tertata sesuai standar industri: lensetek-edge-loop-3b (Safetensors 16-bit), "
            "lensetek-edge-loop-3b-GGUF (Edge 4-bit), dan lensetek-edge-ai-agent (Code Hub). Server Python, SQLite RAG, "
            "Whisper/Piper Voice, dan UI Mobile-First sudah berfungsi."
        ),
        "rekomendasi_perbaikan": (
            "Lengkapi repo model dengan hasil benchmark terukur pasca-training (TruthfulQA-Indo, BFCL-Edge Tool Accuracy, "
            "Hallucination Rate Matrix) sebelum melakukan outreach ke VC dan CVC."
        ),
    },
]

PRE_MORTEM_SCENARIOS = [
    {
        "id": "PM-01",
        "judul": "Bencana Overfitting Dataset (17 Template Statis Diduplikasi 3.000x)",
        "kategori": "Training & AI Engineering",
        "tingkat_risiko": "CRITICAL",
        "severity": 5,
        "probability": 5,
        "rpn": 25,
        "diagnosis_akar_masalah": (
            "File training/dataset_generator.py hanya memiliki 17 skenario hardcoded (C1=4, C2=3, C3=3, C4=2, C5=3, C6=2) "
            "yang disampling berulang via random.choice() menjadi 3.000 baris (~176 salinan identik per skenario). "
            "Dengan train_runpod.py berjalan 350 steps x batch_size 8 (= 2.800 contoh), model mengalami memorisasi ekstrem "
            "(overfitting): selalu menebak '98.4 C', 'GEN-04', atau 'Register 40012' bahkan ketika ditanya mesin berbeda, "
            "dan mengalami catastrophic forgetting pada kemampuan chat umum Qwen2.5."
        ),
        "dampak_jika_terjadi": (
            "Dana RunPod terbuang, model gagal total saat live demo di hadapan angel/VC ('model hafalan'), "
            "dan merusak reputasi awal repositori Hugging Face lensetek-edge-loop-3b."
        ),
        "solusi_konkret": (
            "1. Refaktor dataset_generator.py menjadi Parametric Combinatorial Generator (mengacak 50+ tipe aset industri, "
            "1.000+ rentang register Modbus & CAN-bus PID, variasi angka sensor/suhu/tekanan, serta skenario kegagalan SQL/Serial/RAG dinamis).\n"
            "2. Suntikkan 30% data general instruction & coding grounding agar kemampuan dasar tidak terhapus.\n"
            "3. Aktifkan 'train_on_responses_only' pada Unsloth SFTTrainer dan siapkan 300 sampel held-out evaluation set yang terpisah."
        ),
    },
    {
        "id": "PM-02",
        "judul": "Klaim 'Looped Transformer (Inkling)' & GRPO Tidak Sinkron dengan Bobot Aktual",
        "kategori": "IP Credibility & Due Diligence",
        "tingkat_risiko": "CRITICAL",
        "severity": 5,
        "probability": 4,
        "rpn": 20,
        "diagnosis_akar_masalah": (
            "Model Card dan pitch menonjolkan konsep Looped Transformer ala Thinking Machines Lab (Inkling) serta skema reward GRPO (+1.0/+0.8/-2.0). "
            "Namun train_runpod.py saat ini hanya menjalankan SFTTrainer standar pada arsitektur Qwen2ForCausalLM (bukan recurrent layer weights) "
            "dan belum memiliki kode GRPOTrainer. Investor Deep-Tech & AI Researcher yang membaca config.json dan train_runpod.py akan menganggap klaim berlebihan (AI-washing)."
        ),
        "dampak_jika_terjadi": (
            "Ditolak seketika saat Technical Due Diligence (DD) oleh Global AI VC (OSS Capital, Air Street, Khosla) dan Angel Ex-CTO."
        ),
        "solusi_konkret": (
            "1. Ganti framing arsitektural menjadi 100% akurat: 'System-2 Agentic Compute Loop & Adaptive Token-Budgeted Reasoning' "
            "(di mana loop dilakukan secara terstruktur di level generasi inferensi [EFFORT:LOW/HIGH] sehingga tetap kompatibel 100% dengan llama.cpp standar).\n"
            "2. Tambahkan skrip training/train_grpo_rlvr.py menggunakan Unsloth GRPOTrainer dengan fungsi reward Python deterministik untuk validitas JSON, penalti panjang token pada mode LOW, dan reward +0.8/-2.0 anti-halusinasi."
        ),
    },
    {
        "id": "PM-03",
        "judul": "Kegagalan Recall RAG pada Dokumen Bahasa Indonesia (Lexical Hash vs Semantic Vector)",
        "kategori": "RAG & Akurasi Pengetahuan",
        "tingkat_risiko": "HIGH",
        "severity": 4,
        "probability": 4,
        "rpn": 16,
        "diagnosis_akar_masalah": (
            "Fungsi EdgeRAG.compute_embedding() di rag_engine.py (baris 74-100) menggunakan hashing MD5 kata & SHA256 character trigram berdimensi 256. "
            "Meskipun sangat cepat (<2 ms) dan 0 MB RAM, metode ini tidak memahami sinonim semantik (misal kueri 'obat panas anak' tidak akan cocok dengan dokumen bertuliskan 'antipiretik pediatrik' jika FTS5 tidak menemukan kecocokan leksikal)."
        ),
        "dampak_jika_terjadi": (
            "Model terlalu sering memicu Calibrated Abstention ('Informasi tidak ditemukan') padahal jawabannya ada di dokumen dengan istilah berbeda, menurunkan Task Completion Rate di klinik dan pabrik."
        ),
        "solusi_konkret": (
            "1. Implementasikan Kamus Ekspansi Sinonim Domain Industri & Medis Indonesia-Inggris di rag_engine.py sebelum query FTS5/trigram.\n"
            "2. Latih model pada Cluster 2 agar saat rag_search mengembalikan 0 hits, model wajib melakukan Query Reformulation memakai 2-3 sinonim istilah teknis di langkah kedua.\n"
            "3. Tambahkan mode opsional ONNX INT8 micro-embedder (mis. all-MiniLM/bge-micro ~22 MB) untuk perangkat yang punya sisa RAM."
        ),
    },
    {
        "id": "PM-04",
        "judul": "Degradasi Format Tool-Call Saat Model 3B Dikuantisasi ke GGUF 4-Bit & Mismatch ChatML",
        "kategori": "Inference & Kuantisasi",
        "tingkat_risiko": "HIGH",
        "severity": 4,
        "probability": 4,
        "rpn": 16,
        "diagnosis_akar_masalah": (
            "Pertama, dataset_generator.py memakai format teks bebas 'Action: {...}' alih-alih tag native Qwen2.5 '<tool_call>' dan '<tool_response>'. "
            "Kedua, pasca-kuantisasi 4-bit (Q4_K_M), model kecil 3B rentan kehilangan tanda kutip atau kurung kurawal pada JSON kompleks tanpa kendala tata bahasa."
        ),
        "dampak_jika_terjadi": (
            "Parser Node.js Pi SDK maupun engine agen mengalami crash saat JSON.parse(), menghentikan alur kerja otomasi di tengah jalan."
        ),
        "solusi_konkret": (
            "1. Migrasikan format dataset ke struktur <tool_call>...</tool_call> standar Qwen2.5.\n"
            "2. Gunakan GGUF Importance Matrix (imatrix) dengan kalibrasi teks domain tool-calling Indonesia saat mengonversi FP16 ke Q4_K_M.\n"
            "3. Aktifkan GBNF Grammar / parameter 'response_format' / 'tools' strict schema decoding di llama-server sehingga probabilitas sintaks JSON cacat menjadi 0%."
        ),
    },
    {
        "id": "PM-05",
        "judul": "Plafon RAM 4 GB Tembus di Windows IoT & Ketidaksesuaian Binary Flag (app.py)",
        "kategori": "Hardware & Edge Constraints",
        "tingkat_risiko": "HIGH",
        "severity": 4,
        "probability": 4,
        "rpn": 16,
        "diagnosis_akar_masalah": (
            "app.py baris 252-258 meluncurkan llama-server hanya dengan '-c 4096' tanpa flag '-ctk q4_0 -ctv q4_0' (sehingga KV cache memakan ~580 MB FP16, bukan 140 MB). "
            "Selain itu app.py baris 19-21 hardcode '.exe' untuk Windows, padahal Windows 10/11 sendiri memakan ~1.8-2.2 GB RAM. Jika ditambah Node.js Pi SDK (~200 MB), total RAM menjadi ~4.4 GB dan menyebabkan paging/swap lambat."
        ),
        "dampak_jika_terjadi": (
            "Klaim 'berjalan di edge computer RAM 4 GB' terpatahkan saat diuji di Mini PC Intel N100 4 GB berbasis Windows."
        ),
        "solusi_konkret": (
            "1. Tambahkan '-ctk q4_0 -ctv q4_0 -fa on' secara default di app.py saat meluncurkan llama-server.\n"
            "2. Buat resolusi binary lintas-platform (Linux/macOS/Windows) di app.py dan sertakan profil konfigurasi Headless Debian/Alpine Linux Edge (OS RAM ~350 MB -> Total sistem hanya ~2.85 GB).\n"
            "3. Sediakan mode ringan Python-only Agent Loop tanpa overhead process Node.js untuk perangkat ketat <= 4 GB."
        ),
    },
    {
        "id": "PM-06",
        "judul": "Risiko Liabilitas Kritis pada Aktuasi Mesin Fisik & Triage Medis Otonom",
        "kategori": "Regulasi, Safety & Compliance",
        "tingkat_risiko": "HIGH",
        "severity": 5,
        "probability": 3,
        "rpn": 15,
        "diagnosis_akar_masalah": (
            "Proyek 1 mencakup kendali relay/Modbus dan Proyek 2/Kesehatan mencakup triage medis darurat serta CDSS klinik 3T. "
            "Jika SLM 3B salah membaca nilai register atau keliru menyimpulkan gejala klinis lalu mengeksekusi aktuasi tanpa pengaman, dampak finansial atau nyawa berisiko menuntut tanggung jawab hukum pengembang."
        ),
        "dampak_jika_terjadi": (
            "CVC Industri (Pertambangan/Pabrik), CVC Rumah Sakit, dan Investor Institusional menolak menyetujui uji coba lapangan karena kekhawatiran kepatuhan K3, IEC 61508, dan Kemenkes."
        ),
        "solusi_konkret": (
            "1. Kunci arsitektur sistem pada Read-Only Telemetry by Default.\n"
            "2. Terapkan Mandatory Human-in-the-Loop (HITL) Confirmation Gate dengan token persetujuan kriptografis lokal sebelum tool berstatus WRITE/ACTUATE dieksekusi.\n"
            "3. Cantumkan disclaimer dan mode Audit Trail Log tak-terubah (append-only SQLite audit log) untuk setiap output CDSS/Survival (Alat Bantu Referensi, bukan diagnosis final)."
        ),
    },
    {
        "id": "PM-07",
        "judul": "Kebocoran Nilai Komersial (Free-Rider Trap) Akibat Lisensi Open-Source Terbuka Penuh",
        "kategori": "Business Model & Monetization",
        "tingkat_risiko": "MEDIUM-HIGH",
        "severity": 4,
        "probability": 4,
        "rpn": 16,
        "diagnosis_akar_masalah": (
            "Jika seluruh bobot GGUF (Apache-2.0) dan seluruh agent harness serta field tools (MIT) dirilis gratis tanpa pembeda enterprise, "
            "perusahaan konsultan IT atau pesaing bisa langsung menjual solusi Lensetek ke pabrik dan tambang tanpa membayar lisensi sepeser pun."
        ),
        "dampak_jika_terjadi": (
            "Adopsi unduhan di Hugging Face tinggi, tetapi pendapatan (ARR) tetap nol sehingga startup kesulitan menutup putaran Seed/Series A dari VC berbasis metrik finansial."
        ),
        "solusi_konkret": (
            "1. Adopsi strategi Dual-Track Open-Core (COSS): Model SLM 3B & Core Studio UI tetap Apache-2.0/MIT untuk dominasi ekosistem developer.\n"
            "2. Komersialisasikan komponen Enterprise (Commercial License / Proprietary Source-Available): Certified OT/Industrial Drivers (Modbus, CAN J1939, OPC-UA, HL7/DICOM), Dashboard Fleet Management Multi-Node, Automated On-Premise RL Flywheel, serta Unit Hardware Turnkey (Lensetek Edge Node / ARK Box)."
        ),
    },
    {
        "id": "PM-08",
        "judul": "Context Window Overflow pada Loop Error Recovery Multi-Langkah (> 4.096 Token)",
        "kategori": "Agent Harness Reliability",
        "tingkat_risiko": "MEDIUM-HIGH",
        "severity": 4,
        "probability": 3,
        "rpn": 12,
        "diagnosis_akar_masalah": (
            "Pada batas konteks edge 4.096 token (`-c 4096`), sistem prompt + definisi JSON 5 tools memakan ~900 token. "
            "Jika agen masuk ke 3-4 siklus error recovery berturut-turut ditambah hasil rag_search yang panjang, prompt membengkak melewati 4.096 token sehingga llama-server memotong instruksi awal (system prompt) secara diam-diam."
        ),
        "dampak_jika_terjadi": (
            "Agen kehilangan arah di tengah tugas panjang, mengabaikan aturan anti-halusinasi, dan melambat drastis karena re-evaluasi KV cache pada CPU."
        ),
        "solusi_konkret": (
            "1. Terapkan Episodic State Summarizer di Pi Agent Harness: ringkas observasi tool lama (>2 langkah lalu) menjadi catatan 40 token sebelum mengirim giliran berikutnya.\n"
            "2. Batasi ukuran injeksi chunk RAG maksimal 250-300 token per hasil dan batasi loop self-correction maksimal 3 percobaan sebelum eskalasi terstruktur ke operator manusia."
        ),
    },
    {
        "id": "PM-09",
        "judul": "Siklus Penjualan Enterprise B2B Tambang/Pabrik Terlalu Panjang (6-12 Bulan) Menguras Kas",
        "kategori": "Go-To-Market & Runway",
        "tingkat_risiko": "MEDIUM",
        "severity": 4,
        "probability": 3,
        "rpn": 12,
        "diagnosis_akar_masalah": (
            "Menargetkan korporasi besar (tambang, perkebunan kelapa sawit, pertahanan maritim, dinas kesehatan) membutuhkan proses procurement panjang, audit keamanan IT/OT, dan birokrasi berbulan-bulan. Startup awal sering kehabisan runway sebelum kontrak PO pertama cair."
        ),
        "dampak_jika_terjadi": (
            "Ketidakmampuan menunjukkan traksi pendapatan (MRR/ARR) dalam 6 bulan pertama pasca rilis produk."
        ),
        "solusi_konkret": (
            "1. Jalankan Dual-Velocity Revenue Strategy: Produk fisik/komunitas 'Lensetek ARK Off-Grid AI Box' ($299-$599) diluncurkan lewat Pre-Order/Crowdfunding & e-commerce teknis untuk menghasilkan cashflow awal dalam 30-60 hari.\n"
            "2. Tawarkan paket '30-Day Paid Air-Gapped PoC Box' senilai Rp 35 juta - Rp 75 juta untuk pabrik/klinik menengah dengan skema plug-and-play tanpa integrasi ERP yang rumit."
        ),
    },
    {
        "id": "PM-10",
        "judul": "Risiko Keusangan Cepat oleh Model Dasar Baru (Qwen 3 / Llama 4 / Gemma 3 Nano)",
        "kategori": "Platform & Foundation Model Risk",
        "tingkat_risiko": "MEDIUM",
        "severity": 3,
        "probability": 4,
        "rpn": 12,
        "diagnosis_akar_masalah": (
            "Ekosistem model kecil terbuka bergerak sangat cepat (siklus rilis 4-6 bulan). Jika keunggulan utama hanya bergantung pada bobot Qwen 2.5 3B hasil SFT sekali jalan, model dasar generasi berikutnya bisa melampaui performa baseline dalam hitungan bulan."
        ),
        "dampak_jika_terjadi": (
            "Investor menilai produk sebagai komoditas tipis di atas model raksasa AI global tanpa parit pertahanan jangka panjang."
        ),
        "solusi_konkret": (
            "1. Geser narasi dan aset IP utama dari 'satu checkpoint model' menjadi 'Proprietary Edge Trajectory Dataset, Verifiable Benchmark Suite, & Automated Field RL Flywheel' yang bersifat model-agnostic.\n"
            "2. Pastikan pipeline RunPod & GRPO kita modular sehingga dapat melakukan rebasing otomatis ke model arsitektur masa depan dalam < 3 jam dengan biaya < $2."
        ),
    },
]
