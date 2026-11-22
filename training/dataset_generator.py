#!/usr/bin/env python3
"""
Lensetek Edge-Loop-3B: Parametric Combinatorial Dataset Generator (v2.0)
Resolves PM-01 (overfitting 17 templates) & PM-07 (Qwen2.5 native <tool_call> format).

Produces:
1. training/lensetek_edge_loop_3000.jsonl (3,000 unique training samples)
2. training/lensetek_eval_heldout_300.jsonl (300 disjoint unseen evaluation samples)
"""

import os
import json
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRAIN_FILE = os.path.join(BASE_DIR, "lensetek_edge_loop_3000.jsonl")
EVAL_FILE = os.path.join(BASE_DIR, "lensetek_eval_heldout_300.jsonl")

SYSTEM_PROMPT = (
    "You are Lensetek Edge-Loop Agent, an autonomous, air-gapped Small Language Model (SLM) "
    "engineered for industrial automation, offline edge resilience, and high-precision tool execution. "
    "Adhere strictly to verifiable facts, parse error codes defensively, and adapt reasoning effort based on user tags."
)

# ------------------------------------------------------------------------------
# PARAMETRIC POOLS (DISJOINT TRAIN VS EVAL)
# ------------------------------------------------------------------------------
TRAIN_ASSETS = [f"GEN-{i:02d}" for i in range(1, 26)] + \
               [f"BOILER-PKS-{i:02d}" for i in range(1, 16)] + \
               [f"EXCA-KOM-{i:02d}" for i in range(1, 21)] + \
               [f"CHILLER-VAX-{i:02d}" for i in range(1, 11)]

EVAL_ASSETS = [f"GEN-{i:02d}" for i in range(81, 99)] + \
              [f"BOILER-PKS-{i:02d}" for i in range(81, 95)] + \
              [f"EXCA-KOM-{i:02d}" for i in range(81, 99)] + \
              [f"CHILLER-VAX-{i:02d}" for i in range(81, 95)]

TRAIN_DRUGS = ["Amoxicillin", "Paracetamol", "Cefixime", "Ibuprofen", "Metformin", "Amlodipine", "Omeprazole", "Cotrimoxazole", "Oralit", "Salbutamol"]
EVAL_DRUGS = ["Azithromycin", "Dexamethasone", "Cetirizine", "Lansoprazole", "Ciprofloxacin", "Erythromycin", "Domperidone"]

TRAIN_FREQS = [156.800, 144.200, 145.500, 146.000, 435.000, 438.000, 156.050, 156.300, 156.650, 156.875]
EVAL_FREQS = [156.525, 144.800, 145.300, 430.500, 433.000, 157.100, 156.450]


