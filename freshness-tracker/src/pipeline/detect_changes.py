"""
detect_changes.py — compare successive snapshots and produce change_events rows.

Comparison covers:
  From raw_snapshots  : content_hash, page_title
  From extracted_fields: email, phone, opening_hours, fee_text

Severity rules:
  high   : phone, opening_hours, fee_text
  medium : email
  low    : page_title, content_hash
"""

from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Severity map
# ──────────────────────────────────────────────────────────────────────────────

FIELD_SEVERITY: dict[str, str] = {
    "phone":         "high",
    "opening_hours": "high",
    "fee_text":      "high",
    "email":         "medium",
    "page_title":    "low",
    "content_hash":  "low",
}

# Fields from raw_snapshots vs extracted_fields — used only to know where to read
# them from; comparison logic is the same for both.
RAW_FIELDS       = ("content_hash", "page_title")
EXTRACTED_FIELDS = ("email", "phone", "opening_hours", "fee_text")
ALL_FIELDS       = RAW_FIELDS + EXTRACTED_FIELDS


# ──────────────────────────────────────────────────────────────────────────────
# Core comparison
# ──────────────────────────────────────────────────────────────────────────────

def _change_type(old: Optional[str], new: Optional[str]) -> str:
    """Classify the kind of change between two string values."""
    if old is None and new is not None:
        return "value_added"
    if old is not None and new is None:
        return "value_removed"
    return "value_changed"


def compare_snapshots(
    prev: dict,
    curr: dict,
) -> list[dict]:
    """
    Compare two snapshot dicts and return a list of change_event dicts.

    Each dict in *prev* and *curr* must contain:
      snapshot_id, source_id,
      content_hash, page_title,                  (from raw_snapshots)
      email, phone, opening_hours, fee_text       (from extracted_fields; None if missing)

    Returns a list of dicts ready for INSERT into change_events
    (without detected_at, which is set by the caller).
    """
    events = []

    for field in ALL_FIELDS:
        old_val = prev.get(field)
        new_val = curr.get(field)

        # Normalise to None for empty strings so we don't flag "" vs None
        if old_val == "":
            old_val = None
        if new_val == "":
            new_val = None

        if old_val == new_val:
            continue  # no change

        events.append({
            "source_id":             curr["source_id"],
            "previous_snapshot_id":  prev["snapshot_id"],
            "current_snapshot_id":   curr["snapshot_id"],
            "field_name":            field,
            "old_value":             str(old_val) if old_val is not None else None,
            "new_value":             str(new_val) if new_val is not None else None,
            "change_type":           _change_type(old_val, new_val),
            "severity":              FIELD_SEVERITY[field],
        })

    return events
