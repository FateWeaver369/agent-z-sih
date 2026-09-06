const captureBtn = document.getElementById("captureBtn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const goalSection = document.getElementById("goalSection");
const goalInput = document.getElementById("goalInput");
const executeBtn = document.getElementById("executeBtn");

let currentElements = [];
let currentTabId = null;

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.className = isError ? "error" : "";
}

function renderResults(elements) {
  resultsEl.innerHTML = "";
  if (!elements.length) {
    resultsEl.textContent = "No elements detected.";
    return;
  }
  for (const el of elements) {
    const row = document.createElement("div");
    row.className = "el" + (el.interactable ? " interactable" : "");
    if (el.redacted) row.style.borderLeftColor = "#dc2626";
    row.innerHTML = `<span class="type">${el.redacted ? "🔒 " + el.type : el.type}</span><span class="label">${el.label ?? "(no text)"}</span>`;
    resultsEl.appendChild(row);
  }
}

captureBtn.addEventListener("click", async () => {
  captureBtn.disabled = true;
  setStatus("Capturing tab + running perception pipeline...");
  resultsEl.innerHTML = "";

  chrome.runtime.sendMessage({ type: "CAPTURE_AND_ANALYZE" }, async (response) => {
    captureBtn.disabled = false;

    if (chrome.runtime.lastError) {
      setStatus(`Extension error: ${chrome.runtime.lastError.message}`, true);
      return;
    }
    if (!response || !response.ok) {
      const err = response?.error || "Unknown error";
      setStatus(
        err.includes("Failed to fetch")
          ? "Couldn't reach the local API — is `uvicorn api:app --port 8765` running?"
          : `Error: ${err}`,
        true
      );
      return;
    }

    const { elements, count, tabId } = response.result;
    setStatus(`Found ${count} elements.`);
    renderResults(elements);

    currentElements = elements;
    currentTabId = tabId;
    goalSection.style.display = "block";

    // Draw boxes directly on the page for a live visual check, mirroring
    // the annotated.png the CLI produces.
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        func: drawOverlay,
        args: [elements],
      });
    } catch (e) {
      // Some pages (chrome://, the Web Store, etc.) block script injection —
      // the JSON results above still work fine even if the overlay can't.
      console.warn("Overlay injection skipped:", e);
    }
  });
});

executeBtn.addEventListener("click", () => {
  const goal = goalInput.value.trim();
  if (!goal) return;
  if (!currentElements.length || currentTabId == null) {
    setStatus("Capture & analyze the page first.", true);
    return;
  }

  executeBtn.disabled = true;
  setStatus("Planning...");

  chrome.runtime.sendMessage(
    { type: "PLAN", elements: currentElements, goal },
    async (response) => {
      executeBtn.disabled = false;

      if (chrome.runtime.lastError || !response || !response.ok) {
        const err = response?.error || chrome.runtime.lastError?.message || "Unknown error";
        setStatus(`Plan error: ${err}`, true);
        return;
      }

      const action = response.result;
      setStatus(`${action.action.toUpperCase()}: ${action.reason}`);

      if (action.action === "none") return;

      const target = currentElements.find((e) => e.id === action.element_id);
      if (!target) {
        setStatus("Planner picked an element that's no longer available — try re-capturing.", true);
        return;
      }

      try {
        await chrome.scripting.executeScript({
          target: { tabId: currentTabId },
          func: executeOnPage,
          args: [action.action, target.center, action.text],
        });
      } catch (e) {
        setStatus(`Couldn't act on the page: ${e.message}`, true);
      }
    }
  );
});

// Injected into the page — draws colored boxes + labels over detected
// elements. Runs in the page's context, so it can't reference anything
// from this file's scope directly (hence it's passed via executeScript's
// `func`, not called normally).
//
// Coordinates from the perception pipeline are in screenshot pixels,
// which chrome.tabs.captureVisibleTab captures at devicePixelRatio scale
// (e.g. 1.25x on a 125%-scaled Windows display). CSS positioning expects
// plain CSS pixels, so we divide by devicePixelRatio here to convert back.
function drawOverlay(elements) {
  document.getElementById("__agentz_overlay__")?.remove();
  const dpr = window.devicePixelRatio || 1;

  const layer = document.createElement("div");
  layer.id = "__agentz_overlay__";
  layer.style.cssText =
    "position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483647;";
  document.body.appendChild(layer);

  const colors = {
    button: "#2563eb",
    input: "#10b981",
    container: "#94a3b8",
    text: "#ea580c",
    unknown: "#64748b",
  };

  for (const el of elements) {
    const [x, y, w, h] = el.bbox;
    const box = document.createElement("div");

    if (el.redacted) {
      // Solid black fill + a small "PII" tag — visually distinct from
      // ordinary detections, since this is the privacy-preserving part
      // of the pipeline and should be obvious at a glance in a demo.
      box.style.cssText = `position:absolute;left:${x / dpr}px;top:${y / dpr}px;width:${w / dpr}px;height:${h / dpr}px;background:#000;border:2px solid #dc2626;box-sizing:border-box;display:flex;align-items:center;justify-content:center;`;
      const tag = document.createElement("span");
      tag.textContent = "PII";
      tag.style.cssText = "color:#f87171;font:bold 10px sans-serif;";
      box.appendChild(tag);
    } else {
      box.style.cssText = `position:absolute;left:${x / dpr}px;top:${y / dpr}px;width:${w / dpr}px;height:${h / dpr}px;border:2px solid ${
        colors[el.type] || "#000"
      };box-sizing:border-box;`;
    }
    layer.appendChild(box);
  }

  // auto-remove after 6s so it doesn't clutter the page during a demo
  setTimeout(() => layer.remove(), 6000);
}

// Injected into the page to actually perform the planner's chosen action.
// Same devicePixelRatio conversion as drawOverlay — this is the fix for
// clicks landing on the wrong spot (or nothing) on any display that
// isn't at 100% scaling.
function executeOnPage(actionType, center, text) {
  const dpr = window.devicePixelRatio || 1;
  const [rawX, rawY] = center;
  const x = rawX / dpr;
  const y = rawY / dpr;

  const el = document.elementFromPoint(x, y);
  if (!el) {
    console.warn("Agent Z: no element found at", x, y);
    return;
  }

  if (actionType === "click") {
    el.click();
    return;
  }

  if (actionType === "type") {
    el.focus();
    if ("value" in el) {
      // Native setter bypass so frameworks (React etc.) that override the
      // value property still see the change and fire their own handlers.
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )?.set;
      if (nativeSetter) {
        nativeSetter.call(el, text);
      } else {
        el.value = text;
      }
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    } else {
      el.textContent = text;
    }
  }
}