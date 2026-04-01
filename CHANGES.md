# Change Log — Education Audit Tool

---

## Session: 2026-03-30

---

### SECURITY FIXES

---

#### [1] `app.py` — JSON validation on keyword POST endpoint

**Lines affected:** 229–233 (original) → 229–238 (updated)

**Original:**
```python
@app.route("/api/keywords", methods=["POST"])
def set_keywords():
    data = request.get_json()
    keywords = [k.strip() for k in data.get("keywords", []) if k.strip()]
    save_keywords(keywords)
    return jsonify({"saved": len(keywords)})
```

**Fixed:**
```python
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
```

**Why:** `request.get_json()` returns `None` if the body is not valid JSON or the Content-Type header is wrong. Calling `.get()` on `None` raises an `AttributeError`, crashing the app with an unhandled 500. Added `silent=True` to suppress the parse error, added type checks, and now returns proper 400 errors instead of crashing.

---

#### [2] `app.py` — Filename sanitization on download route

**Lines affected:** 235–237 (original) → 239–244 (updated)

**Original:**
```python
@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(str(OUTPUT_DIR / "reports"), filename, as_attachment=True)
```

**Fixed:**
```python
@app.route("/download/<filename>")
def download(filename):
    safe = secure_filename(filename)
    if not safe:
        return jsonify({"error": "Invalid filename"}), 400
    return send_from_directory(str(OUTPUT_DIR / "reports"), safe, as_attachment=True)
```

**Why:** `send_from_directory` from Werkzeug does block directory traversal internally, but passing the raw user-supplied filename is still bad practice. `secure_filename()` strips path separators, null bytes, and other dangerous characters before the value is passed down. Added an explicit 400 if the result is empty (e.g. filename was all dots or slashes).

---

#### [3] `SRC/report_generator.py` — XML escaping in ReportLab PDF output

**Lines affected:** 7–9 (imports, original) and 171–175 (original)

**Original (import section):**
```python
import logging
from pathlib import Path
from datetime import datetime
```

**Fixed (import section):**
```python
import logging
from pathlib import Path
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape
```

**Original (red flag context block):**
```python
story.append(Paragraph(
    f"<b>Line {flag['line_number']} — \"{flag['keyword']}\"</b>",
    body_style,
))
story.append(Paragraph(f"...{flag['context']}...", flag_context_style))
```

**Fixed:**
```python
story.append(Paragraph(
    f"<b>Line {flag['line_number']} — \"{xml_escape(flag['keyword'])}\"</b>",
    body_style,
))
story.append(Paragraph(f"...{xml_escape(flag['context'])}...", flag_context_style))
```

**Why:** ReportLab's `Paragraph()` parses its input as XML-like markup. If a keyword or context snippet contains `<`, `>`, or `&` (e.g. a custom keyword like `<no notice>`), ReportLab would either misparse it as a tag or raise an exception, corrupting or crashing the PDF build. `xml_escape()` converts those characters to safe entities (`&lt;`, `&gt;`, `&amp;`) before they enter the renderer.

---

#### [4] `SRC/compliance.py` — Word boundary keyword matching

**Lines affected:** 85–99 (original) → 88–97 (updated)

**Original:**
```python
for line_num, line in enumerate(lines, start=1):
    line_lower = line.lower()
    for keyword, category in all_keywords.items():
        if keyword in line_lower:
```

**Fixed:**
```python
# Pre-compile word-boundary patterns to avoid false positives
# e.g. "idea" should not match "ideal", "ada" should not match "adequate"
compiled = {kw: re.compile(r'\b' + re.escape(kw) + r'\b') for kw in all_keywords}

for line_num, line in enumerate(lines, start=1):
    line_lower = line.lower()
    for keyword, category in all_keywords.items():
        if compiled[keyword].search(line_lower):
```

**Why:** Simple substring matching (`"idea" in line_lower`) produces false positives — e.g. `"IDEA"` → `"idea"` matches inside `"ideal"` or `"ideas"`; `"ADA"` → `"ada"` matches inside `"adequate"`. Word-boundary regex (`\b`) ensures only whole-word matches are flagged. Patterns are pre-compiled outside the loop for performance.

