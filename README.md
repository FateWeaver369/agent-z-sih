# Agent Z — Perception Pipeline (Step 1 of SIH-26171)

This is the first buildable piece of Agent Z: take a page screenshot and
turn it into a structured JSON "semantic map" of UI elements (buttons,
inputs, text) with bounding boxes and labels — the thing the planner will
later act on.

```
screenshot  --->  detector.py (OpenCV)  --+
                                           +--> semantic_map.py --> JSON
screenshot  --->  ocr.py (pytesseract)  --+
```

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You also need the Tesseract OCR binary itself (pytesseract is just a
wrapper around it):
- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`
- Windows: installer at https://github.com/UB-Mannheim/tesseract/wiki

## Run it

A synthetic test page is included so you can try it immediately without a
real browser capture:

```bash
python samples/make_sample.py          # regenerate the test image (optional)
python main.py --image samples/sample_page.png --output output/map.json --annotated output/annotated.png
```

- `output/map.json` — the semantic map (what the planner will consume)
- `output/annotated.png` — the same image with detected boxes/labels drawn
  on top, so you can eyeball whether detection is working

To run it on a real screenshot, just point `--image` at any `.png`/`.jpg`.

## Output format

```json
[
  {
    "id": 20,
    "type": "button",
    "label": "GO",
    "bbox": [420, 100, 80, 40],
    "center": [460, 120],
    "interactable": true
  }
]
```

## What's solid vs. what's a known shortcut right now

**Works well:**
- Distinguishing filled buttons from outline/plain inputs (via HSV
  saturation/value of the box interior, not raw pixel variance — that was
  the first thing I had to fix, since white text on a colored button
  fools a naive variance check)
- Reading small, isolated labels like "GO" or "Search" — full-page OCR
  drops these (tesseract's page-segmentation ignores tiny isolated text
  blocks), so each detected button/input is cropped and OCR'd on its own
  at 4x upscale with single-line mode. This is the fix that made GO/Search/
  Sign Up/Cancel all read correctly.

**Known shortcut — the detector will over-detect on plain text:**
The OpenCV contour detector finds *any* rectangular edge, so headings and
paragraph text get picked up as spurious "button"/"input" boxes alongside
real UI elements (see the annotated image — header words get boxed too).
It's noisy but harmless: the planner only needs to care about elements
where `interactable: true`, and the real buttons/inputs are correctly
identified among the noise. If you want cleaner output before the demo,
the fix is a real detector, not more heuristic tuning — see below.

## Run the local API (for the Chrome extension to call)

```bash
uvicorn api:app --reload --port 8765
```

Test it's up: open http://127.0.0.1:8765/health in a browser — should show
`{"status":"ok"}`.

The extension will POST a screenshot to `/parse` as multipart form data
(field name `image`) and get back JSON: `{"elements": [...], "count": N}`
— same shape as `output/map.json`, just wrapped with a count. CORS is wide
open (`allow_origins=["*"]`) so a `chrome-extension://` origin can call it
without fuss — fine for a hackathon demo on localhost, tighten it to the
specific extension origin before anything more permanent.

## Chrome extension

Lives in `extension/`. Captures whatever tab is currently active, sends it
to the local API above, and shows you what was detected — both as a list
in the popup and as colored boxes drawn directly on the page for a few
seconds.

**Load it:**
1. Make sure the API is running first: `uvicorn api:app --reload --port 8765`
2. Open `chrome://extensions` in Chrome
3. Turn on **Developer mode** (top-right toggle)
4. Click **Load unpacked** and select the `extension/` folder
5. The Agent Z icon appears in your toolbar (you may need to click the
   puzzle-piece icon and pin it)

**Use it:**
1. Go to any real webpage
2. Click the Agent Z toolbar icon
3. Click **Capture & Analyze Page**
4. The popup lists detected elements; the page itself briefly shows
   colored boxes over them (blue = button, green = input, gray = container/text)

If the popup says it can't reach the API, the `uvicorn` server isn't
running — start it and try again. Extension pages (`chrome://...`) and the
Chrome Web Store block script injection by policy, so the box-overlay step
will silently skip on those — the JSON list in the popup still works fine.

## Next steps (in order)

1. ~~FastAPI bridge~~ — done (`api.py`)
2. ~~Chrome extension~~ — done (`extension/`) — captures, calls the API,
   shows results + overlay
3. **Planner**: consumes the semantic map, picks the next click/type/scroll
   action given a goal — separate module, doesn't touch this pipeline.
   The extension would need a small addition to actually *execute* an
   action (e.g. `chrome.scripting.executeScript` to click a coordinate or
   fill an input) — not built yet, this just perceives right now.
4. **Better detector** (post-presentation): swap `detector.py`'s OpenCV
   heuristic for [Microsoft OmniParser](https://github.com/microsoft/OmniParser)
   or a small trained model once there's time to do it properly — the
   current heuristic has a real ceiling (see below) that's fine for a demo
   but not for arbitrary real pages.

## Add to the SIH deck's tech stack

Worth listing alongside what's already there:
- **FastAPI + Uvicorn** — local inference server bridging the extension and the Python perception code
- **Microsoft OmniParser** (or similar) — pretrained UI-element detector, likely faster to a working detector than training one from scratch
