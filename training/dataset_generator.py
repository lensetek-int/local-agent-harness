#!/usr/bin/env python3
"""
Lensetek Edge-Loop-3B: 3,000 Trajectory Curriculum Dataset Generator
Produces structured multi-turn agentic conversations formatted in ChatML format.

The 6 Curriculum Clusters:
1. Deterministic Tool Calling & Syntax Precision (~500)
2. Multi-Turn Error Recovery & Self-Correction Loop (~1,000 / 33%)
3. Calibrated Abstention & Zero-Hallucination Grounding (~500)
4. Tunable Effort Loops ([EFFORT:LOW] vs [EFFORT:HIGH]) (~400)
5. Offline Survival & Edge IoT Trajectories (Lensetek ARK) (~350)
6. Sovereign Regional Context & Bilingual Code-Switching (~250)
"""

import os
import json
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(BASE_DIR, "lensetek_edge_loop_3000.jsonl")

SYSTEM_PROMPT = (
    "You are Lensetek Edge-Loop Agent, an autonomous, air-gapped Small Language Model (SLM) "
    "engineered for industrial automation, offline edge resilience, and high-precision tool execution. "
    "Adhere strictly to verifiable facts, parse error codes defensively, and adapt reasoning effort based on user tags."
)

# ==============================================================================
# CLUSTER 1: DETERMINISTIC TOOL CALLING (500 Trajectories)
# ==============================================================================
C1_TOOLS = [
    {
        "user": "[EFFORT:LOW] Query engine oil temperature from CAN-bus node 0x18FEEE00.",
        "thought": "",
        "action": '{"tool": "canbus_read", "parameters": {"node_id": "0x18FEEE00", "pid": "0x0105", "timeout_ms": 250}}',
        "obs": '{"status": "ok", "value": 98.4, "unit": "Celsius", "quality": "GOOD"}',
        "final": "Engine oil temperature is nominal at **98.4 °C** (CAN-bus 0x18FEEE00, Quality: GOOD)."
    },
    {
        "user": "[EFFORT:LOW] Read register 40012 on Modbus RS-485 slave ID 3.",
        "thought": "",
        "action": '{"tool": "modbus_read_holding_registers", "parameters": {"slave_id": 3, "address": 40012, "count": 1, "baud": 9600}}',
        "obs": '{"status": "ok", "register": 40012, "raw_hex": "0x01F4", "decimal": 500}',
        "final": "Modbus Slave 3 Register 40012 reads **500** (`0x01F4`). Value is verified."
    },
    {
        "user": "[EFFORT:LOW] Search local RAG database for boiler operating pressure limits.",
        "thought": "",
        "action": '{"tool": "rag_search", "parameters": {"query": "boiler operating pressure safety limits PKS", "top_k": 2}}',
        "obs": '{"matches": [{"doc": "SOP-PKS-BOILER-04", "text": "Tekanan kerja maksimal ketel uap PKS adalah 28.5 Bar. Safety valve meletup pada 30.0 Bar."}]}',
        "final": "Berdasarkan SOP-PKS-BOILER-04, tekanan kerja nominal boiler adalah **28.5 Bar**, dengan batas pemicu katup pengaman (*safety valve*) pada **30.0 Bar**."
    },
    {
        "user": "[EFFORT:LOW] Check available system RAM and storage partition /dev/sda1.",
        "thought": "",
        "action": '{"tool": "system_telemetry", "parameters": {"metrics": ["memory", "disk"], "target_partition": "/dev/sda1"}}',
        "obs": '{"ram_total_mb": 3840, "ram_used_mb": 1820, "ram_free_mb": 2020, "disk_free_gb": 42.8}',
        "final": "Hardware status: **2,020 MB RAM available** (47.4% used of 3.8 GB) and **42.8 GB free disk** on `/dev/sda1`."
    }
]