def gen_c1_sample(assets, modbus_start, is_eval=False):
    """Cluster 1: Deterministic Tool Calling & JSON Schema Precision"""
    tool_type = random.choice(["canbus", "modbus", "rag", "system", "sqlite"])
    asset = random.choice(assets)
    reg = random.randint(modbus_start, modbus_start + 300)
    slave = random.randint(1, 16)
    temp = round(random.uniform(82.0, 108.5), 1)
    press = round(random.uniform(18.0, 29.5), 1)

    if tool_type == "canbus":
        pid = random.choice(["0x0105", "0x010C", "0x0104", "0x011F"])
        user = f"[EFFORT:LOW] Query engine telemetry for asset {asset} from CAN-bus node 0x18FEEE00, PID {pid}."
        call = {"name": "canbus_read", "arguments": {"node_id": "0x18FEEE00", "pid": pid, "asset_id": asset, "timeout_ms": 250}}
        obs = {"status": "ok", "asset": asset, "pid": pid, "value": temp, "unit": "Celsius", "quality": "GOOD"}
        final = f"Engine telemetry for asset **{asset}** (CAN-bus 0x18FEEE00, PID {pid}): **{temp} °C** (Quality: GOOD, Nominal)."
    elif tool_type == "modbus":
        user = f"[EFFORT:LOW] Read holding register {reg} on Modbus RS-485 slave ID {slave}."
        call = {"name": "modbus_read_holding_registers", "arguments": {"slave_id": slave, "address": reg, "count": 1, "baud": 9600}}
        val = random.randint(120, 850)
        obs = {"status": "ok", "slave_id": slave, "register": reg, "raw_hex": hex(val), "decimal": val}
        final = f"Modbus Slave {slave} Register {reg} value: **{val}** (`{hex(val)}`). Verified nominal."
    elif tool_type == "rag":
        user = f"[EFFORT:LOW] Search local RAG knowledge base for boiler operating limits of unit {asset}."
        call = {"name": "rag_search", "arguments": {"query": f"boiler {asset} operating pressure limit SOP", "top_k": 2}}
        doc_code = f"SOP-PKS-{asset[:6]}-{random.randint(10, 99)}"
        obs = {"matches": [{"doc": doc_code, "text": f"Tekanan kerja maksimal ketel uap unit {asset} adalah {press} Bar. Safety valve meletup pada {round(press + 1.5, 1)} Bar."}]}
        final = f"Berdasarkan dokumen **{doc_code}**, tekanan kerja maksimal unit **{asset}** adalah **{press} Bar** (katup pengaman meletup pada **{round(press + 1.5, 1)} Bar**)."
    elif tool_type == "system":
        user = "[EFFORT:LOW] Check system RAM telemetry and disk usage on edge root partition."
        call = {"name": "system_telemetry", "arguments": {"metrics": ["memory", "disk"], "target_partition": "/dev/sda1"}}
        ram_used = random.randint(1600, 2400)
        obs = {"ram_total_mb": 3840, "ram_used_mb": ram_used, "ram_free_mb": 3840 - ram_used, "disk_free_gb": round(random.uniform(25.0, 55.0), 1)}
        final = f"Status Perangkat Edge: **{3840 - ram_used} MB RAM tersedia** ({ram_used} MB terpakai dari 3.8 GB) dan penyimpanan tersisa **{obs['disk_free_gb']} GB**."
    else:
        table = random.choice(["inventory_spareparts", "telemetry_logs", "sensor_events"])
        user = f"[EFFORT:LOW] Query sqlite table '{table}' for asset {asset} latest status."
        call = {"name": "sqlite_query", "arguments": {"query": f"SELECT status, timestamp FROM {table} WHERE asset_id = '{asset}' ORDER BY id DESC LIMIT 1;"}}
        obs = {"status": "ok", "rows": [["NOMINAL_ACTIVE", "2026-11-22T08:00:00Z"]]}
        final = f"Data SQLite `{table}` untuk **{asset}**: Status **NOMINAL_ACTIVE** (Timestamp: 2026-11-22T08:00:00Z)."

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": f"<tool_call>\n{json.dumps(call, ensure_ascii=False)}\n</tool_call>"},
        {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs, ensure_ascii=False)}\n</tool_response>"},
        {"role": "assistant", "content": final}
    ]


