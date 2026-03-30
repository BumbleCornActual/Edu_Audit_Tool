"""
Organizer
Moves processed source files into a dated archive folder so the input/ directory stays clean.
"""

import shutil
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)


def organize_output(source_file: Path, output_dir: Path):
    """
    Move the source file into output/organized/YYYY-MM-DD/ after processing.
    Keeps the input directory clean between runs.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    archive_dir = output_dir / "organized" / today
    archive_dir.mkdir(parents=True, exist_ok=True)

    dest = archive_dir / source_file.name

    # Avoid overwriting if same filename was processed earlier today
    if dest.exists():
        stem = source_file.stem
        suffix = source_file.suffix
        timestamp = datetime.now().strftime("%H%M%S")
        dest = archive_dir / f"{stem}_{timestamp}{suffix}"

    shutil.move(str(source_file), str(dest))
    log.info(f"    Archived source file → organized/{today}/{dest.name}")
