// CivicGuide front-end — vanilla ES modules, zero build step.

// `crypto.randomUUID()` only works in a secure context (HTTPS or localhost).
// We fall back to a Math.random-based generator so the app stays usable when
// served over plain HTTP on a LAN IP (e.g. 0.0.0.0:8080) during development.
function newSessionId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  // RFC4122-style v4-ish fallback. Not cryptographically strong, but good
  // enough for a chat session id used only on the client.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const SESSION_ID = (() => {
  const k = "civicguide.session";
  try {
    let v = localStorage.getItem(k);
    if (!v) {
      v = newSessionId();
      localStorage.setItem(k, v);
    }
    return v;
  } catch {
    // localStorage may throw in private mode / sandboxed iframes.
    return newSessionId();
  }
})();

const $ = (sel) => document.querySelector(sel);

const els = {
  messages: $("#messages"),
  composer: $("#composer"),
  prompt: $("#prompt"),
  location: $("#location"),
  sendBtn: $("#send-btn"),
  locale: $("#locale"),
  resetBtn: $("#reset-btn"),
  pollingForm: $("#polling-form"),
  pollingAddr: $("#polling-addr"),
  pollingResults: $("#polling-results"),
  videoForm: $("#video-form"),
  videoTopic: $("#video-topic"),
  videoResults: $("#video-results"),
  reminderForm: $("#reminder-form"),
  reminderTitle: $("#reminder-title"),
  reminderWhen: $("#reminder-when"),
  reminderLoc: $("#reminder-loc"),
};

// Tiny markdown → safe HTML (links, bold, italics, lists). Avoids importing a
// 50 KB dependency just for chat formatting.
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function renderMarkdown(text) {
  const safe = escapeHtml(text);
  return safe
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/_([^_]+)_/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
}

function appendMessage(role, text, { meta } = {}) {
  const li = document.createElement("li");
  li.className = `msg ${role}`;
  li.innerHTML = renderMarkdown(text);
  if (meta) {
    const m = document.createElement("span");
    m.className = "meta";
    m.textContent = meta;
    li.appendChild(m);
  }
  els.messages.appendChild(li);
  els.messages.scrollTop = els.messages.scrollHeight;
  return li;
}

function setBusy(b) {
  els.messages.setAttribute("aria-busy", String(b));
  els.sendBtn.disabled = b;
  // Update label so screen readers announce the state change.
  els.sendBtn.setAttribute("aria-label", b ? "Sending… please wait" : "Send message");
}

// Keep `<html lang>` synced with the chosen locale so screen readers
// pronounce content correctly. Fires on initial load and every change.
function syncDocumentLang() {
  const lang = els.locale.value || "en";
  document.documentElement.setAttribute("lang", lang);
}
els.locale.addEventListener("change", syncDocumentLang);
syncDocumentLang();

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const ct = r.headers.get("content-type") || "";
  if (!r.ok) {
    let msg = r.statusText;
    if (ct.includes("application/json")) {
      const j = await r.json().catch(() => ({}));
      msg = j.detail || j.error || msg;
    }
    throw new Error(msg);
  }
  return ct.includes("application/json") ? r.json() : r.blob();
}

// ---------------- Chat ----------------

els.composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = els.prompt.value.trim();
  if (!text) return;

  appendMessage("user", text);
  els.prompt.value = "";
  setBusy(true);

  const placeholder = appendMessage("bot", "");
  placeholder.classList.add("typing");

  try {
    const data = await postJSON("/api/chat", {
      message: text,
      session_id: SESSION_ID,
      locale: els.locale.value,
      location: els.location.value || null,
    });
    placeholder.classList.remove("typing");
    placeholder.innerHTML = renderMarkdown(data.reply);

    const tools = (data.tools_used || []).map((t) => t.name).join(", ");
    const meta = [
      tools && `tools: ${tools}`,
      data.safety_filtered && "filtered for non-partisanship",
      (data.citations || []).length && data.citations.join(" · "),
    ]
      .filter(Boolean)
      .join(" — ");
    if (meta) {
      const m = document.createElement("span");
      m.className = "meta";
      m.textContent = meta;
      placeholder.appendChild(m);
    }
  } catch (err) {
    placeholder.classList.remove("typing");
    placeholder.innerHTML = renderMarkdown(`⚠️ Sorry — ${err.message}`);
  } finally {
    setBusy(false);
  }
});

els.prompt.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    els.composer.requestSubmit();
  }
});

els.resetBtn.addEventListener("click", () => {
  els.messages.innerHTML = "";
  greet();
});

// ---------------- Polling places ----------------

els.pollingForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const addr = els.pollingAddr.value.trim();
  if (!addr) return;
  els.pollingResults.innerHTML = "<li>Searching…</li>";
  try {
    const data = await postJSON("/api/polling-places", { address: addr, radius_m: 5000 });
    els.pollingResults.innerHTML = "";
    if (!data.results.length) {
      els.pollingResults.innerHTML = "<li>No candidates found. Try a more specific address.</li>";
      return;
    }
    for (const p of data.results.slice(0, 6)) {
      const li = document.createElement("li");
      const dist = p.distance_m ? ` (${(p.distance_m / 1000).toFixed(1)} km)` : "";
      const link = p.map_url ? ` · <a href="${p.map_url}" target="_blank" rel="noopener noreferrer">map</a>` : "";
      li.innerHTML = `<strong>${escapeHtml(p.name)}</strong>${dist}${link}<br><small>${escapeHtml(p.address)}</small>`;
      els.pollingResults.appendChild(li);
    }
  } catch (err) {
    els.pollingResults.innerHTML = `<li>⚠️ ${escapeHtml(err.message)}</li>`;
  }
});

// ---------------- Videos ----------------

els.videoForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const topic = els.videoTopic.value.trim();
  if (!topic) return;
  els.videoResults.innerHTML = "<li>Searching…</li>";
  try {
    const data = await postJSON("/api/videos", {
      topic,
      locale: els.locale.value,
      max_results: 5,
    });
    els.videoResults.innerHTML = "";
    if (!data.items.length) {
      els.videoResults.innerHTML = "<li>No videos found.</li>";
      return;
    }
    for (const v of data.items) {
      const li = document.createElement("li");
      li.innerHTML = `<a href="${v.url}" target="_blank" rel="noopener noreferrer">${escapeHtml(v.title)}</a><br><small>${escapeHtml(v.channel)}</small>`;
      els.videoResults.appendChild(li);
    }
  } catch (err) {
    els.videoResults.innerHTML = `<li>⚠️ ${escapeHtml(err.message)}</li>`;
  }
});

// ---------------- Reminder ICS ----------------

els.reminderForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    title: els.reminderTitle.value.trim(),
    description: "Election milestone reminder created via CivicGuide.",
    start: new Date(els.reminderWhen.value).toISOString(),
    duration_minutes: 60,
    location: els.reminderLoc.value || null,
  };
  try {
    const blob = await postJSON("/api/reminder.ics", body);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "election-reminder.ics";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Couldn't generate reminder: ${err.message}`);
  }
});

// ---------------- Greeting ----------------

function greet() {
  appendMessage(
    "bot",
    `**Welcome to CivicGuide.** I can explain how elections work — eligibility, voter registration, polling timings, ID requirements, the role of the Election Commission, and what happens after voting.\n\nTry asking:\n- *How do I register as a first-time voter?*\n- *What ID can I bring to the polling station?*\n- *Find polling-style venues near MG Road, Bengaluru.*\n- *Show me explainer videos on EVM and VVPAT.*`
  );
}
greet();