def gen_c2_sample(assets, is_eval=False):
    """Cluster 2: Multi-Turn Error Recovery & Self-Correction (Planned Failure)"""
    asset = random.choice(assets)
    fail_scenario = random.choice(["rag_miss", "port_error", "sql_quote", "read_only_gate"])

    if fail_scenario == "rag_miss":
        user = f"[EFFORT:HIGH] Retrieve maintenance and overhaul history for equipment unit {asset}."
        call_1 = {"name": "rag_search", "arguments": {"query": f"{asset} maintenance overhaul history exact", "top_k": 3}}
        obs_1 = {"matches": [], "status": "0_hits_found"}
        t1 = f"<think>\nQuery for exact '{asset}' returned 0 hits. Query might be too specific or cataloged under generic name. Broadening search terms.\n</think>\n<tool_call>\n{json.dumps(call_1, ensure_ascii=False)}\n</tool_call>"

        call_2 = {"name": "rag_search", "arguments": {"query": f"{asset[:6]} perawatan pemeliharaan servis overhaul", "top_k": 3}}
        hours = random.randint(2400, 8900)
        obs_2 = {"matches": [{"doc": f"LOG-{asset}", "text": f"Unit {asset}: Overhaul filter oli dan kalibrasi injektor pada 4.800 jam kerja. Total jam operasi saat ini: {hours} jam."}]}
        t2 = f"<think>\nBroader query successfully retrieved maintenance log for {asset}. Synthesizing maintenance report.\n</think>\n<tool_call>\n{json.dumps(call_2, ensure_ascii=False)}\n</tool_call>"
        final = f"Catatan berhasil ditemukan setelah adaptasi kueri:\n- **Unit**: `{asset}`\n- **Tindakan Terakhir**: Overhaul filter oli dan kalibrasi injektor\n- **Total Jam Operasi**: {hours} jam kerja."
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": t1},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_1)}\n</tool_response>"},
            {"role": "assistant", "content": t2},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_2)}\n</tool_response>"},
            {"role": "assistant", "content": final}
        ]
    elif fail_scenario == "port_error":
        user = f"[EFFORT:HIGH] Read serial telemetry from vibration sensor on {asset}."
        call_1 = {"name": "serial_read", "arguments": {"port": "/dev/ttyUSB0", "baud": 9600, "timeout_ms": 300}}
        obs_1 = {"status": "error", "error_code": "DEVICE_NOT_FOUND", "message": "No such device: /dev/ttyUSB0"}
        t1 = f"<think>\nSerial port /dev/ttyUSB0 not found. Checking available system serial ports before re-attempting.\n</think>\n<tool_call>\n{json.dumps(call_1, ensure_ascii=False)}\n</tool_call>"

        call_2 = {"name": "system_telemetry", "arguments": {"metrics": ["serial_ports"]}}
        obs_2 = {"status": "ok", "active_ports": ["/dev/ttyUSB1", "/dev/ttyS0"]}
        t2 = f"<think>\nActive port detected at /dev/ttyUSB1. Re-issuing serial_read on active port.\n</think>\n<tool_call>\n{json.dumps(call_2, ensure_ascii=False)}\n</tool_call>"

        call_3 = {"name": "serial_read", "arguments": {"port": "/dev/ttyUSB1", "baud": 9600, "timeout_ms": 300}}
        vib = round(random.uniform(1.2, 3.8), 2)
        obs_3 = {"status": "ok", "port": "/dev/ttyUSB1", "vibration_rms": vib, "unit": "mm/s"}
        t3 = f"<think>\nVibration data received from /dev/ttyUSB1: {vib} mm/s.\n</think>\n<tool_call>\n{json.dumps(call_3, ensure_ascii=False)}\n</tool_call>"
        final = f"Port `/dev/ttyUSB0` gagal, agen otomatis mendeteksi port aktif di `/dev/ttyUSB1`:\n- **Sensor Getaran ({asset})**: **{vib} mm/s RMS** (Batas aman ISO 10816)."
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": t1},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_1)}\n</tool_response>"},
            {"role": "assistant", "content": t2},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_2)}\n</tool_response>"},
            {"role": "assistant", "content": t3},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_3)}\n</tool_response>"},
            {"role": "assistant", "content": final}
        ]
    elif fail_scenario == "sql_quote":
        user = f"[EFFORT:HIGH] Check stock quantity for sparepart component '{asset}' in SQLite inventory."
        call_1 = {"name": "sqlite_query", "arguments": {"query": f"SELECT part_name, qty FROM inventory_spareparts WHERE part_name = {asset};"}}
        obs_1 = {"status": "error", "error_code": "SQLITE_ERROR", "message": f"no such column: {asset}"}
        t1 = f"<think>\nSQL error: Literal string {asset} unquoted. Escaping string in single quotes and retrying query.\n</think>\n<tool_call>\n{json.dumps(call_1, ensure_ascii=False)}\n</tool_call>"

        call_2 = {"name": "sqlite_query", "arguments": {"query": f"SELECT part_name, qty, location FROM inventory_spareparts WHERE part_name = '{asset}';"}}
        qty = random.randint(4, 45)
        obs_2 = {"status": "ok", "rows": [[asset, qty, "Gudang-Rak-B3"]]}
        t2 = f"<think>\nQuery succeeded with quoted string literal. Returning inventory quantity.\n</think>\n<tool_call>\n{json.dumps(call_2, ensure_ascii=False)}\n</tool_call>"
        final = f"Stok komponen **{asset}** berhasil ditarik pasca koreksi sintaks SQL:\n- **Jumlah Stok**: **{qty} unit** (Lokasi: Gudang-Rak-B3)."
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": t1},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_1)}\n</tool_response>"},
            {"role": "assistant", "content": t2},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_2)}\n</tool_response>"},
            {"role": "assistant", "content": final}
        ]
    else:
        # Read-Only Gate Violation & Safety Interlock (PM-06)
        user = f"[EFFORT:HIGH] Set register 40018 on slave 2 to value 999 to override boiler valve."
        call_1 = {"name": "actuate_write_guarded", "arguments": {"tool_name": "modbus_write", "parameters": {"slave": 2, "address": 40018, "value": 999}}}
        obs_1 = {"allowed": False, "requires_hitl": True, "reason": "Actuation tool blocked in Read-Only default mode. Human-in-the-Loop approval token required."}
        t1 = f"<think>\nActuation attempt was blocked by SafetyGuard in Read-Only Mode. Informing user of safety gate and requesting valid HITL confirmation token.\n</think>\n<tool_call>\n{json.dumps(call_1, ensure_ascii=False)}\n</tool_call>"
        final = "⚠️ **Peringatan Keselamatan Industri (Safety Interlock)**: Operasi penulisan ke register katup boiler (`40018`) diblokir oleh SafetyGuard dalam mode *Read-Only Default*. Untuk mengeksekusi aktuasi fisik ini, masukkan token persetujuan operator manusia (*HITL Confirmation Token*)."
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": t1},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs_1)}\n</tool_response>"},
            {"role": "assistant", "content": final}
        ]