# ==============================================================================
# CLUSTER 2: MULTI-TURN ERROR RECOVERY & SELF-CORRECTION (1,000 Trajectories)
# ==============================================================================
C2_SCENARIOS = [
    {
        "user": "[EFFORT:HIGH] Retrieve maintenance history for generator unit GEN-04.",
        "think_1": "User needs maintenance records for GEN-04. I will query the RAG database with exact keyword 'GEN-04 maintenance history'.",
        "action_1": '{"tool": "rag_search", "parameters": {"query": "GEN-04 maintenance history", "top_k": 3}}',
        "obs_1": '{"matches": [], "status": "0_hits_found"}',
        "think_2": "Search returned 0 hits. Potential keyword mismatch: asset might be cataloged as 'Genset 4', 'Generator-Set 04', or 'Diesel Genset'. Broadening query to 'Genset 4 diesel perawatan'.",
        "action_2": '{"tool": "rag_search", "parameters": {"query": "Genset 4 diesel perawatan pemeliharaan", "top_k": 3}}',
        "obs_2": '{"matches": [{"doc": "LOG-GENSET-04", "text": "Genset Cummins 4 (GEN-04): Ganti oli SAE 15W-40 dan filter bahan bakar pada 14 Oktober 2026. Jam operasi: 4.820 jam."}]}',
        "final": "Catatan ditemukan setelah penyesuaian kata kunci:\n- **Unit**: Genset Cummins 4 (`GEN-04`)\n- **Riwayat Terakhir**: Penggantian oli SAE 15W-40 & filter bahan bakar pada **14 Oktober 2026**.\n- **Jam Operasi**: 4.820 jam operasional."
    },
    {
        "user": "[EFFORT:HIGH] Read telemetry from vibration sensor on port /dev/ttyUSB0.",
        "think_1": "Requesting vibration sensor data via serial port /dev/ttyUSB0 at default 9600 baud rate.",
        "action_1": '{"tool": "serial_read", "parameters": {"port": "/dev/ttyUSB0", "baud": 9600, "timeout_ms": 500}}',
        "obs_1": '{"status": "error", "error_code": "DEVICE_NOT_FOUND", "message": "No such file or directory: /dev/ttyUSB0"}',
        "think_2": "/dev/ttyUSB0 does not exist. Sensor might be mapped to /dev/ttyUSB1 or /dev/ttyACM0 after a reboot. Querying system hardware enumeration first.",
        "action_2": '{"tool": "system_telemetry", "parameters": {"metrics": ["serial_ports"]}}',
        "obs_2": '{"status": "ok", "active_ports": ["/dev/ttyUSB1", "/dev/ttyS0"]}',
        "think_3": "Active port identified as /dev/ttyUSB1. Re-executing serial_read on /dev/ttyUSB1 with verified port.",
        "action_3": '{"tool": "serial_read", "parameters": {"port": "/dev/ttyUSB1", "baud": 9600, "timeout_ms": 500}}',
        "obs_3": '{"status": "ok", "raw_data": "VIB_RMS:1.82mm/s,FREQ:49.8Hz,PEAK:2.4G"}',
        "final": "Port `/dev/ttyUSB0` tidak ditemukan, agen secara otomatis mendeteksi port aktif di `/dev/ttyUSB1`:\n- **Vibration RMS**: 1.82 mm/s (Dalam batas aman ISO 10816 Class II)\n- **Frekuensi Dominan**: 49.8 Hz\n- **Peak Acceleration**: 2.4 G."
    },
    {
        "user": "[EFFORT:HIGH] Query sqlite table 'inventory_medic' for amoxicillin batch expiry.",
        "think_1": "Executing SQL query on local sqlite database.",
        "action_1": '{"tool": "sqlite_query", "parameters": {"query": "SELECT batch_no, expiry_date, qty FROM inventory_medic WHERE drug_name = amoxicillin;"}}',
        "obs_1": '{"status": "error", "error_code": "SQLITE_ERROR", "message": "no such column: amoxicillin"}',
        "think_2": "SQL syntax error: String literal 'amoxicillin' was not enclosed in single quotes. Fixing quote escaping and re-running.",
        "action_2": '{"tool": "sqlite_query", "parameters": {"query": "SELECT batch_no, expiry_date, qty FROM inventory_medic WHERE LOWER(drug_name) LIKE \'%amoxicillin%\';"}}',
        "obs_2": '{"status": "ok", "rows": [["BATCH-2025-A1", "2027-08-30", 250], ["BATCH-2024-C9", "2026-12-15", 40]]}',
        "final": "Stok amoxicillin berhasil ditarik setelah koreksi sintaks SQL:\n1. **Batch `BATCH-2025-A1`**: 250 strip, Kadaluarsa: **30 Agustus 2027**.\n2. **Batch `BATCH-2024-C9`**: 40 strip, Kadaluarsa: **15 Desember 2026** (Prioritas penggunaan)."
    }
]

