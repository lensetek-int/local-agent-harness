"""Modul OCR lokal untuk membaca gambar dan scan PDF (faktur pajak, struk, surat) tanpa API cloud."""

from pathlib import Path
from typing import Any


def extract_text_from_image(image_path: str | Path) -> dict[str, Any]:
    """Menjalankan OCR lokal pada file gambar (.png/.jpg) menggunakan RapidOCR atau Tesseract."""
    path = Path(image_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File gambar tidak ditemukan: {path}")

    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        result, _ = engine(str(path))
        lines = [item[1] for item in (result or [])]
        return {"engine": "rapidocr", "file": str(path), "text": "\n".join(lines)}
    except ImportError:
        pass

    try:
        from PIL import Image
        import pytesseract

        text = pytesseract.image_to_string(Image.open(path), lang="ind+eng")
        return {"engine": "tesseract", "file": str(path), "text": text.strip()}
    except ImportError as exc:
        raise RuntimeError(
            "Engine OCR belum terpasang. Install 'rapidocr-onnxruntime' atau 'pytesseract' + 'pillow'."
        ) from exc


def ocr_scanned_pdf(pdf_path: str | Path, dpi: int = 200) -> dict[str, Any]:
    """Merender halaman PDF scan menjadi gambar sementara lalu mengekstrak teks via OCR lokal."""
    import tempfile
    import fitz  # PyMuPDF

    path = Path(pdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File PDF tidak ditemukan: {path}")

    doc = fitz.open(str(path))
    pages_text: list[str] = []
    engine_used = "none"

    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            img_path = Path(tmpdir) / f"page_{idx + 1}.png"
            pix.save(str(img_path))
            res = extract_text_from_image(img_path)
            engine_used = res["engine"]
            pages_text.append(f"--- HALAMAN {idx + 1} ---\n{res['text']}")

    doc.close()
    return {"engine": engine_used, "file": str(path), "pages": len(pages_text), "text": "\n\n".join(pages_text)}