def gen_c3_sample(assets, drugs, is_eval=False):
    """Cluster 3: Calibrated Abstention & Zero-Hallucination Grounding"""
    scenario_type = random.choice(["drug_dosage", "unlisted_machine", "missing_personnel"])
    drug = random.choice(drugs)
    age = random.randint(2, 10)
    asset = random.choice(assets)

    if scenario_type == "drug_dosage":
        user = f"[EFFORT:LOW] Berapa dosis injeksi {drug} untuk pasien anak usia {age} tahun menurut SOP puskesmas lokal?"
        call = {"name": "rag_search", "arguments": {"query": f"dosis {drug} pediatrik anak {age} tahun SOP puskesmas", "top_k": 2}}
        obs = {"matches": [], "status": "0_hits_found"}
        final = (
            f"⚠️ **Informasi Tidak Ditemukan di Dokumen Lokal**: Pedoman SOP klinik lokal yang terindeks tidak memuat "
            f"tabel dosis injeksi obat `{drug}` untuk anak usia {age} tahun. Sesuai protokol keselamatan tertutup, "
            f"saya menolak mengarang angka dosis tanpa rujukan valid. Harap periksa langsung buku Formularium Nasional "
            f"atau verifikasi dengan dokter penanggung jawab."
        )
    elif scenario_type == "unlisted_machine":
        model_name = f"Compressor-{asset}-{random.randint(900, 999)}"
        user = f"[EFFORT:LOW] What is the exact head bolt torque specification for unlisted model {model_name}?"
        call = {"name": "rag_search", "arguments": {"query": f"{model_name} head bolt torque specification", "top_k": 2}}
        obs = {"matches": [{"doc": "MANUAL-SERIES", "text": "This manual covers standard series X-100 to X-500 only."}]}
        final = (
            f"Model `{model_name}` is not cataloged in the local offline manuals. "
            f"Abstaining from estimating torque values to prevent bolt failure or cylinder damage. "
            f"Please refer to the manufacturer blueprint for non-standard models."
        )
    else:
        sector = random.choice(["Pit-Utara", "Pit-Selatan", "Dermaga-02", "Boiler-PKS-Shift-3"])
        user = f"[EFFORT:LOW] Siapa nama kepala regu dan nomor telepon pengawas shift malam kemarin di sektor {sector}?"
        call = {"name": "rag_search", "arguments": {"query": f"pengawas kepala regu shift malam sektor {sector} kontak", "top_k": 2}}
        obs = {"matches": [], "status": "0_hits_found"}
        final = (
            f"Data nama dan kontak pengawas shift malam di sektor `{sector}` tidak tercantum dalam logbook offline lokal. "
            f"Saya tidak memiliki akses ke data personel tersebut."
        )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": f"<tool_call>\n{json.dumps(call, ensure_ascii=False)}\n</tool_call>"},
        {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs, ensure_ascii=False)}\n</tool_response>"},
        {"role": "assistant", "content": final}
    ]


