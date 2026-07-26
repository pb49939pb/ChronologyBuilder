import "./pdfjs-polyfills.mjs";
import * as pdfjsLib from "./pdfjs/pdf.min.mjs";

// workerSrc is consumed by a `new Worker(url)` call inside pdf.js, and relative URLs passed to
// the Worker constructor resolve against the page's URL, NOT against this module's URL the way a
// real `import` statement would — so a plain relative string here resolves incorrectly (the page
// is served at "/", but this file lives at "/static/pdfjs/..."). Resolving explicitly against
// this module's own URL sidesteps that mismatch regardless of what path the page is served from.
// Points at the polyfill wrapper (not pdf.worker.min.mjs directly) so the worker's own execution
// context also gets the URL.parse polyfill before the real worker script runs.
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL("./pdfjs/pdf.worker.polyfill.mjs", import.meta.url).href;

const form = document.getElementById("upload-form");
const statusEl = document.getElementById("status");
const statusText = document.getElementById("status-text");
const progressFill = document.getElementById("progress-fill");
const fileLog = document.getElementById("file-log");
const resultsEl = document.getElementById("results");
const warningsEl = document.getElementById("warnings");
const batchProgressBanner = document.getElementById("batch-progress-banner");
const statsEl = document.getElementById("stats");
const findingsListEl = document.getElementById("findings-list");
const factsPanel = document.getElementById("facts-panel");
const factsTabsEl = document.getElementById("facts-tabs");
const factsListEl = document.getElementById("facts-list");
const submitBtn = document.getElementById("submit-btn");
const reviewProgressEl = document.getElementById("review-progress");
const exportBtn = document.getElementById("export-btn");
const caseRescanRow = document.getElementById("case-rescan-row");
const reviewRescanBtn = document.getElementById("review-rescan-btn");
const reviewRescanMessage = document.getElementById("review-rescan-message");

const viewerTitle = document.getElementById("viewer-title");
const viewerPageInfo = document.getElementById("viewer-page-info");
const viewerHint = document.getElementById("viewer-hint");
const viewerBatesCheck = document.getElementById("viewer-bates-check");
const canvas = document.getElementById("pdf-canvas");
const ctx = canvas.getContext("2d");
const viewerCanvasWrap = document.getElementById("viewer-canvas-wrap");
const highlightLayer = document.getElementById("highlight-layer");
const textLayerDiv = document.getElementById("text-layer");
const approveBtn = document.getElementById("approve-btn");
const rejectBtn = document.getElementById("reject-btn");
const previewChronologyBtn = document.getElementById("preview-chronology-btn");
const chronologyPreviewEl = document.getElementById("chronology-preview");
const chronologyPreviewModal = document.getElementById("chronology-preview-modal");
const chronologyPreviewClose = document.getElementById("chronology-preview-close");
const exportConfirmModal = document.getElementById("export-confirm-modal");
const exportConfirmMessage = document.getElementById("export-confirm-message");
const exportConfirmCancel = document.getElementById("export-confirm-cancel");
const exportConfirmProceed = document.getElementById("export-confirm-proceed");

// Categorized atomic facts (populated by the model — see RESPONSE_SCHEMA/prompt in the backend)
// shown as clickable tabs above the timeline/viewer. Clicking one adds it to the reviewed output
// (auto-approved, since clicking is an explicit reviewer action) if an equivalent finding isn't
// already present, or points at the existing one if it is. Declared up here, before the
// restore-cached-result block below runs renderResults() synchronously at page-load time — a
// `const` declared further down the file is in the temporal dead zone until execution reaches it,
// so referencing it from a function invoked this early would throw.
const FACTS_CATEGORIES = [
  { key: "medications", label: "Medications" },
  { key: "procedures", label: "Procedures" },
  { key: "diagnoses", label: "Diagnoses" },
  { key: "labs", label: "Labs" },
];

// Same reason this lives up here, not next to realValue()/normalize() further down where it reads
// more naturally: parseDateForSort() (used by the Timeline date-sort, which the cached-result
// restore path below can trigger synchronously at page-load time) references it too.
const PLACEHOLDER_VALUES = new Set([
  "", "not stated", "not applicable", "n/a", "na", "none", "unknown", "not specified", "not given",
]);

let currentSessionId = null;
let currentPdfDoc = null;
let currentFilename = null;
let currentOcrFiles = new Set(); // filenames read via OCR fallback — no text layer for pdf.js to search
let renderToken = 0; // guards against out-of-order async renders when switching finding quickly
// Case-level metadata (plaintiff/defendant/DOL/facts/patient demographics/source filenames) — only
// present when this result came from Case Mode's primary (plaintiff) group; null for a plain
// single-upload session or a secondary "also mentions" group. Used by buildExportPayload() to fill
// in the export template's header block; the export gracefully falls back to blank placeholders
// (matching the blank template itself) when this is null.
let currentCaseMeta = null;
// filename -> short content-derived label (e.g. "record_01.pdf" -> "FairviewOpReport"), computed
// server-side (see _resolve_record_sources in app.py) and unique within this result. Used anywhere
// a source citation is displayed, in place of the raw filename — a real production's filenames
// aren't always meaningful, and the label is guaranteed unique while a filename alone might not be
// distinctive at a glance.
let currentRecordSourceLabels = {};

// Review state — kept in the browser only (sessionStorage), not sent to the server.
// findingsById: id -> { section, text, date, sourceFile, quote, sourceFiles, quotes }
// findingStatus: id -> "approved" | "rejected" (absence = not yet reviewed)
let findingsById = {};
let orderedFindingIds = [];
let findingStatus = {};
let currentFindingId = null;
let editingFindingId = null; // set while a finding's text is being edited inline
let currentRawFindings = null; // the server's findings object for the active session, kept so the
                                // Key Facts panel can re-render the main list after adding a fact
let activeFactsTab = null;

const LAST_RESULT_KEY = "lawfirmagent_last_result";
const reviewKey = (sessionId) => `lawfirmagent_review_${sessionId}`;
const editsKey = (sessionId) => `lawfirmagent_edits_${sessionId}`;
const addedFactsKey = (sessionId) => `lawfirmagent_addedfacts_${sessionId}`;
const summaryEditKey = (sessionId) => `lawfirmagent_summary_edit_${sessionId}`;

function saveLastResult(data) {
  try {
    sessionStorage.setItem(LAST_RESULT_KEY, JSON.stringify(data));
  } catch {
    // sessionStorage can throw if full/unavailable — non-fatal, just means no refresh-resilience
  }
}

