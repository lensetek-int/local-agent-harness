#!/usr/bin/env python3
"""
Tool Otomatis Ingest Dokumen SOP ke Basis Pengetahuan RAG Lokal (Lensetek EdgeRAG)
Tanpa perlu melatih ulang (fine-tuning) model AI.

Penggunaan:
  py ingest_sop.py dokumen_sop.pdf
  py ingest_sop.py --folder ./sop
  py ingest_sop.py --list
  py ingest_sop.py --search "batas tekanan boiler"
"""

import os
import sys
import argparse
import glob
from rag_engine import EdgeRAG

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def ingest_file(rag, file_path):
    if not os.path.exists(file_path):
        print(f"[ERROR] Berkas tidak ditemukan: {file_path}")
        return False
    
    filename = os.path.basename(file_path)
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        res = rag.add_document(filename, data)
        print(f"  [✓] Berhasil diindeks: {filename}")
        print(f"      - Ukuran Teks : {res.get('char_count', 0):,} karakter")
        print(f"      - Potongan    : {res.get('chunk_count', 0)} chunk")
        return True
    except Exception as e:
        print(f"  [!] Gagal mengindeks {filename}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Ingest Dokumen SOP ke Basis Pengetahuan RAG Lensetek")
    parser.add_argument("file", nargs="?", help="Path ke berkas SOP tunggal (.pdf, .docx, .txt, .md, .csv, .json)")
    parser.add_argument("--folder", type=str, help="Path ke folder berisi banyak berkas SOP")
    parser.add_argument("--list", action="store_true", help="Lihat daftar seluruh SOP yang saat ini terindeks")
    parser.add_argument("--search", type=str, help="Uji coba pencarian semantik pada SOP yang terindeks")
    parser.add_argument("--clear", action="store_true", help="Hapus seluruh dokumen dari database RAG")

    args = parser.parse_args()
    rag = EdgeRAG()

    if args.list:
        docs = rag.list_documents()
        stats = rag.get_stats()
        print("\n" + "=" * 60)
        print("       DAFTAR DOKUMEN SOP DALAM BASIS PENGETAHUAN RAG")
        print("=" * 60)
        print(f"Total Dokumen: {stats.get('total_documents', 0)} | Total Chunk: {stats.get('total_chunks', 0)} | Ukuran DB: {stats.get('db_size_kb', 0)} KB\n")
        if not docs:
            print("  (Belum ada dokumen SOP yang diindeks)")
        else:
            for i, d in enumerate(docs, 1):
                print(f"  {i}. [{d['file_type']}] {d['filename']}")
                print(f"     -> {d['chunk_count']} chunk | {d['char_count']:,} karakter | {d['created_at']}")
        print("=" * 60 + "\n")
        return

    if args.clear:
        confirm = input("Apakah Anda yakin ingin menghapus SEMUA dokumen SOP dari database RAG? (y/N): ")
        if confirm.lower() == 'y':
            with rag._get_connection() as conn:
                conn.execute("DELETE FROM chunks;")
                conn.execute("DELETE FROM documents;")
                try:
                    conn.execute("DELETE FROM chunks_fts;")
                except Exception:
                    pass
                conn.commit()
            print("[✓] Seluruh dokumen RAG berhasil dibersihkan.")
        return

    if args.search:
        print(f"\n[INFO] Menjalankan pencarian semantik untuk: '{args.search}'...")
        results = rag.search(args.search, top_k=3)
        if not results:
            print("  [!] Tidak ada hasil yang relevan ditemukan.")
        else:
            for i, r in enumerate(results, 1):
                print(f"\n--- Hasil {i} (Skor Relevansi: {r['score']:.4f}) ---")
                print(f"Sumber: {r['filename']}")
                print(f"Kutipan:\n{r['content']}")
        print()
        return

    if args.folder:
        folder_path = os.path.abspath(args.folder)
        if not os.path.isdir(folder_path):
            print(f"[ERROR] Folder tidak ditemukan: {folder_path}")
            return
        supported_exts = ("*.pdf", "*.docx", "*.txt", "*.md", "*.csv", "*.json")
        files = []
        for ext in supported_exts:
            files.extend(glob.glob(os.path.join(folder_path, ext)))
        
        if not files:
            print(f"[!] Tidak ada file yang didukung di folder: {folder_path}")
            return
        
        print(f"\n[INFO] Menemukan {len(files)} berkas SOP di '{folder_path}'...")
        success_count = 0
        for f in files:
            if ingest_file(rag, f):
                success_count += 1
        print(f"\n[✓] Selesai: {success_count}/{len(files)} berkas berhasil diindeks ke RAG!\n")
        return

    if args.file:
        print(f"\n[INFO] Memproses berkas SOP: {args.file}")
        ingest_file(rag, args.file)
        print()
        return

    parser.print_help()

if __name__ == "__main__":
    main()
