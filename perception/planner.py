"""
Planner — MVP version.

Given the semantic map (from the perception pipeline) and a plain-English
goal, picks exactly one next action: click something, or type into
something. No ML here — keyword matching against element labels. It's
deliberately simple: swap this module for an LLM-based planner later
(same input/output shape) without touching perception or the extension.

Supported goal phrasing:
  "click <description>"          -> click the best-matching interactable element
  "type '<text>' into <field>"   -> type <text> into the best-matching input
  anything else                  -> treated like a click target description
"""
import re
from dataclasses import dataclass


@dataclass
class Action:
    action: str            # "click" | "type" | "none"
    element_id: int | None
    text: str | None
    reason: str


STOPWORDS = {"the", "a", "an", "in", "on", "into", "to", "click", "type",
             "press", "tap", "button", "field", "box", "please"}


def _tokenize(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOPWORDS]


def _score(tokens: list[str], label: str) -> int:
    if not label:
        return 0
    label_tokens = _tokenize(label)
    return sum(1 for t in tokens if t in label_tokens)


def _best_match(candidates: list[dict], tokens: list[str]) -> dict | None:
    if not tokens or not candidates:
        return None
    scored = [(_score(tokens, c.get("label") or ""), c) for c in candidates]
    scored = [(s, c) for s, c in scored if s > 0]
    if not scored:
        return None
    scored.sort(key=lambda pair: -pair[0])
    return scored[0][1]


def plan(elements: list[dict], goal: str) -> Action:
    goal_lower = goal.lower().strip()

    # "type '<text>' into <field description>"
    m = re.search(r"type\s+['\"]?(.+?)['\"]?\s+(?:into|in|on)\s+(.+)", goal_lower)
    if m:
        text_to_type, field_desc = m.group(1), m.group(2)
        tokens = _tokenize(field_desc)
        candidates = [e for e in elements if e.get("interactable") and e.get("type") == "input"]
        best = _best_match(candidates, tokens)
        if best:
            return Action("type", best["id"], text_to_type,
                           f"Typing into element labeled '{best.get('label')}'")
        return Action("none", None, None, "No matching input field found for that goal")

    # default: whole goal describes what to click
    tokens = _tokenize(goal_lower)
    candidates = [e for e in elements if e.get("interactable")]
    best = _best_match(candidates, tokens)
    if best:
        return Action("click", best["id"], None,
                       f"Clicking element labeled '{best.get('label')}'")
    return Action("none", None, None, "No matching interactable element found for that goal")