"""
Agent Z — perception pipeline entry point.

Usage:
    python main.py --image samples/sample_page.png --output output/map.json

This is step 1 of the SIH-26171 pipeline:
    screenshot -> detect elements -> OCR -> semantic map (this script)
    semantic map -> planner -> action                    (next step)

The planner/action step is intentionally separate: it consumes the JSON
this script produces, so you can develop/test them independently.
"""
import argparse
import json
import cv2

from perception.detector import detect_elements
from perception.ocr import extract_text
from perception.semantic_map import build_semantic_map
from perception.redaction import redact_image, classify_pii


COLORS = {
    "button": (37, 99, 235),
    "input": (16, 185, 129),
    "container": (148, 163, 184),
    "text": (234, 88, 12),
    "unknown": (100, 100, 100),
}


def annotate(image_bgr, semantic_map, out_path):
    img = image_bgr.copy()
    for el in semantic_map:
        x, y, w, h = el["bbox"]
        color = COLORS.get(el["type"], (0, 0, 0))
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        label = f'{el["type"]}:{el["label"]}' if el["label"] else el["type"]
        cv2.putText(img, label[:30], (x, max(y - 6, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    cv2.imwrite(out_path, img)


def run(image_path: str, output_path: str, annotated_path: str | None,
        redacted_path: str | None = None):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")

    elements = detect_elements(image_bgr)
    text_boxes = extract_text(image_bgr)
    semantic_map = build_semantic_map(elements, text_boxes, image_bgr)

    with open(output_path, "w") as f:
        json.dump(semantic_map, f, indent=2)
    print(f"Wrote semantic map ({len(semantic_map)} elements) -> {output_path}")

    if annotated_path:
        annotate(image_bgr, semantic_map, annotated_path)
        print(f"Wrote annotated debug image -> {annotated_path}")

    if redacted_path:
        # Redact using the raw OCR boxes, not the (heuristic, sometimes
        # fragmented) UI-detector element boxes — a text token can get
        # split across overlapping element boxes, which under-covers the
        # actual sensitive text. The OCR box is where the text actually
        # was, so it's the correct region to black out regardless of how
        # the element detector chunked things.
        sensitive_boxes = [t.bbox for t in text_boxes if classify_pii(t.text)]
        redacted_img = redact_image(image_bgr, sensitive_boxes)
        cv2.imwrite(redacted_path, redacted_img)
        print(f"Wrote redacted image ({len(sensitive_boxes)} regions blacked out) -> {redacted_path}")

    return semantic_map


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Z perception pipeline")
    parser.add_argument("--image", required=True, help="Path to screenshot/page image")
    parser.add_argument("--output", default="output/map.json", help="Path to write semantic map JSON")
    parser.add_argument("--annotated", default="output/annotated.png", help="Path to write debug overlay image")
    parser.add_argument("--redacted", default="output/redacted.png", help="Path to write PII-redacted image")
    args = parser.parse_args()

    run(args.image, args.output, args.annotated, args.redacted)