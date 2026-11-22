# 📚 Panduan Lengkap: Menambahkan Dokumen SOP ke Lensetek Edge AI via RAG (Tanpa Training Ulang)

Panduan ini menjelaskan cara menambahkan dokumen **SOP (Standard Operating Procedure)**, manual operasional pabrik, instruksi kerja teknis, atau pedoman klinis ke dalam sistem **Lensetek Edge AI**.

> [!IMPORTANT]
> **Model AI Anda Sudah FIX & Siap Pakai (`lensetek-edge-loop-3b-q4_k_m.gguf`).**  
> Anda **TIDAK PERLU** melakukan pelatihan ulang (*fine-tuning/training*) setiap kali ada penambahan atau perubahan dokumen SOP. Pengetahuan SOP disuntikkan secara dinamis menggunakan teknologi **EdgeRAG (Retrieval-Augmented Generation)** berbasis SQLite lokal dan kalkulasi vektor instan.

---

## 🌟 Mengapa Menggunakan RAG, Bukan Melatih Ulang Model?

1. **Instan (< 2 Detik)**: Begitu dokumen SOP diunggah, model langsung dapat menjawab pertanyaan terkait SOP tersebut.
2. **Zero-Hallucination**: Model Lensetek dilatih dengan kemampuan *Calibrated Abstention*—model akan menjawab murni berdasarkan teks SOP resmi Anda dan menolak berspekulasi jika informasi tidak ditemukan.
3. **Fleksibel & Mudah Direvisi**: Jika SOP pabrik berubah versi (misal: SOP 2026 diperbarui ke 2027), Anda cukup menghapus dokumen lama dan mengunggah dokumen baru tanpa perlu menyewa GPU ratusan ribu rupiah.
4. **100% Privat & Offline**: Seluruh dokumen SOP dienkripsi dan disimpan lokal di komputer Anda (`knowledge_rag.db`), tidak pernah dikirim ke internet atau cloud pihak ketiga.

---

## 📄 Format Berkas SOP yang Didukung

Engine RAG secara otomatis mengenali dan mengekstrak isi teks dari format:
* **Dokumen Digital**: `.pdf` (Dokumen PDF resmi, cetak SOP, formularium)
* **Microsoft Word**: `.docx` (Dokumen naskah SOP dari Word)
* **Teks Terbuka**: `.txt`, `.md` (Markdown catatan instruksi kerja)
* **Data Tabel & Log**: `.csv`, `.json`, `.log` (Data tabel referensi mesin/parameter)

---

## 🛠️ Pilihan Metode Menambahkan Dokumen SOP

Anda dapat memilih salah satu dari 3 cara berikut sesuai kenyamanan Anda:

```
                      ┌──────────────────────────────────────────────┐
                      │            PILIH METODE INGEST SOP           │
                      └──────────────────────┬───────────────────────┘
                                             │
             ┌───────────────────────────────┼───────────────────────────────┐
             ▼                               ▼                               ▼
     [ METODE 1: VISUAL ]            [ METODE 2: TERMINAL ]          [ METODE 3: REST API ]
     Buka Web UI Studio              Gunakan py ingest_sop.py        Kirim ke Endpoint
     Klik 'Dokumen RAG'              Batch 1 folder SOP sekaligus    Otomatisasi ERP / Python
     Drag & Drop File                Cepat untuk puluhan berkas      Integrasi sistem backend
```

---

### METODE 1: Melalui Tampilan Web Studio UI (Paling Praktis)

Ini adalah cara termudah bagi operator pabrik atau staf tanpa keahlian pemrograman:

1. **Buka Aplikasi**:
   Jalankan `start.bat` (atau ketik `py app.py` di terminal).