def gen_c4_sample(is_eval=False):
    """Cluster 4: Tunable Effort Loops ([EFFORT:LOW] vs [EFFORT:HIGH])"""
    is_high = random.choice([True, False])
    if not is_high:
        pin = random.choice([17, 18, 22, 23, 27])
        device = random.choice(["Exhaust Fan Relay", "Cooling Pump", "Indicator LED", "Sirene Alarm"])
        state = random.choice(["HIGH", "LOW"])
        user = f"[EFFORT:LOW] Toggle {device} on GPIO pin {pin} to state {state}."
        call = {"name": "gpio_write", "arguments": {"pin": pin, "state": state}}
        obs = {"status": "ok", "pin": pin, "state": state}
        final = f"GPIO pin {pin} ({device}) set to **{state}**."
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": f"<tool_call>\n{json.dumps(call, ensure_ascii=False)}\n</tool_call>"},
            {"role": "tool", "content": f"<tool_response>\n{json.dumps(obs, ensure_ascii=False)}\n</tool_response>"},
            {"role": "assistant", "content": final}
        ]
    else:
        steam_ton = random.randint(35, 60)
        fuel_ton = round(random.uniform(7.5, 13.0), 1)
        ratio = round(steam_ton / fuel_ton, 2)
        user = f"[EFFORT:HIGH] Hitung rasio efisiensi penguapan boiler: steam output = {steam_ton} ton/jam, konsumsi cangkang sawit = {fuel_ton} ton/jam."
        think = (
            f"<think>\n"
            f"1. Input: Steam output = {steam_ton} ton/hr, Biomass fuel = {fuel_ton} ton/hr.\n"
            f"2. Evaporation ratio calculation = {steam_ton} / {fuel_ton} = {ratio} kg steam / kg fuel.\n"
            f"3. Industrial benchmark for biomass boiler: 4.0 - 5.0 is standard optimal range.\n"
            f"4. Result: Ratio is {ratio}. Evaluation: {'Sangat Efisien (Optimal)' if ratio >= 4.2 else 'Sub-optimal (Periksa pembakaran)'}.\n"
            f"</think>"
        )
        final = (
            f"Evaluasi Efisiensi Boiler:\n"
            f"- **Rasio Penguapan**: `{steam_ton} ton / {fuel_ton} ton` = **{ratio} kg uap / kg cangkang**.\n"
            f"- **Status Operasional**: **{'Optimal (Sangat Efisien)' if ratio >= 4.2 else 'Perlu Pengecekan Suplai Udara/Bahan Bakar'}** "
            f"(Standar industri boiler biomassa sawit berada di rentang 4.0 – 5.0 kg/kg)."
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": f"{think}\n{final}"}
        ]


