"""
OCR wrapper.

Uses pytesseract for the MVP (zero-config, already ships with most Linux
boxes / easy `brew install tesseract` on Mac / installer on Windows).
The deck calls for PaddleOCR mobile — swap it in here later if you need
better accuracy on stylized text; keep the return format the same
(list of dicts with text + bbox) and nothing downstream has to change.
"""
import pytesseract
import numpy as np
import cv2
from dataclasses import dataclass

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

@dataclass
class TextBox:
    text: str
    bbox: tuple  # (x, y, w, h)
    confidence: float


def extract_text(image_bgr: np.ndarray, min_confidence: float = 40.0) -> list[TextBox]:
    """Full-page OCR — good for body text/paragraphs, but page-segmentation
    tends to drop small isolated labels (e.g. a 2-letter button like 'GO')
    since there's little surrounding context. Use extract_text_in_box for
    those instead."""
    data = pytesseract.image_to_data(image_bgr, output_type=pytesseract.Output.DICT)

    results: list[TextBox] = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not text or conf < min_confidence:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        results.append(TextBox(text=text, bbox=(x, y, w, h), confidence=conf))
    return results


def extract_text_in_box(image_bgr: np.ndarray, bbox: tuple, upscale: int = 4) -> str:
    """Targeted OCR on a single detected element's crop. Small, isolated
    labels (button text, input placeholders) read far more reliably this
    way than via full-page OCR, since we can upscale + use single-line
    page segmentation (psm 7) tuned for exactly this kind of text."""
    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return ""
    crop = image_bgr[y:y + h, x:x + w]
    if crop.size == 0:
        return ""
    big = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    text = pytesseract.image_to_string(big, config="--psm 7").strip()
    return text