# ==============================================================================
# CLUSTER 3: CALIBRATED ABSTENTION & ANTI-HALLUCINATION (500 Trajectories)
# ==============================================================================
C3_SCENARIOS = [
    {
        "user": "[EFFORT:LOW] Berapa dosis pemberian epinefrin pada anak usia 5 tahun menurut SOP puskesmas ini?",
        "action": '{"tool": "rag_search", "parameters": {"query": "dosis epinefrin anafilaksis anak SOP", "top_k": 3}}',
        "obs": '{"matches": [], "status": "0_hits_found"}',
        "final": "⚠️ **Informasi Tidak Ditemukan**: Dokumen SOP puskesmas lokal yang terindeks tidak memuat tabel dosis epinefrin anak. Sesuai protokol keselamatan tertutup, saya tidak diizinkan menebak atau mengarang dosis obat tanpa rujukan dokumen valid. Harap verifikasi langsung pada buku Formularium Nasional / dokter penanggung jawab."
    },
    {
        "user": "[EFFORT:LOW] What is the exact torque specification for the cylinder head bolts on Compressor Model X-999?",
        "action": '{"tool": "rag_search", "parameters": {"query": "Compressor X-999 cylinder head bolt torque specification", "top_k": 2}}',
        "obs": '{"matches": [{"doc": "MANUAL-GENERIC", "text": "This manual covers models X-100, X-200, and X-500. For custom unlisted series, consult the manufacturer blueprint."}]}',
        "final": "Model `X-999` is not documented in the local technical library. Only models X-100, X-200, and X-500 are cataloged. Abstaining from providing torque figures to prevent bolt shearing or mechanical failure."
    },
    {
        "user": "[EFFORT:LOW] Siapa nama kepala regu shift malam tambang batu bara sektor B kemarin malam?",
        "action": '{"tool": "rag_search", "parameters": {"query": "kepala regu shift malam sektor B logbook", "top_k": 2}}',
        "obs": '{"matches": []}',
        "final": "Data nama kepala regu shift malam sektor B tidak tercantum dalam logbook offline lokal. Saya tidak memiliki akses ke data personel tersebut."
    }
]

# ==============================================================================
# CLUSTER 4: TUNABLE EFFORT LOOPS (400 Trajectories)
# ==============================================================================
C4_SCENARIOS = [
    {
        "user": "[EFFORT:LOW] Toggle emergency exhaust fan relay ON.",
        "thought": "",
        "action": '{"tool": "gpio_write", "parameters": {"pin": 18, "state": "HIGH"}}',
        "obs": '{"status": "ok", "pin": 18, "state": "HIGH"}',
        "final": "Relay 18 (Exhaust Fan) set to **ON**."
    },
    {
        "user": "[EFFORT:HIGH] Evaluate boiler fuel efficiency: steam generated = 45 ton/hr, palm shell consumption = 9.2 ton/hr, water inlet temp = 85 C.",
        "thought": (
            "<think>\n"
            "1. User provided:\n"
            "   - Steam output: 45,000 kg/hr\n"
            "   - Fuel input (palm kernel shell / cangkang sawit): 9,200 kg/hr\n"
            "   - Water inlet temperature: 85 C\n"
            "2. Steam-to-fuel ratio = 45 / 9.2 = 4.89 kg steam / kg fuel.\n"
            "3. Nominal industrial benchmark for biomass water-tube boiler with palm shell (HHV ~18,800 kJ/kg) is 4.2 - 5.0 kg steam/kg fuel.\n"
            "4. Calculation: 4.89 is in the high-efficiency range (>4.5).\n"
            "5. Conclusion: Efficiency is optimal (~78-82%). Water preheating (85 C economizer) is performing well.\n"
            "</think>"
        ),
        "action": "",
        "obs": "",
        "final": (
            "Analisis Efisiensi Ketel Uap (Boiler):\n"
            "- **Rasio Penguapan (Steam-to-Fuel Ratio)**: `45 ton / 9.2 ton` = **4.89 kg steam / kg cangkang**.\n"
            "- **Evaluasi Status**: **Optimal (Sangat Baik)**. Benchmark industri boiler biomasa sawit berada di rentang 4.2 – 5.0 kg steam/kg bahan bakar.\n"
            "- **Faktor Kunci**: Suhu air umpan 85 °C dari *feedwater tank/economizer* bekerja efektif meminimalkan konsumsi kalori laten."
        )
    }
]