function loadLastResult() {
  try {
    const raw = sessionStorage.getItem(LAST_RESULT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveReviewStatus() {
  if (!currentSessionId) return;
  try {
    sessionStorage.setItem(reviewKey(currentSessionId), JSON.stringify(findingStatus));
  } catch {
    // non-fatal
  }
}

function loadReviewStatus(sessionId) {
  try {
    const raw = sessionStorage.getItem(reviewKey(sessionId));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveFindingEdits() {
  if (!currentSessionId) return;
  const edits = {};
  for (const id of orderedFindingIds) {
    if (findingsById[id]?.edited) edits[id] = findingsById[id].text;
  }
  try {
    sessionStorage.setItem(editsKey(currentSessionId), JSON.stringify(edits));
  } catch {
    // non-fatal
  }
}

function loadFindingEdits(sessionId) {
  try {
    const raw = sessionStorage.getItem(editsKey(sessionId));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

// The AI-drafted summary at the bottom of the timeline gets the same click-to-edit treatment as
// individual findings (see startEditingFinding) and the same survives-a-refresh persistence as
// everything else reviewed here — a paralegal correcting a finding's wording but leaving the
// overall summary untouched (or vice versa) is a completely normal thing to want to do.
function saveSummaryEdit(text) {
  if (!currentSessionId) return;
  try {
    sessionStorage.setItem(summaryEditKey(currentSessionId), text);
  } catch {
    // non-fatal
  }
  durablePost("/summary_edit", { text });
}

function loadSummaryEdit(sessionId) {
  try {
    return sessionStorage.getItem(summaryEditKey(sessionId));
  } catch {
    return null;
  }
}

// Facts added via the Key Facts panel aren't part of the server's analysis response, so they get
// their own sessionStorage slot (same survives-a-refresh pattern as review status/edits) — a list
// of {id, text, date, sourceFile, quote} objects, re-injected as a "Key Facts" section every time
// renderFindings runs.
function saveAddedFacts(facts) {
  if (!currentSessionId) return;
  try {
    sessionStorage.setItem(addedFactsKey(currentSessionId), JSON.stringify(facts));
  } catch {
    // non-fatal
  }
}

function loadAddedFacts(sessionId) {
  try {
    const raw = sessionStorage.getItem(addedFactsKey(sessionId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

// If this page was opened from the Start a New Case status page (a link like
// /?case=<job_id>&group=<key>), load that specific case group's already-generated chronology
// instead of the upload form / whatever was last cached in this browser tab — reuses the exact
// same rendering/highlighting/review code as a normal single-analysis result, just fetched from
// the case job's stored results rather than a live streamed /analyze response.
const urlParams = new URLSearchParams(window.location.search);
const caseJobId = urlParams.get("case");
const caseGroupKey = urlParams.get("group");

// Durable, server-side backstop for reviewer state (Case Mode only — see db.py's review_actions/
// added_facts tables). sessionStorage stays the synchronous source of truth for all rendering
// everywhere in this file; these are fire-and-forget writes alongside it, not a replacement — if
// one fails (offline, server hiccup), the reviewer's session keeps working exactly as it already
// does today, it just won't survive as long as it otherwise would.
function durablePost(path, body) {
  if (!caseJobId || !caseGroupKey) return;
  fetch(`/case/${encodeURIComponent(caseJobId)}/${encodeURIComponent(caseGroupKey)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => {
    // non-fatal — sessionStorage already has this reviewer's decision either way
  });
}

function durableDelete(path) {
  if (!caseJobId || !caseGroupKey) return;
  fetch(`/case/${encodeURIComponent(caseJobId)}/${encodeURIComponent(caseGroupKey)}${path}`, {
    method: "DELETE",
  }).catch(() => {
    // non-fatal
  });
}

if (caseJobId && caseGroupKey) {
  // The plain single-zip-upload form makes no sense here — this page is showing a specific Case
  // Mode group's results, not waiting for a manual upload, and the form's own submit handler
  // below would only confuse things if it were still visible/usable alongside a live case.
  form.style.display = "none";

  // A large, multi-chunk case can take a long time to fully finish (see the Case Mode feature) —
  // rather than show nothing until it's completely done, this polls the same results endpoint the
  // case status page uses and re-renders as soon as more findings are available, so there's a
  // real, growing chronology to start reviewing immediately instead of a blank wait.
  let lastFindingCount = -1;
  let renderedFinal = false; // once the "done" result has been rendered once, never skip a later
                              // poll's render just because of a stale count comparison again
  let pollTimer = null;

  // "Check for new files" (incremental reprocessing, see POST /case/<job_id>/rescan) lives here —
  // on the actual chronology-builder page a reviewer is working from — not just on the separate
  // /case status page, which isn't part of the normal day-to-day reviewing workflow.
  //
  // There's no server-side folder path to silently re-scan anymore (see /case/start's upload-based
  // redesign) — checking for new files means re-picking the same folder via the native OS folder
  // picker so the browser can re-enumerate its CURRENT contents, then uploading that; the backend
  // diffs it against what it's already processed and reprocesses only genuinely new files.
  caseRescanRow.style.display = "flex";
  const reviewRescanFolderInput = document.getElementById("review-rescan-folder-input");
  reviewRescanBtn.addEventListener("click", () => {
    reviewRescanFolderInput.value = ""; // ensures "change" fires even if the same folder is re-picked
    reviewRescanFolderInput.onchange = async () => {
      if (!reviewRescanFolderInput.files.length) return; // picker was cancelled
      reviewRescanBtn.disabled = true;
      reviewRescanBtn.textContent = "Checking for new files…";
      try {
        const body = new FormData();
        Array.from(reviewRescanFolderInput.files).forEach((file) => {
          body.append("files", file, file.webkitRelativePath || file.name);
        });
        const resp = await fetch(`/case/${encodeURIComponent(caseJobId)}/rescan`, { method: "POST", body });
        const data = await resp.json();
        if (!resp.ok) {
          reviewRescanMessage.textContent = data.error || "Couldn't start checking for new files.";
          reviewRescanBtn.disabled = false;
          reviewRescanBtn.textContent = "Check for new files";
          return;
        }
        // The GROUP's own status (unlike the job's overall status) genuinely goes back to
        // "processing" while a rescan runs on it (see _run_case_rescan in app.py), so the existing
        // poll loop's isDone check already handles this correctly once it's running again — it
        // just needs restarting, since it already stopped once this group first reached "done".
        // The interval is established UNCONDITIONALLY here (not left to fetchAndRenderCaseResult's
        // own conditional scheduling) because the very first poll right after starting a rescan
        // can still race the background thread and see a stale "done" status — the exact same race
        // already found and fixed server-side for the initial case-creation flow (see
        // verify_case_group_not_yet_created.py) — which would otherwise skip scheduling anything.
        renderedFinal = false;
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(fetchAndRenderCaseResult, 4000);
        fetchAndRenderCaseResult();
      } catch {
        reviewRescanMessage.textContent = "Couldn't reach the server to check for new files.";
        reviewRescanBtn.disabled = false;
        reviewRescanBtn.textContent = "Check for new files";
      }
    };
    reviewRescanFolderInput.click();
  });

  const countFindings = (findings) => {
    if (!findings) return 0;
    return ["timeline", "medications", "procedures", "diagnoses", "labs", "potential_issues", "discrepancies"]
      .reduce((sum, key) => sum + (findings[key] ? findings[key].length : 0), 0);
  };

  // Pre-seeds sessionStorage from durably-stored reviewer state (see db.py's review_actions/
  // added_facts tables, returned by /results as review_state/added_facts) — but ONLY for a
  // genuinely fresh tab that has nothing of its own yet (checked via the reviewKey slot
  // specifically, as a stand-in for "has this tab ever rendered this session before"). This is
  // the actual "come back a month later" scenario: reopening a case's review link in a browser
  // that never itself reviewed it gets the real, previously-reviewed state back instead of a blank
  // unreviewed chronology. Never overwrites a tab's own in-progress review.
  function preSeedDurableStateIfFresh(sessionId, data) {
    if (sessionStorage.getItem(reviewKey(sessionId)) !== null) return;

    const reviewState = data.review_state || {};
    const statusSeed = {};
    const editsSeed = {};
    let summarySeed = null;
    for (const [findingId, entry] of Object.entries(reviewState)) {
      if (entry.kind === "summary") {
        if (entry.edited_text) summarySeed = entry.edited_text;
        continue;
      }
      if (entry.status) statusSeed[findingId] = entry.status;
      if (entry.edited_text) editsSeed[findingId] = entry.edited_text;
    }
    try {
      sessionStorage.setItem(reviewKey(sessionId), JSON.stringify(statusSeed));
      sessionStorage.setItem(editsKey(sessionId), JSON.stringify(editsSeed));
      if (summarySeed != null) sessionStorage.setItem(summaryEditKey(sessionId), summarySeed);
      if (data.added_facts && data.added_facts.length) {
        sessionStorage.setItem(addedFactsKey(sessionId), JSON.stringify(data.added_facts));
      }
    } catch {
      // non-fatal — just means this tab won't have the durable state pre-loaded
    }
  }

  const fetchAndRenderCaseResult = () => {
    fetch(`/case/${encodeURIComponent(caseJobId)}/${encodeURIComponent(caseGroupKey)}/results`)
      .then((r) => r.json())
      .then((data) => {
        if (!data.ready) {
          if (data.error) return; // unknown job/group (real error) — nothing sensible to show, just stop
          // Nothing at all yet (still reading documents, or still on the very first chunk) —
          // reuse the same "in progress" UI the live-upload flow uses, and keep polling.
          statusEl.style.display = "block";
          resultsEl.style.display = "none";
          statusText.textContent = data.progress_text || "Waiting for the first pass to complete…";
          progressFill.classList.add("busy");
          if (!pollTimer) pollTimer = setInterval(fetchAndRenderCaseResult, 4000);
          return;
        }

        const currentCount = countFindings(data.findings);
        const isDone = data.status === "done";
        // A genuine bug found via testing: mid-generation polls only ever GROW in count (chunks
        // append), but the final "done" result runs Bates resolution + duplicate-record merging
        // (see _resolve_bates/_dedupe_all_with_multi_source in app.py) AFTER every chunk is
        // already merged — dedup can legitimately REDUCE the total count from what the last
        // partial poll showed. A plain `currentCount > lastFindingCount` check then silently
        // skips rendering the final result forever (a tab left open while the job finishes never
        // updates — Bates numbers/dedup never appear, only a page refresh would show them, since
        // that resets this state and fetches fresh). `isDone` must always force at least one
        // final render, regardless of how the count compares to the last partial snapshot.
        if (!renderedFinal && (currentCount !== lastFindingCount || isDone)) {
          // timeline/potential_issues/discrepancies ids are now content-stable (server-computed
          // finding_id, see _assign_finding_ids in app.py) rather than array position, so a
          // previously-approved item's id and saved status correctly survive dedup/reordering here.
          const previouslySelected = currentFindingId;
          try {
            preSeedDurableStateIfFresh(data.session_id, data);
            renderResults(data);
            if (previouslySelected && findingsById[previouslySelected]) {
              selectFinding(previouslySelected);
            }
            lastFindingCount = currentCount; // only commit once rendering actually succeeded —
            if (isDone) renderedFinal = true; // see comment below on why this order matters
            saveLastResult(data);
          } catch (err) {
            // A bug here must not silently disappear into the outer .catch() below (which exists
            // only for genuine fetch/network failures) — that swallowed a real bug during testing
            // (lastFindingCount had already been bumped before render threw, so every later poll
            // saw "nothing new" and stopped retrying forever, even though nothing had ever
            // rendered at all). Logging it explicitly, and deliberately NOT updating
            // lastFindingCount/renderedFinal above until render succeeds, means a transient render
            // failure gets retried on the next poll instead of being silently stuck forever.
            console.error("Failed to render incoming case result:", err);
          }
        }

        if (isDone) {
          batchProgressBanner.style.display = "none";
          if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        } else {
          batchProgressBanner.style.display = "flex";
          batchProgressBanner.innerHTML = '<span class="spinner-dot"></span> This chronology is ' +
            "still being generated" + (data.progress_text ? ` — ${escapeHtml(data.progress_text)}` : "") +
            ". It updates automatically here — feel free to start reviewing what's already below.";
          if (!pollTimer) pollTimer = setInterval(fetchAndRenderCaseResult, 4000);
        }

        // Reflects rescan_status/rescan_message (see POST /case/<job_id>/rescan) regardless of
        // whether THIS tab is the one that triggered it — a rescan started from the /case status
        // page, or from a different tab, still shows up here on the next poll.
        if (data.rescan_status === "processing") {
          reviewRescanBtn.disabled = true;
          reviewRescanBtn.textContent = "Checking for new files…";
          reviewRescanMessage.textContent = "";
        } else {
          reviewRescanBtn.disabled = false;
          reviewRescanBtn.textContent = "Check for new files";
          reviewRescanMessage.textContent = data.rescan_message || "";
        }
      })
      .catch(() => {
        // transient network hiccup — keep polling rather than giving up
      });
  };

  fetchAndRenderCaseResult();
} else {
  // Restore the last analysis automatically if the page gets refreshed mid-review.
  const cachedResult = loadLastResult();
  if (cachedResult) {
    renderResults(cachedResult, { fromCache: true });
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById("zipfile");
  if (!fileInput.files.length) return;

  const detailLevels = ["brief", "standard", "detailed"];
  const detailLevel = detailLevels[Number(document.getElementById("detail-slider").value)] || "standard";

  const formData = new FormData();
  formData.append("zipfile", fileInput.files[0]);
  formData.append("detail_level", detailLevel);

  submitBtn.disabled = true;
  resultsEl.style.display = "none";
  statusEl.style.display = "block";
  progressFill.style.width = "0%";
  progressFill.classList.remove("busy");
  fileLog.innerHTML = "";
  statusText.textContent = "Uploading...";

  try {
    const resp = await fetch("/analyze", { method: "POST", body: formData });

    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      statusText.textContent = "Error: " + (data.error || resp.statusText);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.trim()) continue;
        handleEvent(JSON.parse(line));
      }
    }
  } catch (err) {
    statusText.textContent = "Request failed: " + err;
  } finally {
    submitBtn.disabled = false;
  }
});

function handleEvent(event) {
  switch (event.stage) {
    case "start":
      currentSessionId = event.session_id;
      statusText.textContent = `Extracting 0 of ${event.total_files} PDFs...`;
      break;

    case "extract": {
      const pct = Math.round((event.index / event.total) * 100);
      progressFill.style.width = pct + "%";
      statusText.textContent = `Extracting ${event.index} of ${event.total} PDFs...`;
      const line = document.createElement("div");
      line.textContent = event.ok
        ? `✓ ${event.filename} (${event.pages} page${event.pages === 1 ? "" : "s"})`
        : `⚠ ${event.filename} — no extractable text, skipped`;
      if (!event.ok) line.classList.add("skip");
      fileLog.appendChild(line);
      fileLog.scrollTop = fileLog.scrollHeight;
      break;
    }

    case "extract_done":
      statusText.textContent =
        `Extraction complete — ${event.documents_processed} document(s), ${event.total_pages} page(s). ` +
        `Sending to the model...`;
      progressFill.style.width = "100%";
      progressFill.classList.add("busy");
      break;

    case "generating":
      statusText.textContent =
        `Model is generating the chronology... ${event.tokens_so_far} tokens so far (${event.elapsed}s elapsed)`;
      break;

    case "error":
      progressFill.classList.remove("busy");
      statusText.textContent = "Error: " + event.message;
      if (event.warnings && event.warnings.length) {
        event.warnings.forEach((w) => {
          const line = document.createElement("div");
          line.textContent = w;
          line.classList.add("skip");
          fileLog.appendChild(line);
        });
      }
      break;

    case "done":
      progressFill.classList.remove("busy");
      saveLastResult(event);
      renderResults(event);
      break;
  }
}

function renderResults(data, { fromCache = false } = {}) {
  statusEl.style.display = "none";
  resultsEl.style.display = "block";
  currentSessionId = data.session_id;
  currentOcrFiles = new Set(data.ocr_files || []);
  currentCaseMeta = data.case || null;
  currentRecordSourceLabels = data.record_source_labels || {};

  // A batch result being shown while still generating (see the polling loop below) legitimately
  // has no final stats yet — they're only computed once every chunk finishes — so this must not
  // assume `data.stats` is always a complete object. Confirmed as a real crash during testing, not
  // a hypothetical: rendering a genuine partial result threw here every time before this guard.
  const s = data.stats;
  statsEl.textContent = s
    ? `Documents analyzed: ${s.documents_processed} | Pages: ${s.total_pages} | ` +
      `Time: ${s.wall_time_seconds}s | Speed: ${s.tokens_per_second ?? "—"} tok/s | Model: ${s.model} | ` +
      `Detail: ${s.detail_level ?? "standard"}` +
      (s.input_truncated ? " | ⚠ input truncated to fit context window" : "") +
      (fromCache ? " | (restored after page refresh)" : "")
    : "Still generating — final stats (pages, timing, tokens/sec) will appear once complete.";

  warningsEl.innerHTML = "";
  if (data.warnings && data.warnings.length) {
    const h = document.createElement("h3");
    h.textContent = "Warnings";
    warningsEl.appendChild(h);
    const ul = document.createElement("ul");
    data.warnings.forEach((w) => {
      const li = document.createElement("li");
      li.textContent = w;
      ul.appendChild(li);
    });
    warningsEl.appendChild(ul);
  }

  findingStatus = loadReviewStatus(currentSessionId);
  const savedEdits = loadFindingEdits(currentSessionId);
  currentRawFindings = data.findings || {};
  activeFactsTab = null;
  renderFindings(currentRawFindings, savedEdits);
  renderFactsPanel();
  updateReviewProgress();

  // Reset viewer state for the new session
  currentPdfDoc = null;
  currentFilename = null;
  currentFindingId = null;
  viewerTitle.textContent = "No document loaded";
  viewerPageInfo.textContent = "";
  viewerHint.textContent = "Click a finding on the left to jump to its source.";
  approveBtn.disabled = true;
  rejectBtn.disabled = true;
  clearCanvas();
}

// Best-effort date-string -> sortable-number parser, used to keep the Timeline (both on screen and
// in the export) in true chronological order — earliest first — rather than whatever order the
// model happened to emit entries in (usually close to chronological since that's literally its
// task, but not guaranteed, and definitely not guaranteed across merged chunks in a large case).
// Unparseable/placeholder dates ("not stated", empty) sort to the END rather than being guessed at
// or left to collide at the top — same "omit rather than guess" spirit as the rest of this app.
function parseDateForSort(dateStr) {
  if (!dateStr) return Infinity;
  const s = String(dateStr).trim();
  if (!s || PLACEHOLDER_VALUES.has(s.toLowerCase())) return Infinity;
  // A day-range within a slash-date (e.g. "03/04-06, 2026", "03/04-11, 2026" — seen in real model
  // output for entries spanning several days) isn't parseable by Date.parse as-is; take just the
  // first day of the range, which is what matters for chronological ORDER (this entry starts then).
  const rangeMatch = s.match(/^(\d{1,2})\/(\d{1,2})-\d{1,2},?\s*(\d{4})$/);
  if (rangeMatch) {
    const [, mo, day, yr] = rangeMatch;
    const t = Date.parse(`${mo}/${day}/${yr}`);
    if (!isNaN(t)) return t;
  }
  const t = Date.parse(s);
  return isNaN(t) ? Infinity : t;
}

// Sorts a dated-entry array into ascending chronological order WITHOUT disturbing item identity —
// pairs each item with its ORIGINAL array index before sorting and returns a lookup back to it, so
// a caller that keys ids by array position (see the `section` helper's default `idFor` below) can
// still use the item's original position rather than its new sorted position. This matters for the
// live-updating batch/case results poll: a later poll can append a new, EARLIER-dated entry mid-
// stream, and re-sorting by position alone would silently reassign an already-reviewed item's id
// (and therefore its saved approve/reject/edit state) onto a different entry.
function sortDatedItemsStably(items) {
  const withIndex = items.map((item, origIndex) => ({ item, origIndex }));
  withIndex.sort((a, b) => parseDateForSort(a.item.date) - parseDateForSort(b.item.date));
  return {
    sorted: withIndex.map(({ item }) => item),
    origIndexOf: new Map(withIndex.map(({ item, origIndex }) => [item, origIndex])),
  };
}

function renderFindings(findings, savedEdits = {}) {
  findingsListEl.innerHTML = "";
  findingsById = {};
  orderedFindingIds = [];

  // idFor lets a section key its rows by something other than array position. The default now
  // prefers the server-computed, content-stable finding_id (see _assign_finding_ids in app.py) —
  // immune to reordering/dedup/incremental-reprocessing merges, unlike a plain array index — and
  // falls back to `${sectionKey}-${index}` only for data that predates this (e.g. an old cached
  // sessionStorage result from before this existed). key_facts overrides this with its own
  // sequential item.id scheme (see onFactChipClick/removeAddedFact) since those items are
  // reviewer-added, never server-provided, and can be removed from the middle of the list.
  const section = (sectionKey, title, items, extract, idFor = (item, index) => item.finding_id ?? `${sectionKey}-${index}`) => {
    if (!items || !items.length) return;
    const h = document.createElement("h2");
    h.textContent = `${title} (${items.length})`;
    findingsListEl.appendChild(h);

    items.forEach((item, index) => {
      const id = idFor(item, index);
      const meta = extract(item);
      if (savedEdits[id] !== undefined) {
        meta.text = savedEdits[id];
        meta.edited = true;
      }
      findingsById[id] = { section: sectionKey, ...meta };
      orderedFindingIds.push(id);
      findingsListEl.appendChild(makeFindingEl(id, meta));
    });
  };

  const { sorted: sortedTimeline } = sortDatedItemsStably(findings.timeline || []);
  section("timeline", "Timeline", sortedTimeline, (item) => ({
    text: item.text, date: item.date, sourceFile: item.source_file, quote: item.quote,
    recordType: item.record_type, author: item.author, atIssue: item.at_issue, bates: item.bates,
    // Present only when this entry was merged from literal duplicate source documents saying the
    // same thing (see _dedupe_with_multi_source in app.py) — the row then shows every source it
    // was corroborated by instead of just the first one, same rendering already used for
    // discrepancies below.
    sourceFiles: item.source_files, batesList: item.bates_list,
  }));

  section("potential_issues", "Potential Issues", findings.potential_issues, (item) => ({
    text: item.text, date: null, sourceFile: item.source_file, quote: item.quote, bates: item.bates,
    sourceFiles: item.source_files, batesList: item.bates_list,
  }));

  section("discrepancies", "Discrepancies", findings.discrepancies, (item) => ({
    text: item.text, date: null,
    sourceFile: (item.source_files || []).join(", "),
    quote: (item.quotes || [])[0],
    sourceFiles: item.source_files, quotes: item.quotes, batesList: item.bates_list,
  }));

  // Facts pulled in via the Key Facts panel (clicked because they weren't already covered above) —
  // not part of the server's response, persisted separately (see saveAddedFacts/loadAddedFacts).
  // Already keyed by a stable per-fact id (item.id), not position, so sorting here for display
  // order needs no special origIndex handling the way "timeline" above does.
  const addedFacts = currentSessionId ? loadAddedFacts(currentSessionId) : [];
  const sortedAddedFacts = [...addedFacts].sort((a, b) => parseDateForSort(a.date) - parseDateForSort(b.date));
  section("key_facts", "Key Facts (added)", sortedAddedFacts, (item) => ({
    text: item.text, date: item.date, sourceFile: item.sourceFile, quote: item.quote,
    recordType: item.recordType, author: item.author, atIssue: item.atIssue, bates: item.bates,
    sourceFiles: item.sourceFiles, batesList: item.batesList,
  }), (item) => `key_facts-${item.id}`);

  const savedSummaryEdit = currentSessionId ? loadSummaryEdit(currentSessionId) : null;
  const summaryText = savedSummaryEdit != null ? savedSummaryEdit : findings.summary;
  if (summaryText) {
    const h = document.createElement("h2");
    h.textContent = "Summary";
    findingsListEl.appendChild(h);
    const box = document.createElement("div");
    box.className = "summary-box";
    box.textContent = summaryText;
    box.title = "Click to edit this summary";
    box.addEventListener("click", () => startEditingSummary(box));
    findingsListEl.appendChild(box);
  }

  if (!findingsListEl.children.length) {
    findingsListEl.textContent = "No structured findings were returned for this run.";
  }
}

function renderFactsPanel() {
  const available = FACTS_CATEGORIES.filter(
    (c) => currentRawFindings?.[c.key]?.length
  );

  if (!available.length) {
    factsPanel.style.display = "none";
    return;
  }
  factsPanel.style.display = "block";

  if (!activeFactsTab || !available.some((c) => c.key === activeFactsTab)) {
    activeFactsTab = available[0].key;
  }

  factsTabsEl.innerHTML = "";
  available.forEach(({ key, label }) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "facts-tab" + (key === activeFactsTab ? " active" : "");
    btn.setAttribute("role", "tab");
    btn.innerHTML = `${label} <span class="facts-tab-count">(${currentRawFindings[key].length})</span>`;
    btn.addEventListener("click", () => {
      activeFactsTab = key;
      renderFactsPanel();
    });
    factsTabsEl.appendChild(btn);
  });

  renderFactsList();
}

// A fact is considered "already in the output" if any current finding's text normalizes to the
// same thing — catches both the model's own narrative timeline happening to already state it
// verbatim, and simply re-clicking a fact that was already added this way.
function findExistingFindingForFact(factText) {
  const target = normalize(factText);
  if (!target) return null;
  for (const id of orderedFindingIds) {
    if (normalize(findingsById[id]?.text) === target) return id;
  }
  return null;
}

function renderFactsList() {
  factsListEl.innerHTML = "";
  const items = currentRawFindings?.[activeFactsTab] || [];
  if (!items.length) {
    factsListEl.innerHTML = '<span class="facts-empty">Nothing extracted for this category.</span>';
    return;
  }

  items.forEach((item) => {
    const existingId = findExistingFindingForFact(item.text);
    // Only a fact that got into the output THROUGH this panel can be "unadded" here — one that's
    // already in the model's own narrative timeline isn't something this panel put there, so
    // there's nothing for this panel to undo (rejecting it, if desired, is a decision made on the
    // finding itself via the normal approve/reject controls, not from this facts list).
    const isRemovable = !!existingId && findingsById[existingId]?.section === "key_facts";
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "fact-chip" + (existingId ? " already-added" : "");
    chip.title = isRemovable
      ? "Already added — click to remove it from the reviewed output"
      : existingId
      ? "Already in the output — click to jump to it"
      : "Click to add this to the reviewed output";
    const icon = isRemovable ? "−" : existingId ? "✓" : "+";
    chip.innerHTML =
      `<span class="fact-chip-icon">${icon}</span><span>${escapeHtml(item.text || "")}</span>`;
    chip.addEventListener("click", () => onFactChipClick(item, existingId, isRemovable));
    factsListEl.appendChild(chip);
  });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function onFactChipClick(item, existingId, isRemovable) {
  if (existingId && isRemovable) {
    removeAddedFact(existingId);
    return;
  }
  if (existingId) {
    const el = findingsListEl.querySelector(`.finding[data-id="${CSS.escape(existingId)}"]`);
    if (el) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      el.classList.remove("fact-flash");
      // Force a reflow so re-adding the class restarts the animation if clicked again.
      void el.offsetWidth;
      el.classList.add("fact-flash");
    }
    selectFinding(existingId);
    return;
  }

  const addedFacts = loadAddedFacts(currentSessionId);
  // A stable, never-reused id (not array position) — removeAddedFact can delete from the middle
  // of this list, and a position-based id would then silently relabel every later fact's already-
  // saved review status/edits onto the wrong item.
  const nextFactId = addedFacts.reduce((max, f) => Math.max(max, f.id ?? -1), -1) + 1;
  const newId = `key_facts-${nextFactId}`;
  const newFact = {
    id: nextFactId, text: item.text, date: item.date, sourceFile: item.source_file, quote: item.quote,
    recordType: item.record_type, author: item.author, atIssue: item.at_issue, bates: item.bates,
    sourceFiles: item.source_files, batesList: item.bates_list,
  };
  addedFacts.push(newFact);
  saveAddedFacts(addedFacts);
  durablePost("/facts", { fact_id: nextFactId, payload: newFact });
  // Auto-approved: clicking to add is itself the reviewer's explicit approval decision, not a
  // pending suggestion — matches how this panel is meant to be used (a fast way to pull in facts
  // the narrative timeline missed, not a second unreviewed queue).
  setFindingStatus(newId, "approved");
  renderFindings(currentRawFindings, loadFindingEdits(currentSessionId));
  renderFactsPanel();
  updateReviewProgress();
  selectFinding(newId);
}

// The reverse of the add path above — removes a fact this panel previously added (identified by
// its stable id) from the reviewed output entirely, not just marks it rejected, since it was never
// part of the model's own output to begin with.
function removeAddedFact(id) {
  const factIdStr = id.slice("key_facts-".length);
  const addedFacts = loadAddedFacts(currentSessionId).filter((f) => String(f.id) !== factIdStr);
  saveAddedFacts(addedFacts);
  durableDelete(`/facts/${encodeURIComponent(factIdStr)}`);
  delete findingStatus[id];
  saveReviewStatus();

  if (currentFindingId === id) {
    currentFindingId = null;
    approveBtn.disabled = true;
    rejectBtn.disabled = true;
    currentPdfDoc = null;
    currentFilename = null;
    clearCanvas();
    viewerTitle.textContent = "No document loaded";
    viewerPageInfo.textContent = "";
    viewerHint.textContent = "Click a finding on the left to jump to its source.";
  }

  renderFindings(currentRawFindings, loadFindingEdits(currentSessionId));
  renderFactsPanel();
  updateReviewProgress();
}

function recordSourceLabel(sourceFile) {
  return (sourceFile && currentRecordSourceLabels[sourceFile]) || sourceFile || "";
}

// The citation string shown for a single source — always the Bates number, never a plain page
// index (the firm's own citation convention: a Bates number uniquely identifies a specific page
// across the whole production, unlike an ambiguous "page N" that only makes sense within a single
// PDF's own numbering). `bates` is computed server-side and travels with the finding from the
// moment results are rendered, not just once a reviewer happens to open the source — see
// _resolve_bates in app.py.
function citationText(sourceFile, bates) {
  const label = recordSourceLabel(sourceFile);
  return bates ? `${label} (Bates ${bates})` : `${label} (Bates not resolved)`;
}

function statusIcon(status) {
  if (status === "approved") return "✓";
  if (status === "rejected") return "✗";
  return "–";
}

function makeFindingEl(id, meta) {
  const { text, date, sourceFile, quote } = meta;

  const div = document.createElement("div");
  div.className = "finding";
  div.dataset.id = id;
  if (meta.atIssue) div.classList.add("at-issue");

  const status = findingStatus[id];
  if (status) div.classList.add(`status-${status}`);

  const icon = document.createElement("span");
  icon.className = `finding-status-icon ${status || "pending"}`;
  icon.textContent = statusIcon(status);
  div.appendChild(icon);

  const body = document.createElement("div");
  body.className = "finding-body";

  // Bold record-type/authoring-provider header line, per Olivia's real chronology-review workflow:
  // title each entry with what kind of record it came from and who authored it, both bold, so a
  // reviewer scanning quickly can find a specific note type or provider without reading every line.
  const recordType = realValue(meta.recordType);
  const author = realValue(meta.author);
  if (recordType || author) {
    const header = document.createElement("span");
    header.className = "finding-record-header";
    header.textContent = [recordType, author].filter(Boolean).join(" — ");
    body.appendChild(header);
  }
  if (meta.atIssue) {
    const badge = document.createElement("span");
    badge.className = "finding-at-issue-badge";
    badge.textContent = "AT-ISSUE";
    badge.title = "This entry involves or names a defendant in this case";
    body.appendChild(badge);
  }

  if (date) {
    const dateSpan = document.createElement("span");
    dateSpan.className = "finding-date";
    dateSpan.textContent = date;
    body.appendChild(dateSpan);
  }

  const textSpan = document.createElement("span");
  textSpan.className = "finding-text";
  textSpan.textContent = text || "";
  body.appendChild(textSpan);

  const editedTag = document.createElement("span");
  editedTag.className = "finding-edited-tag";
  editedTag.textContent = " (edited)";
  editedTag.style.display = meta.edited ? "" : "none";
  body.appendChild(editedTag);

  // Inline citation: the verbatim quote shown directly in the list, not just in the PDF viewer —
  // this is the primary way to verify a finding now, matching how Perplexity/NotebookLM/Claude/
  // ChatGPT search all handle grounded citations (a visible source snippet at the point of the
  // claim, with opening the full source as a secondary, on-demand action) rather than requiring a
  // document viewer to load and render before a reviewer can check anything. Clicking THIS
  // specifically (not the rest of the row) is what opens the PDF/highlight — reviewing many
  // findings via keyboard (arrow keys below) never has to wait on a single PDF load unless the
  // reviewer actually wants to double-check the source.
  const realQuote = realValue(quote);
  if (realQuote) {
    const citation = document.createElement("button");
    citation.type = "button";
    citation.className = "finding-citation";
    citation.title = "Click to view this passage highlighted in the source PDF";
    const truncated = realQuote.length > 160 ? realQuote.slice(0, 160) + "…" : realQuote;
    citation.innerHTML = `<span class="finding-citation-icon">&#10077;</span> ${escapeHtml(truncated)}`;
    citation.addEventListener("click", (e) => {
      e.stopPropagation(); // don't also trigger the row's own click (which just selects it)
      selectFinding(id);
      openFindingSource(id);
    });
    body.appendChild(citation);
  }

  const sourceSpan = document.createElement("span");
  sourceSpan.className = "finding-source";
  if (meta.sourceFiles && meta.sourceFiles.length) {
    // Discrepancies cite multiple sources at once.
    const batesList = meta.batesList || [];
    const parts = meta.sourceFiles.map((sf, i) => citationText(sf, batesList[i]));
    sourceSpan.textContent = parts.length ? `Sources: ${parts.join("; ")}` : "";
  } else {
    sourceSpan.textContent = sourceFile ? `Source: ${citationText(sourceFile, meta.bates)}` : "";
  }
  if (!quote) sourceSpan.classList.add("finding-no-quote");
  body.appendChild(sourceSpan);

  div.appendChild(body);

  // Clicking straight into a finding both selects it AND opens it for editing immediately — every
  // item shown here either already is, or with one click could be, part of the exported chronology,
  // so there's no separate "select first, then explicitly ask to edit" step for the mouse. The
  // citation button above has its own stopPropagation'd click handler, so clicking it to view the
  // source still doesn't also drop the reviewer into edit mode.
  div.addEventListener("click", () => {
    selectFinding(id);
    startEditingFinding(id);
  });

  return div;
}

// Lightweight: marks a finding active and enables approve/reject, WITHOUT touching the PDF
// viewer. Deliberately does not call showFinding — loading/searching/rendering a PDF is the
// slowest part of reviewing a finding, and most findings can be judged from the inline citation
// (see makeFindingEl) alone. Opening the actual source is a separate, explicit action
// (openFindingSource) so a keyboard-driven approve/reject/navigate loop never waits on a PDF
// unless the reviewer actually asks to see one. The viewer pane is reset to a neutral state
// rather than left showing a stale PDF from a previously-viewed, DIFFERENT finding — otherwise a
// highlight left over from an earlier selection could misleadingly look like it supports this one.
function selectFinding(id) {
  const meta = findingsById[id];
  if (!meta) return;

  currentFindingId = id;
  document.querySelectorAll(".finding.active").forEach((el) => el.classList.remove("active"));
  const el = findingsListEl.querySelector(`.finding[data-id="${CSS.escape(id)}"]`);
  if (el) el.classList.add("active");

  approveBtn.disabled = false;
  rejectBtn.disabled = false;
  updateDecisionButtons(id);

  const file = realValue(meta.sourceFiles ? meta.sourceFiles[0] : meta.sourceFile);
  const quote = realValue(meta.quotes ? meta.quotes[0] : meta.quote);

  currentPdfDoc = null;
  currentFilename = null;
  clearCanvas();
  if (!file) {
    viewerTitle.textContent = "No document loaded";
    viewerPageInfo.textContent = "";
    viewerHint.textContent = "This finding has no source document to display.";
  } else if (quote) {
    viewerTitle.textContent = file;
    viewerPageInfo.textContent = "";
    viewerHint.textContent = "Click the citation on the left (or press V) to view this passage highlighted in the source PDF.";
  } else {
    viewerTitle.textContent = file;
    viewerPageInfo.textContent = "";
    viewerHint.textContent = "This finding has no quote to locate automatically. Press V to open the source document at page 1.";
  }
}

// The heavyweight action: actually loads the PDF, searches for the quote, and highlights it.
// Triggered by clicking a finding's citation chip, or pressing Enter/V on the active finding.
function openFindingSource(id) {
  const meta = findingsById[id];
  if (!meta) return;
  const file = realValue(meta.sourceFiles ? meta.sourceFiles[0] : meta.sourceFile);
  const quote = realValue(meta.quotes ? meta.quotes[0] : meta.quote);
  if (!file) return;
  showFinding(file, quote, id);
}

// Points at the currently-open edit's own `finish` closure, if any — lets startEditingFinding
// cleanly commit whatever else was being edited when the reviewer clicks straight into a
// DIFFERENT finding without first explicitly finishing the previous one (clicking a plain,
// non-focusable row div doesn't reliably blur a focused textarea in every browser, so blur alone
// can't be relied on to hand off between two edits started this way).
let currentEditFinish = null;

function startEditingFinding(id) {
  if (editingFindingId === id) return; // already editing this exact one — leave it alone
  if (editingFindingId && currentEditFinish) currentEditFinish(true);

  const meta = findingsById[id];
  const el = findingsListEl.querySelector(`.finding[data-id="${CSS.escape(id)}"]`);
  const textSpan = el?.querySelector(".finding-text");
  if (!meta || !el || !textSpan) return;

  editingFindingId = id;

  const textarea = document.createElement("textarea");
  textarea.className = "finding-edit-textarea";
  textarea.value = meta.text || "";
  textarea.rows = Math.max(2, Math.ceil((meta.text || "").length / 45));

  textSpan.replaceWith(textarea);
  textarea.focus();
  textarea.select();

  const finish = (commit) => {
    if (editingFindingId !== id) return; // already finished via another path
    editingFindingId = null;
    currentEditFinish = null;
    if (commit) {
      const newText = textarea.value.trim();
      if (newText && newText !== meta.text) {
        meta.text = newText;
        meta.edited = true;
        saveFindingEdits();
        durablePost("/edit", { finding_id: id, text: newText });
      }
    }
    // Re-render just this row from current (possibly updated) meta rather than hand-patching DOM.
    const fresh = makeFindingEl(id, meta);
    el.replaceWith(fresh);
    if (currentFindingId === id) fresh.classList.add("active");
  };
  currentEditFinish = finish;

  textarea.addEventListener("click", (e) => e.stopPropagation()); // don't re-trigger the row's own click mid-edit
  textarea.addEventListener("keydown", (e) => {
    e.stopPropagation(); // don't let the global space/arrow/enter shortcuts fire while typing
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      finish(true);
    } else if (e.key === "Escape") {
      e.preventDefault();
      finish(false);
    }
  });
  textarea.addEventListener("blur", () => finish(true));
}

let summaryEditing = false;

// Same click-to-edit interaction as an individual finding (see startEditingFinding above), applied
// to the AI-drafted summary box instead of a single row — no id/meta object to thread through since
// there's only ever one summary, so this is a simpler standalone version of the same pattern.
function startEditingSummary(box) {
  if (summaryEditing) return;
  summaryEditing = true;
  const currentText = box.textContent;

  const textarea = document.createElement("textarea");
  textarea.className = "finding-edit-textarea summary-edit-textarea";
  textarea.value = currentText;
  textarea.rows = Math.max(3, Math.ceil(currentText.length / 70));

  box.replaceWith(textarea);
  textarea.focus();
  textarea.select();

  const finish = (commit) => {
    if (!summaryEditing) return;
    summaryEditing = false;
    let finalText = currentText;
    if (commit) {
      const newText = textarea.value.trim();
      if (newText && newText !== currentText) {
        finalText = newText;
        saveSummaryEdit(finalText);
      }
    }
    const fresh = document.createElement("div");
    fresh.className = "summary-box";
    fresh.textContent = finalText;
    fresh.title = "Click to edit this summary";
    fresh.addEventListener("click", () => startEditingSummary(fresh));
    textarea.replaceWith(fresh);
  };

  textarea.addEventListener("click", (e) => e.stopPropagation());
  textarea.addEventListener("keydown", (e) => {
    e.stopPropagation();
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      finish(true);
    } else if (e.key === "Escape") {
      e.preventDefault();
      finish(false);
    }
  });
  textarea.addEventListener("blur", () => finish(true));
}

// Space bar edits the currently-active finding's text, whenever the tab/window has focus and
// nothing else (an input, a textarea) is already capturing keystrokes.
// Full keyboard-driven review loop: approve/reject/navigate without ever touching the mouse, and
// without any of those actions loading a PDF (see selectFinding/openFindingSource above) — a
// reviewer working through many findings via inline citations alone should never wait on a PDF
// render just to move to the next item or make a decision.
//   Left / Right  — reject / approve the active finding, then auto-advance to the next pending one
//   Up / Down     — move the active selection without deciding (does not affect approve/reject state)
//   Enter or Space — edit the active finding's text inline, so typing can start immediately with
//                    no mouse click needed
//   V             — open the active finding's source PDF at the highlighted citation (on demand)
document.addEventListener("keydown", (e) => {
  const tag = document.activeElement?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
  if (editingFindingId) return; // let the inline edit textarea's own handler take keys while active
  if (!currentFindingId) return;

  if (e.key === " " || e.key === "Enter") {
    e.preventDefault();
    startEditingFinding(currentFindingId);
  } else if (e.key === "ArrowRight") {
    e.preventDefault();
    setFindingStatus(currentFindingId, "approved");
  } else if (e.key === "ArrowLeft") {
    e.preventDefault();
    setFindingStatus(currentFindingId, "rejected");
  } else if (e.key === "ArrowDown") {
    e.preventDefault();
    moveSelection(1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    moveSelection(-1);
  } else if (e.key === "v" || e.key === "V") {
    e.preventDefault();
    openFindingSource(currentFindingId);
  }
});

function moveSelection(direction) {
  const idx = orderedFindingIds.indexOf(currentFindingId);
  if (idx === -1) return;
  const nextIdx = idx + direction;
  if (nextIdx < 0 || nextIdx >= orderedFindingIds.length) return;
  const nextId = orderedFindingIds[nextIdx];
  selectFinding(nextId);
  const el = findingsListEl.querySelector(`.finding[data-id="${CSS.escape(nextId)}"]`);
  if (el) el.scrollIntoView({ block: "nearest" });
}

function updateDecisionButtons(id) {
  const status = findingStatus[id];
  approveBtn.classList.toggle("selected", status === "approved");
  rejectBtn.classList.toggle("selected", status === "rejected");
}

function setFindingStatus(id, status) {
  // Clicking the already-selected decision again clears it back to "pending" (undo).
  if (findingStatus[id] === status) {
    delete findingStatus[id];
  } else {
    findingStatus[id] = status;
  }
  saveReviewStatus();
  durablePost("/review", { finding_id: id, status: findingStatus[id] ?? null });

  const el = findingsListEl.querySelector(`.finding[data-id="${CSS.escape(id)}"]`);
  if (el) {
    el.classList.remove("status-approved", "status-rejected");
    const newStatus = findingStatus[id];
    if (newStatus) el.classList.add(`status-${newStatus}`);
    const icon = el.querySelector(".finding-status-icon");
    icon.className = `finding-status-icon ${newStatus || "pending"}`;
    icon.textContent = statusIcon(newStatus);
  }

  updateDecisionButtons(id);
  updateReviewProgress();
  advanceToNextPending(id);
}

function advanceToNextPending(fromId) {
  const idx = orderedFindingIds.indexOf(fromId);
  if (idx === -1) return;
  for (let i = idx + 1; i < orderedFindingIds.length; i++) {
    const nextId = orderedFindingIds[i];
    if (!findingStatus[nextId]) {
      selectFinding(nextId);
      const el = findingsListEl.querySelector(`.finding[data-id="${CSS.escape(nextId)}"]`);
      if (el) el.scrollIntoView({ block: "nearest" });
      return;
    }
  }
}

approveBtn.addEventListener("click", () => {
  if (currentFindingId) setFindingStatus(currentFindingId, "approved");
});
rejectBtn.addEventListener("click", () => {
  if (currentFindingId) setFindingStatus(currentFindingId, "rejected");
});

function updateReviewProgress() {
  const total = orderedFindingIds.length;
  let approved = 0, rejected = 0;
  orderedFindingIds.forEach((id) => {
    if (findingStatus[id] === "approved") approved++;
    else if (findingStatus[id] === "rejected") rejected++;
  });
  const pending = total - approved - rejected;
  reviewProgressEl.textContent =
    `${approved} approved, ${rejected} rejected, ${pending} pending of ${total} finding${total === 1 ? "" : "s"}`;
  exportBtn.disabled = approved === 0;
}

// Styled replacement for the browser's native confirm() — a plain OS-chrome dialog looked out of
// place next to the rest of this app's custom UI.
// Returns a Promise<boolean>, resolving true only if "Export Anyway" was clicked.
function showExportConfirm(message) {
  return new Promise((resolve) => {
    exportConfirmMessage.textContent = message;
    exportConfirmModal.style.display = "flex";
    const cleanup = (result) => {
      exportConfirmModal.style.display = "none";
      exportConfirmProceed.removeEventListener("click", onProceed);
      exportConfirmCancel.removeEventListener("click", onCancel);
      exportConfirmModal.removeEventListener("click", onOverlayClick);
      resolve(result);
    };
    const onProceed = () => cleanup(true);
    const onCancel = () => cleanup(false);
    const onOverlayClick = (e) => { if (e.target === exportConfirmModal) cleanup(false); };
    exportConfirmProceed.addEventListener("click", onProceed);
    exportConfirmCancel.addEventListener("click", onCancel);
    exportConfirmModal.addEventListener("click", onOverlayClick);
  });
}

exportBtn.addEventListener("click", async () => {
  const total = orderedFindingIds.length;
  const pending = orderedFindingIds.filter((id) => !findingStatus[id]).length;
  if (pending > 0) {
    const proceed = await showExportConfirm(
      `${pending} of ${total} findings haven't been reviewed yet and will be left out of the ` +
      `export (only approved findings are included). Export anyway?`
    );
    if (!proceed) return;
  }
  const payload = buildExportPayload();
  const originalLabel = exportBtn.textContent;
  exportBtn.disabled = true;
  exportBtn.textContent = "Generating Word document...";
  try {
    const resp = await fetch("/export/docx", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`);
    const blob = await resp.blob();
    downloadBlob(blob, `chronology-export-${timestamp()}.docx`);
  } catch (err) {
    console.error("Word export failed:", err);
    alert("Sorry, the Word document export failed. Check the console for details and try again.");
  } finally {
    exportBtn.disabled = false;
    exportBtn.textContent = originalLabel;
  }
});

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
}

// Assembles the reviewer's approved-only content into a plain JSON payload for the server to
// render as a Word document (see /export/docx in app.py) — this app does the review-state bookkeeping
// (findingStatus, edits, added facts, all in sessionStorage) and the server just renders whatever
// it's handed, so this function is the one place that decides what "approved output" means.
// Includes "key_facts" — facts pulled in via the Key Facts panel (see renderFindings) are real,
// approvable findings just like any other section, and must be exportable like any other.
function buildExportPayload() {
  const bySection = { timeline: [], potential_issues: [], discrepancies: [], key_facts: [] };
  orderedFindingIds.forEach((id) => {
    if (findingStatus[id] !== "approved") return;
    const meta = findingsById[id];
    (bySection[meta.section] || (bySection[meta.section] = [])).push(meta);
  });

  const total = orderedFindingIds.length;
  const approved = orderedFindingIds.filter((id) => findingStatus[id] === "approved").length;
  const rejected = orderedFindingIds.filter((id) => findingStatus[id] === "rejected").length;

  // Citation is always the Bates number, never a plain page index — see citationText(). Multi-
  // source items (discrepancies) join each source's own citation together.
  const cite = (f) => {
    if (f.sourceFiles && f.sourceFiles.length) {
      const batesList = f.batesList || [];
      return f.sourceFiles.map((sf, i) => citationText(sf, batesList[i])).join("; ");
    }
    return citationText(f.sourceFile, f.bates);
  };

  // The template's DATE | PAGE | RECORD | SOURCE | DESCRIPTION table — built from the timeline
  // and any manually-added Key Facts, the only two sections shaped like an actual chronology row
  // (a real per-entry date/page/record type/author, not just a citation). Merge-sorted by parsed
  // date — earliest first — rather than left in approval order: the two sections were each already
  // individually date-sorted for on-screen display (see sortDatedItemsStably/renderFindings), but
  // simply concatenating them would still show every Key Fact after every Timeline entry regardless
  // of actual date, which isn't a true chronological order for a table that's presented as one
  // unified sequence. Unparseable/placeholder dates sort to the end, same as on screen.
  // "page" is the Bates number, not a page index — per the firm's citation convention, this IS what
  // belongs in the template's PAGE column. An entry merged from literal duplicate source documents
  // (see _dedupe_with_multi_source in app.py) has sourceFiles/batesList instead of a single source —
  // show every one, joined, so the export doesn't silently hide that this fact was corroborated by
  // more than one record.
  const rows = [...bySection.timeline, ...bySection.key_facts]
    .map((f) => {
      const multiSource = f.sourceFiles && f.sourceFiles.length > 1;
      return {
        date: f.date || null,
        page: multiSource ? f.batesList.filter(Boolean).join(", ") || null : f.bates || null,
        record_type: f.recordType || null,
        author: f.author || null,
        source: multiSource
          ? f.sourceFiles.map((sf) => recordSourceLabel(sf)).join(", ")
          : recordSourceLabel(f.sourceFile) || null,
        text: f.text,
        at_issue: !!f.atIssue,
      };
    })
    .sort((a, b) => parseDateForSort(a.date) - parseDateForSort(b.date));

  const asItems = (list) => list.map((f) => ({ text: f.text, citation: cite(f) }));

  const summaryEl = document.querySelector(".summary-box");
  const summary = summaryEl ? summaryEl.textContent : "";

  // Case-level header fields (RE/DOL/Facts/patient demographics/record sources) only exist when
  // this result came from Case Mode's primary group (see renderResults) — a plain single-upload
  // session has none of this, and the export just renders blank placeholders for it, same as the
  // blank template itself.
  const caseMeta = currentCaseMeta || {};

  // Abbreviations/Record Sources legend: label -> real filename, so the reviewer can look up what
  // e.g. "FairviewOpReport" in the SOURCE column actually refers to.
  const recordSources = Object.entries(currentRecordSourceLabels).map(([filename, label]) => ({
    label, filename,
  }));

  return {
    generated_at: new Date().toLocaleString(),
    total, approved, rejected,
    plaintiff_name: caseMeta.plaintiff_name || null,
    defendant_names: caseMeta.defendant_names || [],
    dol: caseMeta.dol || null,
    facts_summary: caseMeta.facts_summary || null,
    demographics: currentRawFindings?.patient_demographics || {},
    record_sources: recordSources,
    rows,
    potential_issues: asItems(bySection.potential_issues),
    discrepancies: asItems(bySection.discrepancies),
    summary,
  };
}

// "Preview Chronology" — shows exactly what the Word export would produce, styled to resemble the
// firm's actual template, directly in the viewer pane in place of whichever PDF was showing.
// Deliberately an HTML rendering, not a generated PDF: the export itself is a Word document, not a
// PDF, so there's no real PDF to load into the pdf.js viewer here, and generating one just for this
// preview would mean a second, parallel document-generation path to keep in sync with the real one.
// Reuses buildExportPayload() directly — the exact same data /export/docx renders — so the preview
// can never drift out of sync with what actually gets exported.
function renderChronologyPreviewHtml(payload) {
  const field = (value, fallback = "(not provided)") => {
    const v = realValue(value);
    return v ? escapeHtml(String(v)) : fallback;
  };
  const demo = payload.demographics || {};

  const recordSourcesHtml = payload.record_sources && payload.record_sources.length
    ? `<ul class="preview-list">${payload.record_sources.map((e) =>
        `<li>${escapeHtml(e.label || "")} = ${escapeHtml(e.filename || "")}</li>`).join("")}</ul>`
    : `<p>(not provided)</p>`;

  const rowsHtml = payload.rows.length
    ? payload.rows.map((r) => {
        const headerBits = [r.record_type, r.author].filter((v) => realValue(v)).map((v) => escapeHtml(v));
        return `
        <tr class="${r.at_issue ? "preview-at-issue" : ""}">
          <td>${field(r.date, "")}</td>
          <td>${field(r.page, "")}</td>
          <td>${field(r.record_type, "")}</td>
          <td>${field(r.source, "")}</td>
          <td>${headerBits.length ? `<strong>${headerBits.join(" -- ")}</strong><br>` : ""}${escapeHtml(r.text || "")}</td>
        </tr>`;
      }).join("")
    : `<tr><td colspan="5">(no approved chronology entries yet)</td></tr>`;

  const listSection = (title, items, sourceLabel) => {
    if (!items.length) return "";
    return `
      <h3>${title}</h3>
      <ul class="preview-list">
        ${items.map((item) => `
          <li>${escapeHtml(item.text || "")}
            ${item.citation ? `<div class="preview-citation">${sourceLabel}: ${escapeHtml(item.citation)}</div>` : ""}
          </li>`).join("")}
      </ul>`;
  };

  const pending = payload.total - payload.approved - payload.rejected;

  return `
    <div class="preview-doc">
      <h2>COMBINED SUMMARY OF MEDICAL RECORDS / TIMELINE</h2>
      <p><strong>RE:</strong> ${field(payload.plaintiff_name)}</p>
      <p><strong>Updated:</strong> ${field(payload.generated_at)}</p>
      <p><strong>DOL:</strong> ${field(payload.dol)}</p>
      <p><strong>Facts:</strong> ${field(payload.facts_summary)}</p>
      ${payload.defendant_names && payload.defendant_names.length
        ? `<p><strong>Defendant(s):</strong> ${escapeHtml(payload.defendant_names.join(", "))}</p>` : ""}
      <p><strong>DOB:</strong> ${field(demo.dob)}</p>
      <p><strong>ADDRESS:</strong> ${field(demo.address)}</p>
      <p><strong>Social Hx:</strong> ${field(demo.social_history)}</p>
      <p><strong>PMHx:</strong> ${field(demo.past_medical_history)}</p>
      <p><strong>FHx:</strong> ${field(demo.family_history)}</p>
      <p><strong>SURGICAL HX:</strong> ${field(demo.surgical_history)}</p>
      <p><strong>PCP:</strong> ${field(demo.pcp)}</p>

      <h3>ABBREVIATIONS AND RECORD SOURCES</h3>
      ${recordSourcesHtml}

      <h3>Other record sources/Outstanding records:</h3>
      <p>&nbsp;</p>

      <h3>Chronological Events:</h3>
      <table class="preview-table">
        <colgroup>
          <col class="preview-col-narrow"><col class="preview-col-narrow">
          <col class="preview-col-narrow"><col class="preview-col-narrow">
          <col class="preview-col-desc">
        </colgroup>
        <thead><tr><th>DATE</th><th>PAGE</th><th>RECORD</th><th>SOURCE</th><th>DESCRIPTION</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>

      ${listSection("Potential Issues", payload.potential_issues, "Source")}
      ${listSection("Discrepancies", payload.discrepancies, "Sources")}

      ${payload.summary ? `
        <h3>AI-Drafted Summary (not independently verified — for context only)</h3>
        <p>${escapeHtml(payload.summary)}</p>` : ""}

      <p class="preview-footer">
        Of ${payload.total} AI-generated findings: ${payload.approved} approved and included above,
        ${payload.rejected} rejected and excluded, ${pending} not reviewed (also excluded).
      </p>
    </div>
  `;
}

// A full-screen-width modal (not an inline swap in the viewer pane) — the whole point is seeing
// the DATE/PAGE/RECORD/SOURCE/DESCRIPTION table without any horizontal scrolling, which the
// viewer pane (roughly half the window's width) couldn't give enough room for. Vertical scrolling
// within the modal is fine and expected for a long chronology.
function showChronologyPreview() {
  const payload = buildExportPayload();
  chronologyPreviewEl.innerHTML = renderChronologyPreviewHtml(payload);
  chronologyPreviewModal.style.display = "flex";
}

function hideChronologyPreview() {
  chronologyPreviewModal.style.display = "none";
}

previewChronologyBtn.addEventListener("click", showChronologyPreview);
chronologyPreviewClose.addEventListener("click", hideChronologyPreview);
chronologyPreviewModal.addEventListener("click", (e) => {
  if (e.target === chronologyPreviewModal) hideChronologyPreview(); // click outside the box
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && chronologyPreviewModal.style.display !== "none") hideChronologyPreview();
});

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function clearCanvas() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  highlightLayer.innerHTML = "";
  textLayerDiv.innerHTML = "";
}

// Bates cross-check banner: "match"/"mismatch"/"unverified" (muted, no comparison possible) — see
// extractBatesFromPage/findQuoteInDoc for how the two independently-extracted Bates numbers being
// compared are each derived.
function setBatesCheckBanner(state, text) {
  viewerBatesCheck.className = `viewer-bates-check ${state}`;
  viewerBatesCheck.textContent = text;
  viewerBatesCheck.style.display = text ? "block" : "none";
}

async function showFinding(sourceFile, quote, findingId) {
  if (!currentSessionId || !sourceFile) return;
  hideChronologyPreview();
  const myToken = ++renderToken;
  setBatesCheckBanner("unverified", "");
  const expectedBates = findingId ? findingsById[findingId]?.bates : null;

  try {
    if (currentFilename !== sourceFile) {
      viewerTitle.textContent = `Loading ${sourceFile}...`;
      // Pass an actual URL object, not a plain string. Internally pdf.js checks `url instanceof
      // URL` first and only falls back to the newer static `URL.parse()` method for plain
      // strings — and that static method isn't supported in every browser yet (it throws
      // "URL.parse is not a function" on ones without it). The `new URL(...)` constructor is
      // universally supported, so this sidesteps that code path entirely.
      const path = `/session/${currentSessionId}/pdf/${encodeURIComponent(sourceFile)}`;
      const url = new URL(path, window.location.href);
      // This pdf.js version requires an options object — a bare URL is treated as the
      // options object itself (which then has no `.url` property), not as shorthand for one.
      const loadingTask = pdfjsLib.getDocument({ url });
      const doc = await loadingTask.promise;
      if (myToken !== renderToken) return; // a newer selection started while we were loading
      currentPdfDoc = doc;
      currentFilename = sourceFile;
    }

    viewerTitle.textContent = sourceFile;

    if (!quote) {
      // No quote at all for this finding (the model said so rather than inventing one) — clear
      // any highlight left over from a previously-selected finding rather than leaving it up.
      await renderPage(1, null, null);
      viewerHint.textContent = "This finding has no quote to locate automatically — showing page 1 of the source document.";
      viewerPageInfo.textContent = `Page 1 of ${currentPdfDoc.numPages}`;
      return;
    }

    viewerHint.textContent = "Searching for the supporting passage...";

    const match = await findQuoteInDoc(currentPdfDoc, quote, expectedBates);
    if (myToken !== renderToken) return;

    if (!match) {
      await renderPage(1, null, null);
      const batesHint = expectedBates ? ` This finding cites Bates ${expectedBates} — look for that page's stamp to find it manually.` : "";
      viewerHint.textContent = (currentOcrFiles.has(sourceFile)
        ? "This document was scanned/faxed with no digital text layer, so it was read via OCR — the browser can't automatically highlight passages in it. Showing page 1; review the finding against the source image manually."
        : "Couldn't automatically locate the exact quote in this document — showing page 1. The finding may still be accurate; check manually.") + batesHint;
      viewerPageInfo.textContent = `Page 1 of ${currentPdfDoc.numPages}`;
      return;
    }

    const drew = await renderPage(match.pageNum, match.textContent, match.matchedIndices);
    if (myToken !== renderToken) return;
    viewerPageInfo.textContent = `Page ${match.pageNum} of ${currentPdfDoc.numPages}`;
    if (!drew) {
      // findQuoteInDoc already filters out candidates with nothing left to highlight after its own
      // bounds check, so this should be rare — but renderPage's independent, ground-truth check
      // (actual rendered position, not a re-derivation) is a second, different measurement, and a
      // false "success" here is worse than an honest "couldn't highlight it precisely," especially
      // given this exact failure mode (claims a highlight, shows none) is what a real-world PDF
      // triggered before this check existed. See TEST_RESULTS.md.
      viewerHint.textContent = "Found matching text on this page, but couldn't draw a precise " +
        "highlight for it (a source-document quirk) — showing the page; verify the finding manually.";
    } else {
      viewerHint.textContent = match.exact
        ? "Highlighted passage is the model's cited support for this finding — verify it actually says what the finding claims, then approve or reject."
        : "The model's quote wasn't an exact match, so this highlights the closest passage found (partial match) — check it carefully before approving.";
    }

    // Cross-check: does the Bates number visibly stamped on the page we just landed on (read
    // independently here via pdf.js) match the Bates number this finding's own citation already
    // claims (resolved server-side, via pdfplumber, from the same quote — see _resolve_bates in
    // app.py)? Two different extraction libraries agreeing on which physical page (identified by
    // its own unique printed stamp) contains this text is about as strong a non-human guarantee of
    // "this is really the right page" as this app can produce — and a disagreement is a concrete,
    // mechanically-detected reason to distrust the highlight, not just a vague "double check this."
    if (expectedBates && match.pageBates) {
      if (expectedBates === match.pageBates) {
        setBatesCheckBanner("match", `✓ Bates verified: this page is stamped ${match.pageBates}, matching this finding's citation.`);
      } else {
        setBatesCheckBanner(
          "mismatch",
          `⚠ Possible mismatch: this page is stamped ${match.pageBates}, but this finding cites ` +
          `Bates ${expectedBates}. Verify this is really the right page before relying on it.`
        );
      }
    } else if (expectedBates) {
      setBatesCheckBanner(
        "unverified",
        `Couldn't read a Bates number off this page to cross-check against this finding's citation (Bates ${expectedBates}) — verify manually.`
      );
    }

    // Kept for viewer navigation only (see viewerPageInfo above) — the citation line itself
    // already shows the Bates number from the moment a finding is rendered (see makeFindingEl),
    // computed server-side from the model's required verbatim quote rather than only discoverable
    // once a reviewer happens to open this specific finding, so there's nothing to backfill here.
    if (findingId && findingsById[findingId]) {
      findingsById[findingId].pageNum = match.pageNum;
    }
  } catch (err) {
    console.error("showFinding error:", err);
    const message = String(err);
    // A 404 fetching the PDF almost always means this is a stale cached result (sessionStorage
    // restores the last analysis automatically on page load) whose session files were deleted by
    // a *newer* upload since — only the most recent analysis's files are ever kept on disk (see
    // webapp/README.md). Detect that specific case and say so plainly instead of surfacing a raw
    // exception, and clear the stale cache so a refresh doesn't keep restoring a broken result.
    if (/\b404\b/.test(message) || /unexpected server response/i.test(message)) {
      viewerTitle.textContent = "This session has expired";
      viewerHint.textContent =
        "The source PDFs for this result are no longer on disk — only the most recent upload's " +
        "files are kept. This can happen after restoring a cached result from before a newer " +
        "upload. Please re-upload the zip to get a fresh, working session.";
      try {
        sessionStorage.removeItem(LAST_RESULT_KEY);
      } catch {
        // non-fatal
      }
    } else {
      viewerTitle.textContent = `Could not load ${sourceFile}`;
      viewerHint.textContent = message;
    }
  }
}

function normalize(s) {
  // Strip ALL punctuation, not just quote marks, before comparing. Diagnosed via
  // testing/verify_highlighting.py + a debug capture of real match failures (see
  // testing/README.md): the model sometimes reproduces a quote verbatim except for exactly one
  // trailing/internal punctuation mark — e.g. source ends a clause with a comma before continuing
  // the sentence, model's quote field ends the same words with a period, treating the fragment as
  // if it should read as a complete, grammatically "clean" sentence. Punctuation carries no meaning
  // for *locating* a passage, so stripping it from both sides removes this entire failure class
  // rather than trying to special-case every punctuation substitution.
  return (s || "")
    .replace(/[.,;:!?'"`‘’“”()[\]{}]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function normalizeWords(s) {
  return normalize(s).split(" ").filter(Boolean);
}

function realValue(s) {
  // Defensive filter: the prompt tells the model never to write placeholder text into source_file
  // or quote fields, but a local 8B model won't always comply — this stops the frontend from
  // treating "not stated" as if it were a real filename or quote (which previously caused a
  // failed PDF fetch and, worse, left a stale highlight from the prior finding on screen).
  if (!s || typeof s !== "string") return null;
  return PLACEHOLDER_VALUES.has(normalize(s)) ? null : s;
}

// Same Bates format/placement convention as _extract_bates_number in webapp/app.py — a stamp in
// the page's bottom margin, an optional letter prefix followed by a zero-padded digit run. Used to
// independently cross-check WHICH page a highlight landed on: the server already resolved a Bates
// number for this citation from its own (pdfplumber-based) reading of the source text, so if the
// CLIENT's own (pdf.js-based) reading of whatever page it just matched shows a DIFFERENT Bates
// number, that's a concrete, mechanically-verified signal — not a heuristic — that the highlight
// may be on the wrong page (or even the wrong document). See showFinding, where the two are
// compared and a mismatch is surfaced as a clear warning banner, not just a muted hint.
const BATES_PATTERN = /\b[A-Za-z]{0,6}[-_ ]?0\d{3,9}\b/;
const BATES_BOTTOM_MARGIN_FRAC = 0.12;

function extractBatesFromPage(textContent, viewport) {
  const bottomCutoff = viewport.height * (1 - BATES_BOTTOM_MARGIN_FRAC);
  for (const item of textContent.items) {
    const t = item.transform;
    if (!Array.isArray(t) || t.length !== 6 || !t.every((n) => Number.isFinite(n))) continue;
    const [, , , , x, y] = t;
    const [, vy] = viewport.convertToViewportPoint(x, y);
    if (vy < bottomCutoff) continue;
    const m = (item.str || "").match(BATES_PATTERN);
    if (m) return m[0];
  }
  return null;
}

async function findQuoteInDoc(pdfDoc, quote, expectedBates) {
  const normalizedQuote = normalize(quote);
  if (!normalizedQuote) return null;

  const pages = [];
  const exactMatches = [];

  for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
    const page = await pdfDoc.getPage(pageNum);
    const textContent = await page.getTextContent();
    const viewport = page.getViewport({ scale: 1 }); // cheap — no rendering, just for bounds-checking below

    let combined = "";
    const spans = [];
    textContent.items.forEach((item, index) => {
      // Defensive check found necessary on a real-world PDF (an EHR export that also trips a
      // "wrong pointing object" xref warning from pypdf server-side, i.e. a mildly malformed
      // file): pdf.js's getTextContent() can return text items for a page whose own coordinates
      // place them entirely outside that page's actual printed bounds — content that reads like
      // it belongs later in the document, not garbage. pdfplumber (used server-side) parses the
      // same file and sees nothing out of bounds, so this is specifically a pdf.js-side quirk on
      // this file, not bad extraction. Matching a quote into one of these produces a highlight box
      // floating in blank space with no visible text under it, so they're excluded from the search
      // space entirely — same treatment as if the text weren't there.
      //
      // Fail CLOSED, not open: a missing or malformed transform (fewer than 6 numbers) is treated
      // as out-of-bounds and excluded, rather than let through unchecked. The first version of this
      // check let unconditionally-included items with no valid transform slip past, which is
      // exactly the gap that let some genuinely off-page content back into the search — that
      // showed up as the renderer's independent post-render check (in renderPage) rejecting a
      // "found" match's spans one by one until zero were left, while the UI still claimed success.
      const t = item.transform;
      const hasValidTransform = Array.isArray(t) && t.length === 6 && t.every((n) => Number.isFinite(n));
      if (!hasValidTransform) return;
      const [, , , , x, y] = t;
      const [vx, vy] = viewport.convertToViewportPoint(x, y);
      const withinPage = vx >= -2 && vx <= viewport.width + 2 && vy >= -2 && vy <= viewport.height + 2;
      if (!withinPage) return;

      const start = combined.length;
      combined += normalize(item.str) + " ";
      spans.push({ start, end: combined.length, index });
    });

    const idx = combined.indexOf(normalizedQuote);
    // A match is only accepted if at least one span survives the bounds filter above — an exact
    // textual match built entirely from now-excluded content isn't a usable match at all (nothing
    // left to highlight), so it falls through to keep searching other pages instead of being
    // returned as a false "success" with zero boxes drawn.
    if (idx !== -1) {
      const matchEnd = idx + normalizedQuote.length;
      const matchedIndices = spans
        .filter((sp) => sp.end > idx && sp.start < matchEnd)
        .map((sp) => sp.index);
      if (window.__LFA_DEBUG_HIGHLIGHT) {
        console.warn("QUOTE MATCH DEBUG (exact)", JSON.stringify({ pageNum, matchedIndices, itemsInPage: textContent.items.length, spansInSearch: spans.length }));
      }
      if (matchedIndices.length > 0) {
        // Collected rather than returned immediately — a real risk found via direct testing: the
        // exact same short/generic sentence can appear verbatim on more than one page of a real
        // multi-page document, and returning the FIRST page found could silently show the wrong
        // one. Every exact match is gathered across the whole document first, so a Bates hint
        // (below) can disambiguate between them rather than blindly trusting page order.
        const pageBates = extractBatesFromPage(textContent, viewport);
        exactMatches.push({ pageNum, textContent, matchedIndices, exact: true, pageBates });
      }
    }

    pages.push({ pageNum, textContent, combined, spans, viewport });
  }

  if (exactMatches.length > 0) {
    // Prefer whichever exact match's own page is stamped with the Bates number this citation was
    // already resolved to server-side (see _resolve_bates in app.py, and the cross-check in
    // showFinding) — this is what actually disambiguates a quote repeated on more than one page.
    // Falls back to the first match found only when there's no Bates hint to go on, or none of the
    // candidate pages' stamps match it (e.g. the hint itself couldn't be resolved for this entry).
    if (expectedBates) {
      const preferred = exactMatches.find((m) => m.pageBates === expectedBates);
      if (preferred) return preferred;
    }
    if (exactMatches.length > 1 && window.__LFA_DEBUG_HIGHLIGHT) {
      console.warn(
        "QUOTE MATCH DEBUG: same exact quote found on multiple pages, no Bates hint resolved it — using the first",
        JSON.stringify({ pages: exactMatches.map((m) => m.pageNum), expectedBates })
      );
    }
    return exactMatches[0];
  }

  if (window.__LFA_DEBUG_QUOTE_MATCH) {
    console.warn("QUOTE MATCH DEBUG " + JSON.stringify({ normalizedQuote, pages: pages.map((p) => p.combined) }));
  }

  // No page had an exact match. Real local models occasionally paraphrase or reorder a word or
  // two even when explicitly told to quote verbatim (confirmed via testing/verify_highlighting.py
  // debug captures — see testing/README.md). Rather than show nothing, fall back to the longest
  // contiguous run of quote-words that DOES appear verbatim somewhere, as long as it's a
  // substantial fraction of the quote — a partial, clearly-labeled match is more useful to a
  // reviewer than an unexplained blank page.
  const quoteWords = normalizeWords(quote);
  let bestLength = 0;
  let bestCandidates = []; // every match tied for the best length found so far, across all pages —
                           // not just the first one, so a Bates hint (below) can still disambiguate
                           // between more than one equally-good candidate on different pages.

  for (const { pageNum, textContent, combined, spans, viewport } of pages) {
    if (quoteWords.length < bestLength) continue; // this page can't possibly beat the current best
    for (let len = quoteWords.length; len >= 4 && len >= bestLength; len--) {
      let matchedAtThisLength = false;
      for (let start = 0; start + len <= quoteWords.length; start++) {
        const candidate = quoteWords.slice(start, start + len).join(" ");
        const idx = combined.indexOf(candidate);
        if (idx === -1) continue;
        matchedAtThisLength = true;
        const matchEnd = idx + candidate.length;
        const matchedIndices = spans
          .filter((sp) => sp.end > idx && sp.start < matchEnd)
          .map((sp) => sp.index);
        // Belt-and-suspenders alongside the exact-match path above: only accept a candidate that
        // actually has something left to highlight after the bounds filter.
        if (matchedIndices.length > 0) {
          const entry = { pageNum, textContent, matchedIndices, length: len, viewport };
          if (len > bestLength) {
            bestLength = len;
            bestCandidates = [entry];
          } else if (len === bestLength) {
            bestCandidates.push(entry);
          }
        }
        break;
      }
      if (matchedAtThisLength) break; // longer match at this length beats any shorter one on this page
    }
  }

  const minAcceptableLength = Math.max(4, Math.ceil(quoteWords.length * 0.5));
  if (bestCandidates.length > 0 && bestLength >= minAcceptableLength) {
    const withBates = bestCandidates.map((c) => ({ ...c, pageBates: extractBatesFromPage(c.textContent, c.viewport) }));
    // Same disambiguation as the exact-match path above: prefer whichever tied candidate's page is
    // actually stamped with this citation's own resolved Bates number.
    const chosen = (expectedBates && withBates.find((c) => c.pageBates === expectedBates)) || withBates[0];
    return {
      pageNum: chosen.pageNum,
      textContent: chosen.textContent,
      matchedIndices: chosen.matchedIndices,
      exact: false,
      pageBates: chosen.pageBates,
    };
  }

  return null;
}

// Sets a fixed CSS pixel size on an element with !important priority, so nothing else (including
// pdf.js's own internal calc()-based sizing on the text layer container — see renderPage below)
// can silently override it. Highlight-box positions are computed once, in pixels, from real DOM
// measurements — any of these three layers (canvas, text-layer, highlight-layer) drifting to a
// different size than the others is exactly what causes a highlight to visibly misalign with the
// page, so this is intentionally more forceful than a plain style assignment.
function setExactSize(el, width, height) {
  el.style.setProperty("width", `${width}px`, "important");
  el.style.setProperty("height", `${height}px`, "important");
}

// Picks a render scale that fits the page to the viewer's actual current width, instead of a
// fixed scale. A hardcoded scale (previously 1.4) renders a page at the same pixel size
// regardless of how much room the viewer pane actually has — on realistic window sizes the
// rendered page (e.g. ~857px wide for a letter-size page) is wider than the pane, and the
// container's flex `justify-content: center` combined with `overflow: auto` means the side that
// gets clipped by centering isn't reliably reachable by scrolling in some browsers, so part of
// the page reads as permanently "cut off" rather than just scrollable. Fitting to width up front
// avoids relying on that scroll behavior at all. Safe to vary per document/container size because
// canvas/text-layer/highlight-layer are still all derived from this SAME viewport object and
// explicitly sized together in JS (see setExactSize below) — nothing here depends on the scale
// value itself being any particular number.
function computeFitToWidthScale(page) {
  const unscaledWidth = page.getViewport({ scale: 1 }).width;
  const available = viewerCanvasWrap.clientWidth - 4; // small margin so the border-radius edge isn't clipped
  if (!available || available <= 0) return 1.4;
  const fitScale = available / unscaledWidth;
  return Math.min(2.2, Math.max(0.6, fitScale));
}

async function renderPage(pageNum, textContent, matchedIndices) {
  const page = await currentPdfDoc.getPage(pageNum);
  const viewport = page.getViewport({ scale: computeFitToWidthScale(page) });

  // All three layers (canvas, text-layer-measure, highlight-layer) get IDENTICAL explicit pixel
  // dimensions — both the buffer/attribute size AND the CSS display size — so nothing can drift
  // out of sync with anything else, regardless of container width. canvas.style.width/height is
  // set explicitly here (not left to CSS) specifically so it can never differ from the other two.
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  canvas.style.width = viewport.width + "px";
  canvas.style.height = viewport.height + "px";
  highlightLayer.style.width = viewport.width + "px";
  highlightLayer.style.height = viewport.height + "px";
  setExactSize(textLayerDiv, viewport.width, viewport.height);

  await page.render({ canvasContext: ctx, viewport }).promise;

  highlightLayer.innerHTML = "";
  textLayerDiv.innerHTML = "";

  if (!textContent || !matchedIndices || !matchedIndices.length) return false;

  // Render pdf.js's own TextLayer (the same mechanism every pdf.js-based viewer uses to make text
  // selectable) into a hidden container positioned exactly over the canvas, then measure the
  // actual rendered DOM spans with getBoundingClientRect(). This uses the browser's own layout
  // engine to get pixel-accurate positions, rather than re-deriving them by hand from the PDF's
  // raw text transform matrices (baseline vs. box-top, ascent/descent, etc. are easy to get wrong
  // that way — this sidesteps all of it).
  //
  // IMPORTANT: the TextLayer constructor calls pdf.js's internal setLayerDimensions(), which
  // overwrites the container's width/height with a CSS calc() expression referencing custom
  // properties (--total-scale-factor, --scale-round-x/y) that this page never defines — that
  // calc() silently resolves to a WRONG size (confirmed empirically: 204px instead of ~683px)
  // rather than erroring, and previously caused highlight boxes to be measured against a
  // differently-sized text layer than what the canvas actually shows. setExactSize() re-asserts
  // the correct pixel size with !important immediately after, both before and after render(),
  // to guarantee this can't happen regardless of what pdf.js does internally.
  const textLayer = new pdfjsLib.TextLayer({
    textContentSource: textContent,
    container: textLayerDiv,
    viewport,
  });
  setExactSize(textLayerDiv, viewport.width, viewport.height);
  await textLayer.render();
  setExactSize(textLayerDiv, viewport.width, viewport.height);

  const containerRect = textLayerDiv.getBoundingClientRect();
  let firstBox = null;

  matchedIndices.forEach((i) => {
    const span = textLayer.textDivs[i];
    if (!span) {
      if (window.__LFA_DEBUG_HIGHLIGHT) console.warn("HIGHLIGHT DEBUG: no span for index", i, "textDivs.length", textLayer.textDivs.length);
      return;
    }
    const rect = span.getBoundingClientRect();
    const top = rect.top - containerRect.top;
    const left = rect.left - containerRect.left;
    if (window.__LFA_DEBUG_HIGHLIGHT) {
      console.warn("HIGHLIGHT DEBUG", JSON.stringify({ i, text: span.textContent, top, left, vh: viewport.height, vw: viewport.width }));
    }

    // Defense-in-depth against a real bug found on an actual EHR-exported PDF (also flagged by
    // pypdf server-side as having a malformed xref entry): some text items pdf.js returns for a
    // given page render into DOM positions well outside that page's own visible bounds — content
    // that reads like it belongs later in the document, not garbage, but isn't part of what's
    // actually printed on this page. A pre-filter in findQuoteInDoc already excludes most of these
    // from the search using the items' own PDF-space coordinates, but this checks the ACTUAL
    // rendered position instead — unambiguous ground truth, and a safety net in case some other
    // cause ever produces an out-of-bounds span here (e.g. a different malformed PDF). Skipping a
    // bad box is a much better failure mode than a highlight floating in blank space with no text
    // under it, which is confusing and looks broken.
    if (top < -2 || left < -2 || top > viewport.height + 2 || left > viewport.width + 2) return;

    const box = document.createElement("div");
    box.className = "pdf-highlight";
    box.style.left = left + "px";
    box.style.top = top + "px";
    box.style.width = rect.width + "px";
    box.style.height = rect.height + "px";
    highlightLayer.appendChild(box);
    if (!firstBox) firstBox = box;
  });

  if (firstBox) {
    firstBox.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
  }
  return !!firstBox;
}
