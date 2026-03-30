"""
Transcriber
Handles audio → text (via OpenAI Whisper) and document → text (PDF, DOCX, images via OCR).
"""

import os
import logging
from pathlib import Path

log = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4"}
DOC_EXTENSIONS = {".pdf", ".docx", ".txt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff"}


def transcribe_file(path: Path) -> str:
    """Route a file to the correct transcription method and return raw text."""
    ext = path.suffix.lower()

    if ext in AUDIO_EXTENSIONS:
        return _transcribe_audio(path)
    elif ext in DOC_EXTENSIONS:
        return _extract_document(path)
    elif ext in IMAGE_EXTENSIONS:
        return _ocr_image(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


# ── Audio ────────────────────────────────────────────────────────────────────

def _transcribe_audio(path: Path) -> str:
    """Use OpenAI Whisper (local model) to transcribe audio."""
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "whisper is not installed. Run: pip install openai-whisper"
        )

    log.info(f"    Loading Whisper model for: {path.name}")
    model = whisper.load_model("base")  # options: tiny, base, small, medium, large
    result = model.transcribe(str(path))
    return result["text"].strip()


# ── Documents ────────────────────────────────────────────────────────────────

def _extract_document(path: Path) -> str:
    ext = path.suffix.lower()

    if ext == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")

    elif ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")

        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n\n".join(text_parts).strip()

    elif ext == ".docx":
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx not installed. Run: pip install python-docx")

        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs).strip()

    else:
        raise ValueError(f"Unsupported document type: {ext}")


# ── Images / OCR ─────────────────────────────────────────────────────────────

def _ocr_image(path: Path) -> str:
    """Use Tesseract OCR via pytesseract to extract text from an image."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        raise ImportError(
            "pytesseract or Pillow not installed.\n"
            "Run: pip install pytesseract Pillow\n"
            "Also install Tesseract OCR engine: https://github.com/tesseract-ocr/tesseract"
        )

    img = Image.open(path)
    return pytesseract.image_to_string(img).strip()
