const form = document.getElementById("case-form");
const startBtn = document.getElementById("start-btn");
const startError = document.getElementById("start-error");
const jobView = document.getElementById("job-view");
const jobSummary = document.getElementById("job-summary");
const groupsList = document.getElementById("groups-list");

const JOB_KEY = "lawfirmagent_case_job_id";
let pollTimer = null;

const DETAIL_LEVELS = ["brief", "standard", "detailed"];

// --- Folder picker ---
// A native <input type="file" webkitdirectory> — the same OS folder-picker experience the
// single-zip-upload flow on the main page already gets for a single file. This used to instead
// browse the SERVER's own filesystem via a custom /case/browse endpoint, which required Flask to
// already have broad OS-level read permission to arbitrary folders (macOS Full Disk Access, or the
// Windows-service equivalent) — fragile, and a fundamentally different trust model than a plain
// upload. Every file the picker finds (subfolders included) gets uploaded to /case/start with its
// path relative to the picked folder preserved via webkitRelativePath, so Flask needs no special
// filesystem permissions at all, and this works identically whether Flask is running on this same
// machine or a separate tower (see PRODUCT_DEFINITION.md/TOWER_SETUP.md) — the files travel over
// HTTP either way.
const caseFolderInput = document.getElementById("case-folder-input");
const caseFolderSummary = document.getElementById("case-folder-summary");

caseFolderInput.addEventListener("change", () => {
  const files = caseFolderInput.files;
  if (!files.length) {
    caseFolderSummary.style.display = "none";
    return;
  }
  const pdfCount = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".pdf")).length;
  const topName = (files[0].webkitRelativePath || files[0].name).split("/")[0];
  caseFolderSummary.textContent = `Selected "${topName}" — ${pdfCount} PDF file${pdfCount === 1 ? "" : "s"} found.`;
  caseFolderSummary.style.display = "block";
});

function appendFilesToFormData(body, fileList) {
  Array.from(fileList).forEach((file) => {
    body.append("files", file, file.webkitRelativePath || file.name);
  });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  startError.style.display = "none";
  startBtn.disabled = true;
  startBtn.textContent = "Starting…";

  try {
    const body = new FormData();
    body.set("plaintiff_name", document.getElementById("plaintiff-name").value);
    body.set("priority_hint", document.getElementById("priority-hint").value);
    body.set("detail_level", DETAIL_LEVELS[document.getElementById("detail-slider").value]);
    appendFilesToFormData(body, caseFolderInput.files);

    const resp = await fetch("/case/start", { method: "POST", body });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Failed to start case");

    sessionStorage.setItem(JOB_KEY, data.job_id);
    startWatching(data.job_id);
  } catch (err) {
    startError.textContent = String(err.message || err);
    startError.style.display = "block";
  } finally {
    startBtn.disabled = false;
    startBtn.textContent = "Start Case";
  }
});

function statusBadge(status) {
  const label = { pending: "Pending", processing: "Processing…", done: "Done", failed: "Failed" }[status] || status;
  return `<span class="batch-status batch-status-${status}">${label}</span>`;
}