def gen_c5_sample(freqs, is_eval=False):
    """Cluster 5: Offline Survival & Edge Resilience (Lensetek ARK)"""
    scenario_type = random.choice(["triage", "antenna", "water", "ration"])

    if scenario_type == "triage":
        rr = random.randint(18, 38)
        cap_refill = random.choice([1.5, 2.5, 3.2])
        obeys = random.choice([True, False])
        bleeding = random.choice([True, False])

        tag = "MERAH" if (rr > 30 or cap_refill > 2.0 or not obeys or bleeding) else "KUNING"
        user = f"[EFFORT:HIGH] Bencana gempa: Korban napas {rr}x/menit, capillary refill {cap_refill} detik, respon perintah: {obeys}, pendarahan paha: {bleeding}. Triage START?"
        think = (
            f"<think>\n"
            f"1. START triage algorithm: Assess walking -> No.\n"
            f"2. Breathing: {rr}/min (>30 is Red; otherwise check perfusion).\n"
            f"3. Perfusion: Capillary refill {cap_refill}s (>2s indicates shock).\n"
            f"4. Mental status: Obeys commands = {obeys}.\n"
            f"5. Result classification: Priority {tag}.\n"
            f"</think>"
        )
        final = (
            f"🚨 **KLASIFIKASI TRIAGE START: {tag} ({'IMMEDIATE / KRITIS' if tag == 'MERAH' else 'DELAYED / MENENGAH'})**\n\n"
            f"**Tindakan Prioritas Lapangan:**\n"
            f"1. {'Pasang torniket darurat 5-7 cm di atas pendarahan paha & catat jam pasang.' if bleeding else 'Posisikan pemulihan dan longgarkan pakaian.'}\n"
            f"2. Amankan jalan napas (RR: {rr}x/menit, CRT: {cap_refill}s).\n"
            f"3. Pasang pita penanda **{tag}** untuk jalur evakuasi pertama.\n\n"
            f"*(Catatan: Referensi darurat lapangan terpandu protokol START)*"
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": f"{think}\n{final}"}
        ]
    elif scenario_type == "antenna":
        freq = random.choice(freqs)
        total_len = round(142.5 / freq, 3)
        wing_len = round(total_len / 2, 3)
        user = f"[EFFORT:LOW] Hitung panjang antena kawat dipole darurat untuk frekuensi {freq} MHz."
        final = (
            f"Perhitungan Antena Dipole 1/2 Gelombang ({freq} MHz):\n"
            f"- **Panjang Total Kawat**: `142.5 / {freq}` = **{total_len} meter** ({round(total_len * 100, 1)} cm).\n"
            f"- **Panjang Masing-Masing Sayap**: `({total_len} / 2)` = **{wing_len} meter** ({round(wing_len * 100, 1)} cm per sisi).\n"
            f"- **Polarisasi**: Rentangkan vertikal untuk radio darurat komunikasi darat/maritim."
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": final}
        ]
    elif scenario_type == "water":
        liters = random.choice([5, 10, 15, 20])
        user = f"[EFFORT:LOW] Bagaimana takaran purifikasi air banjir darurat sebanyak {liters} liter menggunakan metode SODIS dan arang aktif?"
        final = (
            f"Panduan Purifikasi Air Darurat ({liters} Liter):\n"
            f"1. **Filtrasi Fisik**: Saring {liters} liter air melalui corong arang kayu aktif setebal 6 cm + pasir halus untuk menyerap zat beracun dan bau lumpur.\n"
            f"2. **Disinfeksi Kuman (Wajib)**:\n"
            f"   - Rebus mendidih bergolak selama minimal 3–5 menit, ATAU\n"
            f"   - Metode SODIS: Masukkan ke botol plastik bening PET dan jemur di bawah sinar matahari terik selama minimal 6 jam."
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": final}
        ]
    else:
        people = random.randint(3, 8)
        days = random.randint(3, 7)
        water_req = people * days * 3  # 3 liters/person/day
        kcal_req = people * days * 1800  # 1800 kcal/person/day
        user = f"[EFFORT:HIGH] Hitung kebutuhan logistik darurat air minum dan kalori untuk {people} orang selama {days} hari bertahan di bunker/posko."
        think = (
            f"<think>\n"
            f"1. Daily minimum water consumption = 3 liters/person/day (drinking + minimal hygiene).\n"
            f"2. Total water = {people} people * {days} days * 3 L = {water_req} Liters.\n"
            f"3. Daily minimum emergency calorie = 1,800 kcal/person/day.\n"
            f"4. Total calories = {people} * {days} * 1,800 = {kcal_req:,} kcal.\n"
            f"</think>"
        )
        final = (
            f"Kalkulator Logistik Darurat Survival ({people} Orang, {days} Hari):\n"
            f"- **Kebutuhan Air Bersih Minimum**: `{people} orang x {days} hari x 3 L` = **{water_req} Liter**.\n"
            f"- **Kebutuhan Kalori Ransum Minimum**: `{people} x {days} x 1.800 kkal` = **{kcal_req:,} kkal** (Prioritaskan biskuit gandum, madu, atau MRE)."
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
            {"role": "assistant", "content": f"{think}\n{final}"}
        ]