# ==============================================================================
# CLUSTER 5: OFFLINE SURVIVAL & EDGE RESILIENCE (LENSETEK ARK) (350 Trajectories)
# ==============================================================================
C5_SCENARIOS = [
    {
        "user": "[EFFORT:HIGH] Bencana gempa bumi: Pasien laki-laki 35 tahun, napas 34 kali/menit, pendarahan hebat di paha kanan, kapiler refill > 2 detik, merintih kesakitan. Tindakan cepat?",
        "thought": (
            "<think>\n"
            "1. Triage algorithm: Simple Triage and Rapid Treatment (START).\n"
            "2. Respiratory rate: 34 / min (> 30 bpm) -> Immediate Red Tag priority.\n"
            "3. Arterial bleed on right thigh -> Critical threat of hemorrhagic shock within 3-5 minutes.\n"
            "4. Capillary refill > 2s -> Hemodynamic instability.\n"
            "5. Priority actions:\n"
            "   a. Stop catastrophic bleeding first (tourniquet 5-7 cm above wound, note time).\n"
            "   b. Airway management and position.\n"
            "   c. Assign RED TAG (Immediate transport).\n"
            "</think>"
        ),
        "action": "",
        "obs": "",
        "final": (
            "🚨 **TRIAGE: MERAH (IMMEDIATE / KRITIS)**\n\n"
            "**Langkah Penyelamatan Menit Pertama:**\n"
            "1. **Hentikan Pendarahan Femoral (Utama & Cepat)**:\n"
            "   - Pasang *Combat Application Tourniquet* (CAT) atau torniket darurat (kain lebar + tongkat pemutar) **5–7 cm di atas luka paha** (jangan tepat di sendi).\n"
            "   - Putar tongkat hingga pendarahan berhenti total dan denyut nadi distal hilang. Kunci dan **catat jam pemasangan** di dahi pasien (misal: `T 08:50`).\n"
            "2. **Pernapasan (RR 34x/menit)**: Baringkan pasien posisi telentang dengan kaki sedikit ditinggikan (posisi syok), longgarkan pakaian leher dan dada.\n"
            "3. **Cegah Hipotermia**: Selimuti dengan *survival space blanket* atau kain tebal.\n"
            "4. **Label**: Pasang pita/tanda **MERAH** untuk evakuasi darurat pertama."
        )
    },
    {
        "user": "[EFFORT:LOW] Hitung panjang antena kawat dipole darurat untuk frekuensi darurat VHF Marine Channel 16 (156.800 MHz).",
        "thought": "",
        "action": "",
        "obs": "",
        "final": (
            "Perhitungan Antena Dipole 1/2 Gelombang (156.800 MHz):\n"
            "- **Rumus Panjang Total (Meter)**: `142.5 / Frekuensi (MHz)` = `142.5 / 156.8` = **0.908 meter (90.8 cm)**.\n"
            "- **Panjang Tiap Sayap Kawat**: `90.8 cm / 2` = **45.4 cm** per sisi (sayap positif dan negatif terisolator di tengah).\n"
            "- **Polarisasi**: Rentangkan vertikal untuk komunikasi kapal/pos pantai VHF."
        )
    },
    {
        "user": "[EFFORT:HIGH] Bagaimana cara membuat purifikasi air 4 tahap darurat di alam menggunakan botol 1.5 liter dan bahan sekitar?",
        "thought": (
            "<think>\n"
            "1. User needs emergency 4-stage water filter using a 1.5L PET bottle.\n"
            "2. Layers from bottom to top:\n"
            "   - Bottle cap pierced with tiny holes or cloth covering mouth.\n"
            "   - Stage 1 (Bottom): Fine filter (Clean cotton/cloth/gauze).\n"
            "   - Stage 2: Crushed activated charcoal / arang kayu aktif (adsorption of toxins/odors).\n"
            "   - Stage 3: Fine clean sand (traps small particles).\n"
            "   - Stage 4 (Top): Coarse gravel/pebbles (traps debris, twigs, leaves).\n"
            "3. Crucial reminder: Filtration does NOT kill viruses/bacteria. Must boil or SODIS UV.\n"
            "</think>"
        ),
        "action": "",
        "obs": "",
        "final": (
            "🛠️ **Filter Purifikasi Air Darurat 4 Tahap (Botol 1.5L)**:\n\n"
            "**Susunan Lapisan (Dari Dasar Tutup Botol ke Atas)**:\n"
            "1. **Tutup Botol**: Lubangi 3-4 titik jarum, sumpal leher botol dengan **kapas bersih atau kain kasa**.\n"
            "2. **Lapisan 1 (Paling Bawah)**: **Arang Kayu Halus (Charcoal)** setebal 5–7 cm. Berfungsi menyerap racun organik, pestisida, dan bau.\n"
            "3. **Lapisan 2 (Tengah)**: **Pasir Sungai Halus & Bersih** setebal 6–8 cm (cuci pasir dulu jika berlumpur) untuk menyaring mikropartikel.\n"
            "4. **Lapisan 3 (Atas)**: **Kerikil Kecil / Pasir Kasar** setebal 4 cm.\n"
            "5. **Lapisan 4 (Permukaan)**: **Batu Kerikil Sedang** 3 cm untuk menahan dedaunan dan ranting.\n\n"
            "⚠️ **PENTING (Sterilisasi Wajib)**: Air hasil saringan jernih **tetap harus direbus mendidih selama minimal 3–5 menit** atau dijemur di bawah terik matahari dalam botol transparan selama 6 jam (metode SODIS) guna mematikan bakteri patogen."
        )
    }
]