2. **Akses Browser**:
   Buka alamat: [`http://localhost:3000`](http://localhost:3000).
3. **Buka Menu Dokumen RAG**:
   Pada bilah navigasi atas (header), klik tombol hijau **`📚 Dokumen RAG`**.
4. **Unggah Dokumen SOP**:
   * Jendela *Knowledge Base* akan muncul.
   * Tarik dan lepas (*Drag & Drop*) berkas SOP Anda ke area unggah, atau klik untuk memilih berkas dari komputer.
5. **Proses Pengindeksan Otomatis**:
   * Sistem akan memotong teks menjadi segmen semantik (*chunks*) dan menghitung vektor indeksnya.
   * Muncul notifikasi `✓ Berhasil diindeks` beserta rincian jumlah karakter dan potongan teks.
6. **Mulai Bertanya**:
   * Tutup modal, pastikan toggle **RAG** di dekat kolom input chat bertuliskan **`✓ Aktif`**.
   * Ketik pertanyaan Anda, misalnya:  
     *"Berapa batas tekanan aman boiler unit GEN-09 menurut SOP?"*  
     Model akan langsung merujuk pada dokumen yang baru Anda unggah!

---

### METODE 2: Melalui Skrip Terminal / CLI (`py ingest_sop.py`)

Sangat cocok jika Anda memiliki banyak berkas SOP (misal: puluhan PDF dalam satu folder) dan ingin memasukkannya sekaligus dalam 1 detik:

#### 1. Memasukkan Satu Berkas SOP
```bash
py ingest_sop.py SOP_Operasional_Boiler.pdf
```

#### 2. Memasukkan Seluruh Folder SOP Sekaligus (Batch Ingest)
Kumpulkan semua file SOP Anda ke dalam sebuah folder (misal: `./dokumen_sop`), lalu jalankan:
```bash
py ingest_sop.py --folder ./dokumen_sop
```
*Output:*
```text
[INFO] Menemukan 8 berkas SOP di 'C:\...\dokumen_sop'...
  [✓] Berhasil diindeks: SOP_Boiler_GEN09.pdf (12 chunk)
  [✓] Berhasil diindeks: SOP_K3_Keselamatan_Pabrik.docx (8 chunk)
  [✓] Berhasil diindeks: Pedoman_Dosis_Medis_Darurat.pdf (15 chunk)
[✓] Selesai: 8/8 berkas berhasil diindeks ke RAG!
```

#### 3. Mengecek Daftar Dokumen SOP yang Sedang Aktif
```bash
py ingest_sop.py --list
```
*Menampilkan daftar nama file, jenis format, jumlah karakter, dan tanggal dokumen diindeks.*

#### 4. Menguji Pencarian Semantik Dokumen Tanpa Menjalankan LLM
```bash
py ingest_sop.py --search "batas tekanan boiler"
```

#### 5. Membersihkan Seluruh Dokumen (Jika Ingin Reset Database)
```bash
py ingest_sop.py --clear
```

---

### METODE 3: Melalui Integrasi REST API (`/api/rag/upload`)

Jika Anda ingin dokumen SOP diunggah otomatis dari aplikasi web lain, sistem ERP pabrik, atau bot WhatsApp/Telegram:

* **Endpoint**: `POST http://localhost:3000/api/rag/upload`
* **Content-Type**: `application/json`

#### Contoh Payload 1: Mengirim Teks SOP Langsung
```json
{
  "filename": "SOP_Turbin_2026.txt",
  "text": "STANDAR OPERASIONAL PROSEDUR TURBIN:\n1. Suhu bantalan tidak boleh melebihi 75 derajat Celcius.\n2. Getaran getar maksimal adalah 4.5 mm/s."
}
```

#### Contoh Payload 2: Mengirim File Biner (Base64 PDF / Word)
```json
{
  "filename": "SOP_Klinik_Puskesmas.pdf",
  "content_base64": "data:application/pdf;base64,JVBERi0xLjQKJ..."
}
```

#### Contoh Panggilan via cURL:
```bash
curl -X POST http://localhost:3000/api/rag/upload \
  -H "Content-Type: application/json" \
  -d "{\"filename\": \"SOP_Mini.txt\", \"text\": \"Batas aman boiler adalah 42 bar.\"}"
```

---

## 🔍 Bagaimana Cara Kerja RAG Bersama Model Lensetek-Edge-Loop-3B?

```
┌─────────────────────────────────┐
│ Pertanyaan Pengguna:           │
│ "Berapa batas tekanan boiler?"  │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐       Pencarian Semantik (NumPy Cosine)
│    EdgeRAG Search Engine        │ ◄────────────────────────────────────────┐
└────────────────┬────────────────┘                                          │
                 │ Ditemukan kutipan: "Batas boiler GEN-09 adalah 42 bar"    │
                 ▼                                                           │
┌─────────────────────────────────┐                                          │
│  Injeksi Konteks ke Prompt:     │                               ┌──────────┴────────┐
│  [KONTEKS SOP TERVERIFIKASI]    │                               │  knowledge_rag.db │
│  Pasal 4: Batas aman = 42 bar.  │                               │  (SQLite Lokal)   │
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
│ Jawaban Akhir (Akurat & Terverifikasi):       │
│ "Berdasarkan SOP GEN-09 Pasal 4, batas aman   │
│  tekanan boiler adalah 42 bar."               │
└───────────────────────────────────────────────┘
```

1. **Penyaringan Relevansi Instan**: Query pengguna dicari kecocokannya dengan potongan dokumen SOP di database SQLite lokal menggunakan vektor NumPy (< 2 milidetik).
2. **Grounding Otomatis**: Potongan teks SOP yang paling relevan disisipkan ke dalam instruksi model.
3. **Penalaran Model**: Model `lensetek-edge-loop-3b` membaca kutipan tersebut dan merumuskan jawaban yang padat, presisi, dan sesuai dengan bahasa teknis pabrik/klinik.
4. **Proteksi Anti-Halusinasi**: Jika SOP yang dicari sama sekali tidak ada di database, model **tidak akan menebak-nebak angka berbahaya**, melainkan menjawab jujur: *"Informasi mengenai batas tersebut tidak tercantum dalam dokumen SOP lokal yang terdaftar."*

---

## 🔄 Cara Memperbarui (Revisi) Dokumen SOP

Jika perusahaan/instansi Anda menerbitkan revisi SOP baru:
1. Buka modal **`📚 Dokumen RAG`** di Web Studio UI.
2. Klik tombol **Hapus** (ikon tempat sampah) pada dokumen SOP versi lama.
3. Unggah berkas SOP versi baru.
4. **Selesai!** Model akan seketika itu juga mengikuti instruksi SOP terbaru tanpa perlu merestart server.
