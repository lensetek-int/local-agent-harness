---
name: code-review
description: Melakukan review kode untuk mendeteksi bug, kebocoran kredensial, dan kebersihan arsitektur
---

# 🔍 Code Review Skill

Gunakan skill ini saat mereview kode:
1. **Keamanan Kredensial:** Periksa apakah ada API key, token, atau password yang ter-hardcode. Pastikan credential disimpan di `.env.local` atau environment variables.
2. **Potensi Bug & Error Handling:** Periksa try/except, penanganan kasus edge, dan tipe data.
3. **Kerapihan Sintaks:** Pastikan kode mudah dibaca, modular, dan mengikuti konvensi bahasa yang bersangkutan.
4. **Ringkasan:** Berikan temuan dalam poin-poin yang jelas beserta saran perbaikan baris per baris jika ada.