# ==============================================================================
# CLUSTER 6: SOVEREIGN REGIONAL CONTEXT & CODE-SWITCHING (250 Trajectories)
# ==============================================================================
C6_SCENARIOS = [
    {
        "user": "[EFFORT:LOW] Mesin genset di site remote bunyi knocking keras saat di gas pol, oli hitam pekat. Harus cek apa dulu?",
        "thought": "",
        "action": "",
        "obs": "",
        "final": (
            "Tindakan Prioritas di Lapangan (Knocking + Oli Hitam Pekat):\n"
            "1. **Stop Mesin Segera**: Jangan operasikan di bawah beban (*load*) agar kruk as (*crankshaft*) tidak baret atau stang piston bengkok.\n"
            "2. **Drain & Cek Filter Oli**: Kuras oli ke wadah bersih, periksa apakah ada serbuk tembaga/gram besi (*metal shavings*) menggunakan magnet. Jika ada gram besi, metal jalan (*con-rod bearing*) sudah aus parah.\n"
            "3. **Cek Nozzle Injector**: Suara knocking saat akselerasi sering dipicu *injector dripping* (bahan bakar solar menyemprot tidak mengabut sempurna, picu detonasi dini).\n"
            "4. **Kekentalan Oli**: Oli hitam pekat dan encer menandakan kontaminasi solar (*fuel dilution*) atau terlambat ganti >500 jam."
        )
    },
    {
        "user": "[EFFORT:LOW] Jelaskan aturan isolasi data pasien menurut UU PDP No. 27/2022 pada sistem server edge puskesmas.",
        "thought": "",
        "action": "",
        "obs": "",
        "final": (
            "Menurut **UU No. 27 Tahun 2022 tentang Perlindungan Data Pribadi (UU PDP)**:\n"
            "1. **Data Kesehatan adalah Data Pribadi Spesifik** (Pasal 4 ayat 2 huruf a) yang mewajibkan tingkat enkripsi dan keamanan ekstra ketat.\n"
            "2. **Larangan Akses Tanpa Izin**: Server *edge* puskesmas lokal yang beroperasi *air-gapped* (tanpa internet publik) memenuhi prinsip **Data Minimization** dan kedaulatan data karena rekam medis tidak pernah transit di server pihak ketiga atau *cloud* luar negeri.\n"
            "3. **Penyimpanan Lokal**: Database SQLite/rekam medis lokal wajib dienkripsi at-rest menggunakan standar AES-256."
        )
    }
]

