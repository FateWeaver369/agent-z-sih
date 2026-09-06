"""
PII detection + redaction — the privacy-preserving piece the SIH problem
statement (26171) explicitly scores on: "recall/precision for detection
of sensitive/PII data" (20%) and "precision of redaction" (20%).

Scope for this MVP: catches PII that appears as a SINGLE OCR token (no
internal whitespace) — emails, continuous-digit phone numbers, PAN,
Aadhaar-style numbers, card-style numbers. A phone number typed with
spaces ("987 654 3210") will OCR as multiple separate tokens and won't
be caught by this version — that needs line-level token merging before
pattern matching, a reasonable next step, not done here.
"""
import re
import cv2
import numpy as np

# Ordered so more specific patterns are tried before generic digit-length
# fallbacks (a PAN's digit portion alone shouldn't be caught by "card").
PII_PATTERNS = [
    ("email", re.compile(r"^[\w.+-]+@[\w-]+\.[A-Za-z]{2,}$")),
    ("pan", re.compile(r"^[A-Za-z]{5}\d{4}[A-Za-z]$")),
    ("phone", re.compile(r"^(\+?91[-\s]?)?[6-9]\d{9}$")),
    ("aadhaar", re.compile(r"^\d{12}$")),
    ("card", re.compile(r"^\d{13,19}$")),
]


def classify_pii(text: str | None) -> str | None:
    """Returns a category name ('email', 'phone', ...) if the text looks
    like PII, else None. Matching is done on the token with internal
    spaces/dashes stripped, so "987-654-3210" as a single OCR token still
    matches even though the raw text has separators."""
    if not text:
        return None
    compact = text.strip().replace(" ", "").replace("-", "")
    if not compact:
        return None
    for name, pattern in PII_PATTERNS:
        if pattern.match(compact):
            return name
    return None


def redact_image(image_bgr: np.ndarray, boxes: list[tuple], pad: int = 2) -> np.ndarray:
    """Returns a COPY of image_bgr with each given (x, y, w, h) box
    blacked out. Never mutates the original — callers that need the
    original for anything else (debug overlays, etc.) still can."""
    redacted = image_bgr.copy()
    for (x, y, w, h) in boxes:
        x0, y0 = max(x - pad, 0), max(y - pad, 0)
        x1, y1 = x + w + pad, y + h + pad
        cv2.rectangle(redacted, (x0, y0), (x1, y1), (0, 0, 0), -1)
    return redacted