---
name: plugin-maker
description: Merancang, menyusun (scaffolding), dan mengembangkan plugin baru untuk Lensetek Agent Harness sesuai standar modular lean
---

# 🛠️ Lensetek Plugin Maker Skill

Gunakan skill ini ketika pengguna meminta untuk membuat plugin baru, menambahkan kapabilitas custom, atau mempersiapkan kontribusi plugin ke repositori `local-agent-harness`.

---

## 📌 Alur Kerja Pembuatan Plugin

1. **Klarifikasi Tujuan & Identitas Plugin:**
   - Tentukan `id` unik dalam format kebab-case (contoh: `whatsapp-notifier`, `db-inspector`).
   - Tentukan kategori: `tools`, `ui`, `audio`, `dev`, `data`.
   - Pastikan deskripsi tersedia dalam 3 bahasa (English default, Indonesian, Chinese).

2. **Inisialisasi Kerangka Kerja (Scaffolding):**
   - Salin dari `plugins/_template/` ke `plugins/<plugin-id>/` atau panggil helper CLI `/plugins create <plugin-id>`.
   - Pastikan berkas-berkas berikut ada dan valid:
     - `plugin.json` (metadata, versi, permissions, dependencies)
     - `__init__.py` (ekspor hook)
     - `main.py` (eksekusi logika & registrasi tool/server)
     - `requirements.txt` (dependensi pihak ketiga jika diperlukan)
     - `README.md` (dokumentasi lengkap penggunaan)

3. **Prinsip Desain & Aturan Keamanan:**
   - **Workspace Boundary:** Seluruh operasi file baca/tulis dibatasi ke dalam folder proyek aktif (`context['workspace']`).
   - **Credential Protection:** Dilarang keras membaca atau mengekspos file rahasia (`.env`, `.env.*`, token, private keys, `.git/`) ke sisi klien atau model prompt yang tidak terlindungi.
   - **Mobile-View First:** Bila plugin memuat tampilan UI/Web, rancang tata letak responsif yang nyaman digunakan di layar sentuh ponsel.
   - **Optimal untuk Model 3B:** Bila plugin menyediakan tool agen, pastikan output teks hasil eksekusi diringkas/dibersihkan (maksimal 1.000–2.000 token) agar tidak membebani context window model SLM.

4. **Pendaftaran ke Katalog Publik:**
   - Tambahkan entri metadata ke `plugins/manifest.json` agar plugin dapat terdeteksi oleh perintah `/plugins` di seluruh instalasi pengguna.