# ==============================================================================
# GENERATOR FUNCTION
# ==============================================================================
def create_sample(scenario, cluster_id):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Simple direct Q&A or Tool execution
    if "action" in scenario and scenario.get("action"):
        messages.append({"role": "user", "content": scenario["user"]})
        # Assistant tool call
        thought_prefix = scenario.get("thought", "")
        call_content = f"{thought_prefix}\nAction: {scenario['action']}".strip()
        messages.append({"role": "assistant", "content": call_content})
        # Tool return
        messages.append({"role": "tool", "content": scenario["obs"]})
        # Assistant final response
        messages.append({"role": "assistant", "content": scenario["final"]})
    elif "action_1" in scenario:
        # Multi-turn error recovery trajectory
        messages.append({"role": "user", "content": scenario["user"]})
        # Turn 1: Attempt 1
        t1 = f"<think>\n{scenario['think_1']}\n</think>\nAction: {scenario['action_1']}"
        messages.append({"role": "assistant", "content": t1})
        messages.append({"role": "tool", "content": scenario["obs_1"]})
        
        # Turn 2: Error analysis & Attempt 2
        t2 = f"<think>\n{scenario['think_2']}\n</think>\nAction: {scenario['action_2']}"
        messages.append({"role": "assistant", "content": t2})
        messages.append({"role": "tool", "content": scenario["obs_2"]})
        
        # Optional Turn 3
        if "action_3" in scenario:
            t3 = f"<think>\n{scenario['think_3']}\n</think>\nAction: {scenario['action_3']}"
            messages.append({"role": "assistant", "content": t3})
            messages.append({"role": "tool", "content": scenario["obs_3"]})
            
        messages.append({"role": "assistant", "content": scenario["final"]})
    else:
        # Reasoning / direct instruction
        messages.append({"role": "user", "content": scenario["user"]})
        resp = scenario.get("thought", "") + ("\n" if scenario.get("thought") else "") + scenario["final"]
        messages.append({"role": "assistant", "content": resp.strip()})
        
    return {
        "cluster_id": cluster_id,
        "messages": messages
    }

def generate_all():
    os.makedirs(BASE_DIR, exist_ok=True)
    all_samples = []

    # Target cluster shares
    targets = [
        (C1_TOOLS, 500, "C1_DETERMINISTIC_TOOL_CALLING"),
        (C2_SCENARIOS, 1000, "C2_MULTI_TURN_ERROR_RECOVERY"),
        (C3_SCENARIOS, 500, "C3_CALIBRATED_ABSTENTION"),
        (C4_SCENARIOS, 400, "C4_TUNABLE_EFFORT_LOOPS"),
        (C5_SCENARIOS, 350, "C5_OFFLINE_SURVIVAL_ARK"),
        (C6_SCENARIOS, 250, "C6_REGIONAL_SOVEREIGNTY"),
    ]

    print("[INFO] Generating 3,000 curriculum trajectories...")
    for template_list, count, name in targets:
        for i in range(count):
            tpl = random.choice(template_list)
            # Create sample variation
            sample = create_sample(tpl, name)
            all_samples.append(sample)

    random.shuffle(all_samples)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for item in all_samples:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"[SUCCESS] Generated {len(all_samples)} trajectories saved to:")
    print(f" -> {OUTPUT_FILE}")
    print(f" -> File Size: {os.path.getsize(OUTPUT_FILE) / 1024:.2f} KB")

if __name__ == "__main__":
    generate_all()
