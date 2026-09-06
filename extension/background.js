/**
 * Background service worker.
 *
 * Runs the actual capture + API call here (not in the popup or a content
 * script) because:
 *  - chrome.tabs.captureVisibleTab is only available to the extension's
 *    own contexts, not content scripts.
 *  - fetch() to localhost from here isn't restricted by the target page's
 *    Content-Security-Policy the way a content-script fetch would be.
 */

const API_URL = "http://127.0.0.1:8765/parse";
const PLAN_URL = "http://127.0.0.1:8765/plan";

async function captureAndAnalyze() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) throw new Error("No active tab found");

  // Screenshot of exactly what's visible in the viewport right now.
  const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });

  const blob = await (await fetch(dataUrl)).blob();
  const form = new FormData();
  form.append("image", blob, "screenshot.png");

  const res = await fetch(API_URL, { method: "POST", body: form });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  const data = await res.json();
  return { ...data, tabId: tab.id, imageDataUrl: dataUrl };
}

async function planAction(elements, goal) {
  const res = await fetch(PLAN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ elements, goal }),
  });
  if (!res.ok) {
    throw new Error(`Plan API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "CAPTURE_AND_ANALYZE") {
    captureAndAnalyze()
      .then((result) => sendResponse({ ok: true, result }))
      .catch((err) => sendResponse({ ok: false, error: String(err.message || err) }));
    return true; // keep the message channel open for the async response
  }
  if (message.type === "PLAN") {
    planAction(message.elements, message.goal)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((err) => sendResponse({ ok: false, error: String(err.message || err) }));
    return true;
  }
});