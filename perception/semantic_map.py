"""
Fuses element boxes (from detector.py) with text boxes (from ocr.py) into
one structured "semantic map" — the JSON representation of the page that
the planner will act on.

Output format (matches the shape sketched in the SIH deck):
[
  {
    "id": 0,
    "type": "input",
    "label": "Search",
    "bbox": [x, y, w, h],
    "center": [cx, cy],
    "interactable": true
  },
  ...
]
"""
import numpy as np
from .detector import ElementBox
from .ocr import TextBox, extract_text_in_box
from .redaction import classify_pii


def _center(bbox):
    x, y, w, h = bbox
    return [x + w // 2, y + h // 2]


def _overlaps(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw < bx or bx + bw < ax or ay + ah < by or by + bh < ay)


def _text_inside(element_bbox, text_boxes: list[TextBox]) -> str:
    """Collects OCR text whose box overlaps the element box, in reading order."""
    matches = [t for t in text_boxes if _overlaps(element_bbox, t.bbox)]
    matches.sort(key=lambda t: (t.bbox[1], t.bbox[0]))
    return " ".join(t.text for t in matches).strip()


INTERACTABLE_KINDS = {"button", "input"}


def _apply_redaction(label: str | None) -> tuple[str | None, bool]:
    """Checks a label against PII patterns. Returns (possibly-scrubbed
    label, redacted flag). Scrubbing happens here — the JSON payload
    itself must not carry the raw PII forward, not just the image."""
    category = classify_pii(label)
    if category:
        return f"[REDACTED-{category.upper()}]", True
    return label, False


def build_semantic_map(elements: list[ElementBox], text_boxes: list[TextBox],
                        image_bgr: np.ndarray | None = None) -> list[dict]:
    used_text = set()
    semantic_map = []

    for i, el in enumerate(elements):
        # Try the cheap option first: full-page OCR already ran once for
        # the whole image, so check for an overlapping match there before
        # paying for a separate per-box OCR call. Only fall back to the
        # slow, targeted per-box OCR (a separate tesseract subprocess call
        # each time) for the small/isolated labels that full-page OCR
        # tends to miss (e.g. a lone "GO"). This is what made real pages
        # with 100+ detected boxes slow — every button/input was paying
        # for its own OCR subprocess regardless of whether it needed one.
        label = _text_inside(el.bbox, text_boxes)
        if not label and image_bgr is not None and el.kind in ("button", "input"):
            label = extract_text_in_box(image_bgr, el.bbox)
        label, redacted = _apply_redaction(label)
        semantic_map.append({
            "id": i,
            "type": el.kind,
            "label": label if label else None,
            "bbox": list(el.bbox),
            "center": _center(el.bbox),
            "interactable": el.kind in INTERACTABLE_KINDS,
            "redacted": redacted,
        })
        for t in text_boxes:
            if _overlaps(el.bbox, t.bbox):
                used_text.add(id(t))

    # Any leftover text not claimed by a detected element becomes its own
    # "text" node (headings, labels, plain content) so nothing is lost.
    next_id = len(elements)
    for t in text_boxes:
        if id(t) in used_text:
            continue
        label, redacted = _apply_redaction(t.text)
        semantic_map.append({
            "id": next_id,
            "type": "text",
            "label": label,
            "bbox": list(t.bbox),
            "center": _center(t.bbox),
            "interactable": False,
            "redacted": redacted,
        })
        next_id += 1

    return semantic_map