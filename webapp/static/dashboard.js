const caseListEl = document.getElementById("case-list");
const caseCountEl = document.getElementById("case-count");

function statusBadge(status) {
  const label = {
    scanning: "Scanning…", pending: "Pending", processing: "Processing…",
    done: "Done", failed: "Failed", error: "Error",
  }[status] || status;
  return `<span class="batch-status batch-status-${status}">${label}</span>`;
}

// A second, independent badge — human review/export progress, distinct from the pipeline-status
// badge above. Only meaningful once processing is actually done (see callers), and "exported" wins
// over any in-progress review state since it's the most advanced thing that can be true.
function reviewStatusBadge(progress, exportedAt) {
  if (!progress || progress.total === 0) return "";
  if (exportedAt) {
    return `<span class="review-status review-status-exported" title="Exported ${formatDate(exportedAt)}">Exported</span>`;
  }
  if (progress.decided === 0) {
    return '<span class="review-status review-status-needs-review">Needs Review</span>';
  }
  if (progress.decided < progress.total) {
    return '<span class="review-status review-status-in-review">In Review</span>';
  }
  return '<span class="review-status review-status-reviewed">Reviewed</span>';
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function formatDate(unixSeconds) {
  if (!unixSeconds) return null;
  return new Date(unixSeconds * 1000).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function metaLine(job) {
  const parts = [];
  parts.push(`Defendant(s): ${job.defendant_names && job.defendant_names.length ? escapeHtml(job.defendant_names.join(", ")) : "—"}`);
  parts.push(`${job.total_documents} document${job.total_documents === 1 ? "" : "s"}`);
  const started = formatDate(job.started_at);
  if (started) parts.push(`Started ${started}`);
  if (job.group_count > 1) {
    parts.push(`${job.group_count} individuals`);
  }
  if (job.failed_group_count > 0) {
    parts.push(`${job.failed_group_count} group${job.failed_group_count === 1 ? "" : "s"} failed`);
  }
  return parts.join(" &middot; ");
}

function caseAction(job) {
  // "Continue reviewing" is the fast path straight into the reviewer, available as soon as the
  // primary (plaintiff) group has any findings at all — it doesn't have to be fully done, since a
  // large multi-chunk case can take a long time end to end and there's no reason to make a
  // reviewer wait for all of it (see the same reasoning in case.js's renderJob). Otherwise there's
  // nothing to review yet (still scanning/early chunk, or the whole job errored before any records
  // were read) — send to the case status page instead, which shows live progress.
  if (job.primary_group_ready) {
    const url = `/review?case=${encodeURIComponent(job.job_id)}&group=${encodeURIComponent(job.primary_group_key)}`;
    return `<a href="${url}" target="_blank">Continue reviewing &rarr;</a>`;
  }
  return `<a href="/case?job=${encodeURIComponent(job.job_id)}">View status &rarr;</a>`;
}

async function loadCases() {
  let jobs = [];
  try {
    const resp = await fetch("/case/jobs");
    // fetch() only rejects on a genuine network failure -- an HTTP error status (e.g. a 500) still
    // resolves normally, so this must be checked explicitly or a real server error would silently
    // render as if there were simply no cases yet, which is a much more misleading failure mode.
    if (!resp.ok) throw new Error(`server returned ${resp.status}`);
    jobs = await resp.json();
  } catch {
    caseListEl.innerHTML = '<div class="case-list-empty">Couldn\'t load cases &mdash; check the server is running and try refreshing.</div>';
    return;
  }

  caseCountEl.textContent = jobs.length ? `(${jobs.length})` : "";

  if (!jobs.length) {
    caseListEl.innerHTML = '<div class="case-list-empty">No cases yet &mdash; start your first one above.</div>';
    return;
  }

  caseListEl.innerHTML = "";
  jobs.forEach((job) => {
    const row = document.createElement("div");
    row.className = "case-row";
    let failedNote = "";
    // Only add this second link when the primary action already points elsewhere (straight into
    // the reviewer) — otherwise it would just duplicate the same "View status" link twice.
    if (job.failed_group_count > 0 && job.primary_group_ready) {
      failedNote = `<div class="case-row-extra"><a href="/case?job=${encodeURIComponent(job.job_id)}">View case status &rarr;</a></div>`;
    }
    row.innerHTML = `
      <div class="case-row-top">
        <span class="case-row-name">${escapeHtml(job.plaintiff_name || job.folder_display_name)}</span>
        ${statusBadge(job.status)}
        ${job.status === "done" ? reviewStatusBadge(job.primary_group_review_progress, job.primary_group_exported_at) : ""}
      </div>
      <div class="case-row-meta">${metaLine(job)}</div>
      <div class="case-row-action">${caseAction(job)}</div>
      ${failedNote}
    `;
    caseListEl.appendChild(row);
  });
}

loadCases();
