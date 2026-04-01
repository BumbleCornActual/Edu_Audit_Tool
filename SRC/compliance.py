"""
Compliance Checker
Scans transcripts for education law keywords, regulatory terms, and red-flag phrases.
Returns a list of flagged findings with context.
"""

import re
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

# ── Default keyword sets ──────────────────────────────────────────────────────

# Regulatory / legal terms that should be noted in any audit record
REGULATORY_KEYWORDS = [
    "IDEA", "Individuals with Disabilities Education Act",
    "IEP", "Individualized Education Program",
    "Section 504", "504 plan",
    "FERPA", "Family Educational Rights and Privacy Act",
    "ADA", "Americans with Disabilities Act",
    "LRE", "least restrictive environment",
    "FAPE", "free appropriate public education",
    "due process",
    "prior written notice",
    "parent consent", "parental consent",
    "evaluation", "re-evaluation", "triennial",
    "eligibility determination",
    "placement decision",
    "transition plan", "transition services",
    "behavior intervention plan", "BIP",
    "functional behavior assessment", "FBA",
    "manifestation determination",
    "suspension", "expulsion",
    "extended school year", "ESY",
    "related services",
    "special education services",
]

# Phrases that may indicate procedural violations or concerns
RED_FLAG_PHRASES = [
    "we can't do that",
    "we don't have to",
    "that's not our responsibility",
    "not eligible",
    "denied",
    "refused",
    "won't provide",
    "can't afford",
    "no funding",
    "budget",
    "waiting list",
    "didn't notify",
    "no notice",
    "didn't send",
    "without consent",
    "without permission",
    "override the parent",
    "parent doesn't need to",
]


@dataclass
class ComplianceFlag:
    category: str        # "regulatory" | "red_flag" | "custom"
    keyword: str         # the matched keyword or phrase
    context: str         # surrounding sentence(s)
    line_number: int


def flag_compliance_issues(transcript: str, keywords: list[str] = None) -> list[dict]:
    """
    Scan transcript for compliance-relevant terms and red-flag phrases.
    Returns a list of flag dicts sorted by line number.
    """
    all_keywords = {k.lower(): "regulatory" for k in REGULATORY_KEYWORDS}
    all_keywords.update({k.lower(): "red_flag" for k in RED_FLAG_PHRASES})

    if keywords:
        all_keywords.update({k.lower(): "custom" for k in keywords})

    lines = transcript.split("\n")
    flags: list[ComplianceFlag] = []

    # Pre-compile word-boundary patterns to avoid false positives
    # e.g. "idea" should not match "ideal", "ada" should not match "adequate"
    compiled = {kw: re.compile(r'\b' + re.escape(kw) + r'\b') for kw in all_keywords}

    for line_num, line in enumerate(lines, start=1):
        line_lower = line.lower()
        for keyword, category in all_keywords.items():
            if compiled[keyword].search(line_lower):
                # Build context window (prev line + current + next line)
                prev_line = lines[line_num - 2] if line_num > 1 else ""
                next_line = lines[line_num] if line_num < len(lines) else ""
                context = " ".join(filter(None, [prev_line.strip(), line.strip(), next_line.strip()]))

                flags.append(ComplianceFlag(
                    category=category,
                    keyword=keyword,
                    context=context[:300],   # cap context length
                    line_number=line_num,
                ))
                break   # one flag per line — avoid duplicate hits

    # Deduplicate by (keyword, line_number)
    seen = set()
    unique_flags = []
    for f in flags:
        key = (f.keyword, f.line_number)
        if key not in seen:
            seen.add(key)
            unique_flags.append(f)

    log.info(f"    Compliance scan: {len(unique_flags)} flag(s) found")

    return [
        {
            "category": f.category,
            "keyword": f.keyword,
            "context": f.context,
            "line_number": f.line_number,
        }
        for f in sorted(unique_flags, key=lambda x: x.line_number)
    ]
