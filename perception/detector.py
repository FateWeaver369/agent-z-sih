"""
Lightweight, model-free UI element detector.

For the hackathon MVP this uses classic OpenCV (edges + contours) to find
rectangular regions that look like buttons / input fields / cards. It's
fast, needs no training data or GPU, and is good enough to bootstrap the
semantic map. Swap this module out later for a trained detector (YOLO-nano)
or Microsoft's OmniParser icon-detection model without touching the rest
of the pipeline — it just needs to keep returning the same box format.
"""
from dataclasses import dataclass, field
import cv2
import numpy as np


@dataclass
class ElementBox:
    bbox: tuple  # (x, y, w, h)
    kind: str = "unknown"  # rough guess: "button", "input", "container"
    meta: dict = field(default_factory=dict)


def _classify_box(w: int, h: int, filled: bool) -> str:
    """Rough heuristic classification based on shape + whether the box
    interior is a saturated/solid fill color (typical of a button) versus
    a near-white/gray interior (typical of an input field or plain card)."""
    aspect = w / max(h, 1)
    if h < 60 and 0.8 <= aspect <= 6:
        return "button" if filled else "input"
    if w > 200 and h > 80:
        return "container"
    return "unknown"


def _edge_density(edges: np.ndarray, x: int, y: int, w: int, h: int) -> float:
    """Fraction of edge pixels inside the box. Clean UI elements (buttons,
    inputs) have edges mostly along their border and text; photos/banners
    are edge-dense everywhere inside — this is what lets us tell a real
    button apart from a random patch of a product photo."""
    roi = edges[y:y + h, x:x + w]
    if roi.size == 0:
        return 1.0
    return float(np.count_nonzero(roi)) / roi.size


def detect_elements(image_bgr: np.ndarray, min_area: int = 600,
                     max_edge_density: float = 0.35,
                     density_check_min_area: int = 4000) -> list[ElementBox]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    boxes: list[ElementBox] = []
    img_h, img_w = image_bgr.shape[:2]

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < min_area:
            continue
        # skip boxes that basically cover the whole page (background/page frame)

        if w > 0.98 * img_w and h > 0.98 * img_h:
            continue

        # skip photo/banner-like regions: high internal edge density means
        # busy visual content (product photos, textures), not a clean UI
        # control. Only applied above density_check_min_area — a SMALL
        # box's border+text naturally eats a much bigger share of its own
        # area than a large box's does, so applying this to small boxes
        # was killing real small buttons (e.g. thin-outline "Follow" /
        # "Sign in" pill buttons) — a more common, more damaging miss than
        # the photo noise this was meant to catch. min_area above already
        # drops true micro-noise specks.
        if area >= density_check_min_area and _edge_density(edges, x, y, w, h) > max_edge_density:
            continue

        # "filled vs outline" check: a solid-color button reads as a
        # saturated or dark/colorful median pixel in HSV; a plain input
        # field or card interior is near-white/gray (low saturation, high
        # value). This is far more reliable than raw pixel variance, which
        # gets thrown off by white text sitting on a colored button.
        roi = image_bgr[y:y + h, x:x + w]
        if roi.size == 0:
            continue
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        med_h, med_s, med_v = np.median(hsv_roi.reshape(-1, 3), axis=0)
        filled = med_s > 40 or med_v < 100

        kind = _classify_box(w, h, filled)
        boxes.append(ElementBox(bbox=(x, y, w, h), kind=kind))

    # de-duplicate near-identical/nested boxes (keep the smaller, tighter one)
    boxes = _dedupe(boxes)
    return boxes


def _dedupe(boxes: list[ElementBox], iou_thresh: float = 0.7) -> list[ElementBox]:
    def iou(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ix1, iy1 = max(ax, bx), max(ay, by)
        ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        union = aw * ah + bw * bh - inter
        return inter / union if union else 0

    boxes = sorted(boxes, key=lambda b: b.bbox[2] * b.bbox[3])
    kept: list[ElementBox] = []
    for b in boxes:
        if not any(iou(b.bbox, k.bbox) > iou_thresh for k in kept):
            kept.append(b)
    return kept