function renderJob(manifest) {
  jobView.style.display = "block";
  const groups = manifest.groups || {};
  const keys = Object.keys(groups);
  const doneCount = keys.filter((k) => groups[k].status === "done").length;
  const failedCount = keys.filter((k) => groups[k].status === "failed").length;
  const otherGroupCount = keys.length - 1; // primary (plaintiff) group + any "also mentions" ones

  const rescanning = manifest.rescan_status === "processing";
  jobSummary.innerHTML = `
    <div><strong>Plaintiff:</strong> ${escapeHtml(manifest.plaintiff_name)}</div>
    <div><strong>Folder:</strong> ${escapeHtml(manifest.folder_display_name)}</div>
    ${manifest.defendant_names && manifest.defendant_names.length
      ? `<div><strong>Defendant(s):</strong> ${escapeHtml(manifest.defendant_names.join(", "))}</div>` : ""}
    ${manifest.dol ? `<div><strong>DOL:</strong> ${escapeHtml(manifest.dol)}</div>` : ""}
    ${manifest.facts_summary ? `<div><strong>Facts:</strong> ${escapeHtml(manifest.facts_summary)}</div>` : ""}
    ${manifest.complaint_warning ? `<div class="batch-error">${escapeHtml(manifest.complaint_warning)}</div>` : ""}
    <div><strong>Overall status:</strong> ${statusBadge(manifest.status)}</div>
    ${manifest.progress_text ? `<div class="group-meta">${escapeHtml(manifest.progress_text)}</div>` : ""}
    ${otherGroupCount > 0 ? `<div class="group-meta">Also found ${otherGroupCount} other individual${otherGroupCount === 1 ? "" : "s"} referenced in these records (${doneCount} group(s) done, ${failedCount} failed)</div>` : ""}
    ${manifest.error ? `<div class="batch-error">${escapeHtml(manifest.error)}</div>` : ""}
    ${manifest.status === "done" ? `
      <div class="rescan-row">
        <button type="button" id="rescan-btn" ${rescanning ? "disabled" : ""}>
          ${rescanning ? "Checking for new files…" : "Check for new files"}
        </button>
        ${manifest.rescan_message ? `<span class="group-meta">${escapeHtml(manifest.rescan_message)}</span>` : ""}
      </div>` : ""}
  `;
  // jobSummary.innerHTML is fully regenerated on every poll (see startWatching's 3s interval), so
  // the click listener needs re-attaching each time rather than once at page load.
  const rescanBtn = document.getElementById("rescan-btn");
  if (rescanBtn) {
    rescanBtn.addEventListener("click", () => startRescan(manifest.job_id));
  }

  groupsList.innerHTML = "";
  keys.forEach((key) => {
    const g = groups[key];
    const row = document.createElement("div");
    row.className = "group-row";
    let extra = "";
    // A "View chronology" link appears as soon as ANY findings exist, not only once status is
    // "done" — a large, multi-chunk case can take a long time end to end, and there's no reason
    // to make a reviewer wait for all of it when the first pass is already a real, readable
    // chronology. The linked page polls for further updates on its own (see app.js) while this
    // group is still processing.
    if (g.findings) {
      const label = g.status === "done" ? "View chronology" : "View chronology (still building) ";
      extra = `<a href="/review?case=${manifest.job_id}&group=${encodeURIComponent(key)}" target="_blank">${label} &rarr;</a>`;
      if (g.stats) {
        extra += ` <span class="group-meta">${g.stats.documents_processed} docs, ${g.stats.total_pages} pages, ${g.stats.wall_time_seconds}s</span>`;
      }
    } else if (g.status === "failed") {
      extra = `<span class="batch-error">${escapeHtml(g.error || "unknown error")}</span>`;
    }
    row.innerHTML = `
      <span class="group-name">${escapeHtml(g.display_name)}</span>
      <span class="group-meta">${g.file_count} file${g.file_count === 1 ? "" : "s"}</span>
      ${statusBadge(g.status)}
      ${g.progress_text ? `<span class="group-meta">${escapeHtml(g.progress_text)}</span>` : ""}
      <span class="group-extra">${extra}</span>
    `;
    groupsList.appendChild(row);
  });

  // Also keep polling while a rescan is running (see startRescan) — the job's own top-level
  // `status` stays "done" throughout a rescan (only `rescan_status` changes), so checking `status`
  // alone would stop polling after the very first post-rescan poll and never show its progress or
  // completion message.
  const stillWorking = manifest.status === "scanning" || manifest.status === "processing"
    || manifest.rescan_status === "processing";
  return stillWorking;
}

const rescanFolderInput = document.getElementById("rescan-folder-input");

// Manually triggered only (a button, not automatic background polling) — this is a single local
// user, and unprompted background LLM usage while the reviewer isn't looking would be a surprise,
// not a convenience. There's no server-side folder path to silently re-scan anymore (see
// /case/start's redesign) — checking for new files means re-picking the same folder via the native
// picker so the browser can re-enumerate its CURRENT contents, then uploading that; the backend
// diffs it against what it's already processed (see /case/<job_id>/rescan in app.py) and
// reprocesses only genuinely new files.
function startRescan(jobId) {
  rescanFolderInput.value = ""; // ensures "change" fires even if the same folder is picked again
  rescanFolderInput.onchange = async () => {
    if (!rescanFolderInput.files.length) return; // picker was cancelled
    try {
      const body = new FormData();
      appendFilesToFormData(body, rescanFolderInput.files);
      const resp = await fetch(`/case/${encodeURIComponent(jobId)}/rescan`, { method: "POST", body });
      const data = await resp.json();
      if (!resp.ok) {
        alert(data.error || "Couldn't start checking for new files.");
        return;
      }
      // The job's overall `status` stays "done" throughout a rescan (only `rescan_status` changes —
      // see _run_case_rescan) — polling had already stopped once status first reached "done" (see
      // startWatching below), so it needs explicitly restarting here to pick up rescan progress.
      startWatching(jobId);
    } catch {
      alert("Couldn't reach the server to check for new files.");
    }
  };
  rescanFolderInput.click();
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

async function pollOnce(jobId) {
  try {
    const resp = await fetch(`/case/status/${jobId}`);
    if (!resp.ok) return false;
    const manifest = await resp.json();
    return renderJob(manifest);
  } catch {
    return true; // transient network hiccup — keep trying rather than giving up
  }
}

function startWatching(jobId) {
  if (pollTimer) clearInterval(pollTimer);
  pollOnce(jobId);
  pollTimer = setInterval(async () => {
    const stillWorking = await pollOnce(jobId);
    if (!stillWorking) clearInterval(pollTimer);
  }, 3000);
}

// Opening this page via a link like /case?job=<job_id> (e.g. from the dashboard's case list, for
// a case that wasn't started in this browser tab) watches that specific job — takes priority over
// whatever this tab last had open, since a deliberate link to a specific case is a stronger signal
// than "whatever this tab happened to be doing before." Otherwise, resume whatever case was last
// active in this browser tab's session, if any (the previous, tab-only behavior).
const urlParams = new URLSearchParams(window.location.search);
const linkedJobId = urlParams.get("job");
if (linkedJobId) {
  sessionStorage.setItem(JOB_KEY, linkedJobId);
  startWatching(linkedJobId);
} else {
  const lastJobId = sessionStorage.getItem(JOB_KEY);
  if (lastJobId) startWatching(lastJobId);
}
