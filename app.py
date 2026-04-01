"""
Education Audit Tool — Web UI
Run with: python app.py
Then open http://localhost:5000 in your browser.
"""

import os
import sys
import json
import threading
import logging
from pathlib import Path
from datetime import datetime

# Load config.env into environment variables
_config = Path(__file__).parent / "config.env"
if _config.exists():
    for _line in _config.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

sys.path.insert(0, str(Path(__file__).parent / "src"))

from transcriber import transcribe_file
from summarizer import summarize_transcript
from compliance import flag_compliance_issues
from report_generator import generate_pdf_report
from organizer import organize_output

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

UPLOAD_DIR    = Path("input/uploads")
OUTPUT_DIR    = Path("output")
KEYWORDS_FILE = Path("keywords.txt")
HISTORY_FILE  = Path("output/history.json")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
for sub in ["transcripts", "summaries", "reports", "organized"]:
    (OUTPUT_DIR / sub).mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4",
    ".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".tiff",
}

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_keywords() -> list[str]:
    if KEYWORDS_FILE.exists():
        return [k.strip() for k in KEYWORDS_FILE.read_text().splitlines()
                if k.strip() and not k.startswith("#")]
    return []


def save_keywords(keywords: list[str]):
    lines = ["# Custom compliance keywords for education audits",
             "# One keyword or phrase per line", ""]
    lines += keywords
    KEYWORDS_FILE.write_text("\n".join(lines), encoding="utf-8")


def load_history() -> list[dict]:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def append_history(record: dict):
    history = load_history()
    history.insert(0, record)
    if len(history) > 200:
        logging.warning(f"Job history exceeds 200 records — oldest {len(history) - 200} record(s) will be dropped.")
    HISTORY_FILE.write_text(json.dumps(history[:200], indent=2), encoding="utf-8")


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_job(job_id: str, file_path: Path):
    def update(msg: str, step: str = None, pct: int = None):
        with jobs_lock:
            jobs[job_id]["log"].append(msg)
            if step:
                jobs[job_id]["step"] = step
            if pct is not None:
                jobs[job_id]["pct"] = pct

    with jobs_lock:
        jobs[job_id]["status"] = "running"

    keywords = load_keywords()
    transcript = summary = ""
    flags = []
    report_filename = ""

    try:
        update("Transcribing file...", step="Transcribing", pct=10)
        transcript = transcribe_file(file_path)
        (OUTPUT_DIR / "transcripts" / f"{file_path.stem}.txt").write_text(transcript, encoding="utf-8")
        update(f"Transcript saved ({len(transcript):,} characters)", pct=30)

        update("Sending to Claude for summarization...", step="Summarizing", pct=35)
        summary = summarize_transcript(transcript, source_name=file_path.name)
        (OUTPUT_DIR / "summaries" / f"{file_path.stem}_summary.txt").write_text(summary, encoding="utf-8")
        update("Summary complete", pct=60)

        update("Scanning for compliance keywords...", step="Compliance check", pct=62)
        flags = flag_compliance_issues(transcript, keywords=keywords)
        update(f"Compliance scan: {len(flags)} flag(s) found", pct=75)

        update("Generating PDF report...", step="Building report", pct=77)
        report_path = OUTPUT_DIR / "reports" / f"{file_path.stem}_report.pdf"
        generate_pdf_report(
            source_name=file_path.name, transcript=transcript,
            summary=summary, flags=flags, output_path=report_path,
        )
        report_filename = report_path.name
        update(f"PDF report ready: {report_filename}", pct=92)

        update("Archiving source file...", step="Organizing", pct=95)
        organize_output(file_path, OUTPUT_DIR)
        update("Source file archived", pct=100)

        completed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        with jobs_lock:
            jobs[job_id].update({
                "status": "done", "step": "Complete", "pct": 100,
                "report": report_filename,
                "flag_count": len(flags),
                "red_flags": len([f for f in flags if f["category"] == "red_flag"]),
                "summary_preview": summary[:400] if summary else "",
                "completed_at": completed_at,
            })

        append_history({
            "job_id": job_id, "filename": file_path.name,
            "completed_at": completed_at, "report": report_filename,
            "flag_count": len(flags),
            "red_flags": len([f for f in flags if f["category"] == "red_flag"]),
            "status": "done",
        })

    except Exception as e:
        with jobs_lock:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["step"] = "Error"
            jobs[job_id]["log"].append(f"Error: {e}")
        logging.exception(f"Job {job_id} failed")
        append_history({
            "job_id": job_id, "filename": file_path.name,
            "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "report": "", "flag_count": 0, "red_flags": 0, "status": "error",
        })


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/history")
def history_page():
    return render_template("history.html")

@app.route("/settings")
def settings_page():
    return render_template("settings.html")

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File type '{ext}' is not supported"}), 400

    safe_name = secure_filename(file.filename)
    save_path = UPLOAD_DIR / safe_name
    file.save(str(save_path))

    job_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    with jobs_lock:
        jobs[job_id] = {
            "status": "queued", "step": "Queued", "pct": 0,
            "log": [f"File received: {safe_name}"],
            "filename": safe_name, "report": "",
            "flag_count": 0, "red_flags": 0,
            "summary_preview": "", "completed_at": "",
        }

    threading.Thread(target=run_job, args=(job_id, save_path), daemon=True).start()
    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@app.route("/jobs")
def all_jobs():
    with jobs_lock:
        return jsonify(list(jobs.values()))

@app.route("/api/history")
def api_history():
    return jsonify(load_history())

@app.route("/api/keywords", methods=["GET"])
def get_keywords():
    return jsonify({"keywords": load_keywords()})

@app.route("/api/keywords", methods=["POST"])
def set_keywords():
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid request body"}), 400
    raw = data.get("keywords", [])
    if not isinstance(raw, list):
        return jsonify({"error": "'keywords' must be a list"}), 400
    keywords = [k.strip() for k in raw if isinstance(k, str) and k.strip()]
    save_keywords(keywords)
    return jsonify({"saved": len(keywords)})

@app.route("/download/<filename>")
def download(filename):
    safe = secure_filename(filename)
    if not safe:
        return jsonify({"error": "Invalid filename"}), 400
    return send_from_directory(str(OUTPUT_DIR / "reports"), safe, as_attachment=True)


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n  WARNING: ANTHROPIC_API_KEY is not set. Summarization will fail.")
        print("   Set it with:  export ANTHROPIC_API_KEY=sk-ant-...\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