---

#### [5] `Templates/settings.html` — Single-quote escaping in `escHtml`

**Line affected:** 185

**Original:**
```javascript
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
```

**Fixed:**
```javascript
function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
```

**Why:** The `onclick` handler on each keyword's delete button embeds the keyword inside single quotes: `onclick="removeKeyword('${escHtml(kw)}')"`. The original `escHtml` did not escape `'`, so a keyword containing a single quote (e.g. `parent doesn't need to`) could break out of the JS string and inject arbitrary JavaScript. Adding `&#39;` escaping closes this DOM-based XSS vector.

---

### BUG FIXES

---

#### [6] `app.py` — Silent history truncation warning

**Lines affected:** 80–83 (original) → 80–85 (updated)

**Original:**
```python
def append_history(record: dict):
    history = load_history()
    history.insert(0, record)
    HISTORY_FILE.write_text(json.dumps(history[:200], indent=2), encoding="utf-8")
```

**Fixed:**
```python
def append_history(record: dict):
    history = load_history()
    history.insert(0, record)
    if len(history) > 200:
        logging.warning(f"Job history exceeds 200 records — oldest {len(history) - 200} record(s) will be dropped.")
    HISTORY_FILE.write_text(json.dumps(history[:200], indent=2), encoding="utf-8")
```

**Why:** The 200-record cap silently discarded older job history with no indication it happened. Added a `logging.warning()` so the operator can see in the server logs when records are being dropped, rather than discovering missing history unexpectedly.

---

#### [7] `SRC/summarizer.py` — Transcript truncation at sentence boundary

**Lines affected:** 41–45 (original) → 41–49 (updated)

**Original:**
```python
# Trim if very long (Claude handles ~200k tokens but we keep costs manageable)
max_chars = 80_000
if len(transcript) > max_chars:
    log.warning(f"Transcript truncated from {len(transcript)} to {max_chars} chars for summarization.")
    transcript = transcript[:max_chars] + "\n\n[... transcript truncated for length ...]"
```

**Fixed:**
```python
# Trim if very long (Claude handles ~200k tokens but we keep costs manageable)
max_chars = 80_000
if len(transcript) > max_chars:
    # Break at the last sentence boundary to avoid cutting mid-sentence
    cut = transcript[:max_chars]
    last_boundary = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "), cut.rfind("\n"))
    if last_boundary > max_chars // 2:
        cut = cut[:last_boundary + 1]
    log.warning(f"Transcript truncated from {len(transcript)} to {len(cut)} chars for summarization.")
    transcript = cut + "\n\n[... transcript truncated for length ...]"
```

**Why:** The original cut at exactly 80,000 characters regardless of where that landed — often mid-word or mid-sentence, which could confuse Claude's summarization and produce broken output. The fix searches backward from the cut point for the last sentence-ending character (`. `, `? `, `! `, or newline). The `> max_chars // 2` guard prevents an edge case where no boundary is found in the first half of the text, which would cause the cut to collapse to nearly zero.

---

#### [8] `SRC/transcriber.py` — Whisper model configurable via environment variable

**Lines affected:** 42–43 (original) → 42–44 (updated)

**Original:**
```python
log.info(f"    Loading Whisper model for: {path.name}")
model = whisper.load_model("base")  # options: tiny, base, small, medium, large
```

**Fixed:**
```python
whisper_model = os.environ.get("WHISPER_MODEL", "base")
log.info(f"    Loading Whisper '{whisper_model}' model for: {path.name}")
model = whisper.load_model(whisper_model)  # options: tiny, base, small, medium, large
```

**Why:** The model size was hardcoded to `"base"` with no way to change it without editing source code. Auditors with better hardware may want `"small"` or `"medium"` for improved accuracy; those on slower machines may prefer `"tiny"`. Now the model is read from the `WHISPER_MODEL` environment variable (settable in `config.env`), defaulting to `"base"` if not set — no code changes needed to switch models.

---
