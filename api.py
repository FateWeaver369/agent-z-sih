"""
Local HTTP bridge for the perception pipeline.

The Chrome extension runs in JS and can't call Python directly. This
exposes the pipeline as a tiny local server the extension hits over
localhost instead of dealing with native messaging (much faster to get
working under hackathon time pressure).

Run it:
    uvicorn api:app --reload --port 8765

Then from the extension:
    const form = new FormData();
    form.append("image", screenshotBlob, "screenshot.png");
    const res = await fetch("http://127.0.0.1:8765/parse", { method: "POST", body: form });
    const semanticMap = await res.json();
"""
import cv2
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from perception.detector import detect_elements
from perception.ocr import extract_text
from perception.semantic_map import build_semantic_map
from perception.planner import plan as plan_action

app = FastAPI(title="Agent Z Perception API")

# Chrome extensions call this from a chrome-extension:// origin, not
# http(s)://, so a normal CORS allowlist doesn't fit neatly — wide open
# is fine here since this only ever listens on localhost for a hackathon
# demo. Tighten this (specific extension origin) before shipping anything
# beyond that.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/parse")
async def parse_screenshot(image: UploadFile = File(...)):
    raw = await image.read()
    arr = np.frombuffer(raw, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    if image_bgr is None:
        return {"error": "Could not decode image"}

    elements = detect_elements(image_bgr)
    text_boxes = extract_text(image_bgr)
    semantic_map = build_semantic_map(elements, text_boxes, image_bgr)

    return {"elements": semantic_map, "count": len(semantic_map)}


class PlanRequest(BaseModel):
    elements: list[dict]
    goal: str


@app.post("/plan")
def plan(req: PlanRequest):
    action = plan_action(req.elements, req.goal)
    return {
        "action": action.action,
        "element_id": action.element_id,
        "text": action.text,
        "reason": action.reason,
    }