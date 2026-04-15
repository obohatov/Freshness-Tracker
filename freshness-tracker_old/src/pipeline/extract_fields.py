"""
extract_fields.py — extract structured fields from raw page text.

All extraction is regex-based, deterministic, and requires no external APIs.
"""

import json
import re
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Patterns
# ──────────────────────────────────────────────────────────────────────────────

_RE_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

_RE_PHONE = re.compile(
    r"(?<!\d)"                          # not preceded by a digit
    r"(\+32|0032|0)"                    # Belgian prefix
    r"[\s.\-/]?"
    r"(\d{1,2})"
    r"[\s.\-/]?"
    r"(\d{2,3})"
    r"[\s.\-/]?"
    r"(\d{2,3})"
    r"(?:[\s.\-/]?\d{2})?"             # optional last group
    r"(?!\d)",                          # not followed by a digit
)

_HOURS_KEYWORDS = re.compile(
    r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|maandag|dinsdag|woensdag|donderdag|vrijdag|zaterdag|zondag"
    r"|ouvert|open|gesloten|ferm[eé]|horaire|opening.?hour"
    r"|h\s*[-–]\s*\d|uur|\d+[hH]\d*)\b",
    re.IGNORECASE,
)

_FEE_KEYWORDS = re.compile(
    r"\b(tarif|tariff|prix|price|co[uû]t|frais|fee|tax|€|\beur\b|gratuit|free"
    r"|betaling|gratis|kosten|prijs)\b",
    re.IGNORECASE,
)

_RE_PDF = re.compile(
    r"https?://[^\s\"'<>]+\.pdf(?:\?[^\s\"'<>]*)?",
    re.IGNORECASE,
)

_SNIPPET_WINDOW = 300   # characters around a keyword match for snippets


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _snippet_around(text: str, pattern: re.Pattern, window: int = _SNIPPET_WINDOW) -> Optional[str]:
    """Return a text snippet centred on the first match of pattern, or None."""
    m = pattern.search(text)
    if not m:
        return None
    start = max(0, m.start() - window // 2)
    end   = min(len(text), m.end() + window // 2)
    snippet = text[start:end].strip()
    # Trim to sentence / line boundaries where possible
    snippet = re.sub(r"^\S+\s", "", snippet)   # drop partial leading word
    return snippet[:500]                        # hard cap


# ──────────────────────────────────────────────────────────────────────────────
# Extractors
# ──────────────────────────────────────────────────────────────────────────────

def extract_email(text: str) -> Optional[str]:
    m = _RE_EMAIL.search(text)
    return m.group(0).lower() if m else None


def extract_phone(text: str) -> Optional[str]:
    m = _RE_PHONE.search(text)
    return m.group(0).strip() if m else None


def extract_opening_hours(text: str) -> Optional[str]:
    return _snippet_around(text, _HOURS_KEYWORDS)


def extract_fee_text(text: str) -> Optional[str]:
    return _snippet_around(text, _FEE_KEYWORDS)


def extract_pdf_links(text: str) -> list:
    return list(dict.fromkeys(_RE_PDF.findall(text)))   # deduplicated, order preserved


def extract_all(raw_text: str) -> dict:
    """
    Run all extractors against raw_text.
    Returns a dict matching the extracted_fields column names.
    """
    if not raw_text or raw_text.startswith("ERROR:"):
        return {
            "email":               None,
            "phone":               None,
            "opening_hours":       None,
            "fee_text":            None,
            "pdf_links_json":      json.dumps([]),
            "important_links_json": json.dumps([]),
        }

    return {
        "email":               extract_email(raw_text),
        "phone":               extract_phone(raw_text),
        "opening_hours":       extract_opening_hours(raw_text),
        "fee_text":            extract_fee_text(raw_text),
        "pdf_links_json":      json.dumps(extract_pdf_links(raw_text)),
        "important_links_json": json.dumps([]),   # requires HTML — not available from raw_text alone
    }