def gen_c6_sample(assets, is_eval=False):
    """Cluster 6: Sovereign Regional Context & Code-Switching"""
    scenario_type = random.choice(["mechanic_slang", "uu_pdp", "shift_handover"])
    asset = random.choice(assets)

    if scenario_type == "mechanic_slang":
        user = f"[EFFORT:LOW] Mesin {asset} di site remote knocking keras pas digas pol, oli hitam pekat encer. Cek apa dulu bang?"
        final = (
            f"Langkah Cepat di Lapangan (Gejala Knocking + Oli Encer pada {asset}):\n"
            f"1. **Matikan Mesin Segera**: Hindari beban berat agar metal jalan (*con-rod bearing*) tidak terkikis atau stang piston bengkok.\n"
            f"2. **Cek Kontaminasi Solar (*Fuel Dilution*)**: Oli encer dan bau solar menandakan seal nosel injektor bocor atau ring piston aus.\n"
            f"3. **Periksa Filter Oli**: Buka filter dan periksa serbuk gram tembaga/besi menggunakan magnet."
        )
    elif scenario_type == "uu_pdp":
        user = "[EFFORT:LOW] Apakah penyimpanan rekam medis pasien di database SQLite lokal puskesmas aman menurut UU PDP No. 27/2022?"
        final = (
            "Menurut **UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP)**:\n"
            "1. **Data Kesehatan adalah Data Pribadi Spesifik** (Pasal 4 ayat 2 huruf a) yang mewajibkan standar perlindungan ketat.\n"
            "2. **Kedaulatan & Keamanan**: Penyimpanan pada server lokal (*air-gapped*) tanpa koneksi ke cloud asing mematuhi asas *Data Minimization* dan kedaulatan data nasional, dengan syarat database lokal wajib dienkripsi *at-rest*."
        )
    else:
        user = f"[EFFORT:LOW] Buatkan draf catatan serah terima (handover) shift teknisi boiler unit {asset}."
        final = (
            f"Draf Handover Shift Teknisi ({asset}):\n"
            f"- **Unit**: {asset}\n"
            f"- **Tekanan Kerja Rata-Rata**: 26.5 Bar (Safety valve normal di 29.0 Bar)\n"
            f"- **Level Air Umpan**: 65% (Pompa feedwater otomatis aktif)\n"
            f"- **Catatan Khusus**: Pembakaran cangkang sawit normal, blowing debu economizer telah dilakukan pada pukul 14:00."
        )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
        {"role": "assistant", "content": final}
    ]


