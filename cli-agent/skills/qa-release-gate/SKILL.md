---
name: qa-release-gate
description: Audit QA rilis Lensetek dengan selalu memeriksa Obsidian Vault rule of thumb, versi/What's New, sinkronisasi landing page, paritas CLI-WebUI, keamanan kredensial, dan gate konfirmasi commit/push
---

# QA Release Gate & Vault Compliance Skill

Gunakan skill ini sebelum menyelesaikan perubahan besar, merilis versi baru, atau melakukan `commit`/`push`:

1. **Baca Rule of Thumb di Vault (Wajib):**
   - Baca `C:\Users\ACER\Documents\Obsidian Vault\Lensetek-Rule-of-Thumb.md` terlebih dahulu agar seluruh aturan terbaru selalu diterapkan.
2. **Audit Versi & What's New (`cli-agent/version.json` & `cli-agent/version.py`):**
   - Pastikan nomor versi dan `release_date` sinkron di kedua file.
   - Pastikan isi *What's New* / `CHANGELOG` default berbahasa **English** dan berfokus pada **aplikasi** (CLI, WebUI, Installer, Downloader), bukan perubahan kosmetik landing page.
   - Jika ada perbaikan/fitur untuk pengguna akhir, pastikan versi sudah di-bump agar `lensetek --update` / `/update` mendeteksinya.
3. **Sinkronisasi Landing Page & Dokumentasi:**
   - Jika ada *What's New* / rilis baru, periksa apakah `index.html`, `docs/index.html`, dan `README.md` perlu diperbarui, dan pastikan tampilan tetap **responsive mobile-view first**.
4. **Paritas CLI & WebUI:**
   - Pastikan seluruh *slash command* di `cli-agent/i18n.py` (`get_localized_slash_items`) memiliki handler di `cli-agent/main.py` dan `plugins/webui/server.py`.
   - Pastikan fitur kontrol proses (Cancel/Stop) dan mode `/goal` / `/loop` berjalan di WebUI.
5. **Ketahanan Installer & Lifecycle:**
   - Pastikan `install.ps1` / `install.sh` menghentikan `llama-server` & WebUI sebelum update/repair, memvalidasi `cli-agent/main.py`, dan menyediakan fallback ZIP.
6. **Keamanan Kredensial & Verifikasi Sintaks:**
   - Cek `git status` dan pastikan tidak ada kredensial, `.env`, API key, atau file sensitif yang terekspos di frontend/client-side atau ikut ter-stage.
   - Jalankan `py_compile` pada file Python yang berubah dan validasi AST PowerShell pada `install.ps1`.
7. **Laporan QA & Konfirmasi Commit/Push:**
   - Sajikan hasil audit (PASS/FAIL per poin). **Jangan pernah** menjalankan `git commit` atau `git push` tanpa konfirmasi eksplisit dari pengguna.
