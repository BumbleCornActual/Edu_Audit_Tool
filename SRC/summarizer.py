"""
Summarizer
Uses the Anthropic Claude API to generate structured summaries of education audit transcripts.
"""

import os
import logging
import anthropic

log = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are an expert education auditor assistant. You will receive a transcript from an education audit, meeting, or document review. Your job is to produce a clear, structured summary for the auditor's records.

Format your summary exactly as follows:

## Overview
[2-3 sentences describing the main purpose and context of this document/meeting]

## Key Topics Discussed
- [Bullet point list of main topics]

## Action Items / Recommendations
- [Any follow-up actions, recommendations, or next steps mentioned]

## Participants (if identifiable)
- [Names, roles if mentioned — otherwise write "Not identified"]

## Notable Quotes or Statements
- [Any significant verbatim statements worth highlighting]

## Concerns or Red Flags
- [Anything that may require follow-up, escalation, or legal review]

Be factual, neutral, and concise. Use education/special education terminology where appropriate."""


def summarize_transcript(transcript: str, source_name: str = "") -> str:
    """Send transcript to Claude and return a structured summary."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Trim if very long (Claude handles ~200k tokens but we keep costs manageable)
    max_chars = 80_000
    if len(transcript) > max_chars:
        log.warning(f"Transcript truncated from {len(transcript)} to {max_chars} chars for summarization.")
        transcript = transcript[:max_chars] + "\n\n[... transcript truncated for length ...]"

    user_message = f"Source: {source_name}\n\n---TRANSCRIPT START---\n{transcript}\n---TRANSCRIPT END---"

    log.info("    Sending to Claude for summarization...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text.strip()