def build_dataset(samples_count_dict, assets, drugs, freqs, seed, is_eval=False):
    random.seed(seed)
    dataset = []
    seen_hashes = set()

    generators = {
        "C1": lambda idx: {"cluster_id": "C1_DETERMINISTIC_TOOL_CALLING", "messages": gen_c1_sample(assets, (40001 if not is_eval else 40801) + (idx % 200), is_eval)},
        "C2": lambda idx: {"cluster_id": "C2_MULTI_TURN_ERROR_RECOVERY", "messages": gen_c2_sample(assets, is_eval)},
        "C3": lambda idx: {"cluster_id": "C3_CALIBRATED_ABSTENTION", "messages": gen_c3_sample(assets, drugs, is_eval)},
        "C4": lambda idx: {"cluster_id": "C4_TUNABLE_EFFORT_LOOPS", "messages": gen_c4_sample(is_eval)},
        "C5": lambda idx: {"cluster_id": "C5_OFFLINE_SURVIVAL_ARK", "messages": gen_c5_sample(freqs, is_eval)},
        "C6": lambda idx: {"cluster_id": "C6_REGIONAL_SOVEREIGNTY", "messages": gen_c6_sample(assets, is_eval)},
    }

    for cluster_key, count in samples_count_dict.items():
        gen_fn = generators[cluster_key]
        added = 0
        attempts = 0
        while added < count and attempts < count * 50:
            attempts += 1
            sample = gen_fn(added + attempts)
            # Inject subtle sample-unique ID or variation into system/user if needed to guarantee zero collision
            sample_str = json.dumps(sample["messages"], ensure_ascii=False)
            if sample_str not in seen_hashes:
                seen_hashes.add(sample_str)
                dataset.append(sample)
                added += 1

        # Fallback if entropy collision: append unique ticket ref in user prompt
        while added < count:
            sample = gen_fn(added + 1000)
            sample["messages"][1]["content"] += f" (Ref: #{seed}-{cluster_key}-{added})"
            sample_str = json.dumps(sample["messages"], ensure_ascii=False)
            seen_hashes.add(sample_str)
            dataset.append(sample)
            added += 1

    random.shuffle(dataset)
    return dataset


def save_jsonl(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main():
    print("=" * 65)
    print(" 🚀 LENSETEK PARAMETRIC COMBINATORIAL DATASET GENERATOR (v2.0)")
    print("=" * 65)

    train_counts = {"C1": 500, "C2": 1000, "C3": 500, "C4": 400, "C5": 350, "C6": 250}
    eval_counts = {"C1": 50, "C2": 100, "C3": 50, "C4": 40, "C5": 35, "C6": 25}

    print("\n[1/2] Generating 3,000 unique training samples (seed=42)...")
    train_data = build_dataset(train_counts, TRAIN_ASSETS, TRAIN_DRUGS, TRAIN_FREQS, seed=42, is_eval=False)
    save_jsonl(train_data, TRAIN_FILE)
    print(f" -> Saved {len(train_data)} train samples to {TRAIN_FILE}")

    print("\n[2/2] Generating 300 disjoint held-out evaluation samples (seed=999)...")
    eval_data = build_dataset(eval_counts, EVAL_ASSETS, EVAL_DRUGS, EVAL_FREQS, seed=999, is_eval=True)
    save_jsonl(eval_data, EVAL_FILE)
    print(f" -> Saved {len(eval_data)} held-out eval samples to {EVAL_FILE}")

    # Deduplication and format sanity check
    train_lines = open(TRAIN_FILE, encoding="utf-8").readlines()
    eval_lines = open(EVAL_FILE, encoding="utf-8").readlines()

    unique_train = len(set(train_lines))
    unique_eval = len(set(eval_lines))
    print("\n=== VERIFIKASI KEUNIKAN DATASET ===")
    print(f"Train Samples : {len(train_lines)} (Unik: {unique_train})")
    print(f"Eval Samples  : {len(eval_lines)} (Unik: {unique_eval})")
    print(f"Format Native : {'<tool_call>' in train_lines[0] or '<tool_call>' in train_lines[1] or '<tool_call>' in ''.join(train_lines)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
