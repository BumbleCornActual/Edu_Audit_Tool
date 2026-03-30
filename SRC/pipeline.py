"""
Education Audit Transcription Pipeline
Main orchestrator — runs the full workflow on a file or directory.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

from transcriber import transcribe_file
from summarizer import summarize_transcript
from compliance import flag_compliance_issues
from report_generator import generate_pdf_report
from organizer import organize_output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pipeline.log"),
    ],
)
log = logging.getLogger(__name__)

SUPPORTED_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4"}
SUPPORTED_DOCS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".tiff"}


def process_file(input_path: Path, output_dir: Path, keywords: list[str]) -> dict:
    """Run the full pipeline on a single file. Returns a result summary dict."""
    log.info(f"Processing: {input_path.name}")
    result = {"file": input_path.name, "status": "ok", "steps": {}}

    # ── Step 1: Transcribe ───────────────────────────────────────────────────
    try:
        transcript = transcribe_file(input_path)
        transcript_path = output_dir / "transcripts" / f"{input_path.stem}.txt"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(transcript, encoding="utf-8")
        result["steps"]["transcription"] = "ok"
        log.info(f"  ✓ Transcription saved → {transcript_path.name}")
    except Exception as e:
        log.error(f"  ✗ Transcription failed: {e}")
        result["steps"]["transcription"] = f"error: {e}"
        result["status"] = "partial"
        return result

    # ── Step 2: Summarize ────────────────────────────────────────────────────
    try:
        summary = summarize_transcript(transcript, source_name=input_path.name)
        summary_path = output_dir / "summaries" / f"{input_path.stem}_summary.txt"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary, encoding="utf-8")
        result["steps"]["summary"] = "ok"
        log.info(f"  ✓ Summary saved → {summary_path.name}")
    except Exception as e:
        log.error(f"  ✗ Summarization failed: {e}")
        result["steps"]["summary"] = f"error: {e}"

    # ── Step 3: Compliance Flags ─────────────────────────────────────────────
    try:
        flags = flag_compliance_issues(transcript, keywords=keywords)
        result["flags"] = flags
        result["steps"]["compliance"] = f"{len(flags)} flag(s)"
        log.info(f"  ✓ Compliance check — {len(flags)} flag(s)")
    except Exception as e:
        log.error(f"  ✗ Compliance check failed: {e}")
        result["steps"]["compliance"] = f"error: {e}"
        flags = []

    # ── Step 4: Generate PDF Report ──────────────────────────────────────────
    try:
        report_path = output_dir / "reports" / f"{input_path.stem}_report.pdf"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        generate_pdf_report(
            source_name=input_path.name,
            transcript=transcript,
            summary=summary if "summary" in result["steps"] and result["steps"]["summary"] == "ok" else "",
            flags=flags,
            output_path=report_path,
        )
        result["steps"]["report"] = "ok"
        log.info(f"  ✓ PDF report saved → {report_path.name}")
    except Exception as e:
        log.error(f"  ✗ Report generation failed: {e}")
        result["steps"]["report"] = f"error: {e}"

    # ── Step 5: Organize ─────────────────────────────────────────────────────
    try:
        organize_output(input_path, output_dir)
        result["steps"]["organize"] = "ok"
    except Exception as e:
        log.warning(f"  ⚠ Organizer warning: {e}")
        result["steps"]["organize"] = f"warning: {e}"

    return result


def run_pipeline(input_path: str, output_dir: str, keywords_file: str = None):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load custom compliance keywords
    keywords = []
    if keywords_file and Path(keywords_file).exists():
        keywords = [k.strip() for k in Path(keywords_file).read_text().splitlines() if k.strip()]
    else:
        keywords = [
            "IEP", "IDEA", "Section 504", "FERPA", "accommodation",
            "modification", "due process", "evaluation", "eligibility",
            "placement", "least restrictive environment", "LRE",
            "behavior intervention plan", "BIP", "functional behavior assessment", "FBA",
        ]

    # Collect files
    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = [
            f for f in input_path.rglob("*")
            if f.suffix.lower() in SUPPORTED_AUDIO | SUPPORTED_DOCS
        ]
    else:
        log.error(f"Input path not found: {input_path}")
        sys.exit(1)

    log.info(f"Found {len(files)} file(s) to process.")
    results = []
    for f in files:
        r = process_file(f, output_dir, keywords)
        results.append(r)

    # Session summary
    ok = sum(1 for r in results if r["status"] == "ok")
    partial = sum(1 for r in results if r["status"] == "partial")
    total_flags = sum(len(r.get("flags", [])) for r in results)

    log.info("=" * 50)
    log.info(f"Session complete — {ok} OK / {partial} partial / {total_flags} compliance flags total")
    log.info("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Education Audit Transcription Pipeline")
    parser.add_argument("input", help="File or directory to process")
    parser.add_argument("--output", default="output", help="Output directory (default: ./output)")
    parser.add_argument("--keywords", help="Path to custom compliance keywords file (one per line)")
    args = parser.parse_args()

    run_pipeline(args.input, args.output, args.keywords)
