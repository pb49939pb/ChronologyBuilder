// Structured, PII-safe activity/error logging for the Electron main process — same JSONL format
// and daily-file-per-folder convention as webapp/applog.py (see that file's docstring for the
// full "what's safe to log" policy; the short version: never log filenames/paths that could embed
// a patient/case name, only IDs/status/timing/exception type+traceback). Deliberately two
// components logging into the SAME folder rather than one literally shared file — a shared file
// would need real cross-process write-locking for little practical benefit, and "zip the logs
// folder and send it" already produces one bundle either way.
const fs = require("fs");
const path = require("path");
const { app } = require("electron");

function getLogsDir() {
  // db.get_app_data_dir()'s Python logic, mirrored: Electron's own app.getPath("userData") is a
  // DIFFERENT directory (keyed off package.json's "name", "lawfirmagent-desktop") from the Python
  // backend's app-data dir ("LawFirmAgent") -- deliberately pointed at the SAME logs folder the
  // backend writes to, since that's the one place a user would think to zip up and send.
  const base = process.platform === "darwin"
    ? path.join(app.getPath("home"), "Library", "Application Support")
    : process.platform === "win32"
      ? (process.env.APPDATA || path.join(app.getPath("home"), "AppData", "Roaming"))
      : (process.env.XDG_DATA_HOME || path.join(app.getPath("home"), ".local", "share"));
  return path.join(base, "LawFirmAgent", "logs");
}

function todayPath() {
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD, UTC — matches Python's date.isoformat()
  return path.join(getLogsDir(), `${today}.log`);
}

function logEvent(event, message, { level = "INFO", context = null, error = null } = {}) {
  const entry = {
    ts: new Date().toISOString(),
    level,
    component: "electron",
    event,
    message,
  };
  if (context) entry.context = context;
  if (error) entry.traceback = error.stack || String(error);

  try {
    const logsDir = getLogsDir();
    fs.mkdirSync(logsDir, { recursive: true });
    fs.appendFileSync(todayPath(), JSON.stringify(entry) + "\n", "utf-8");
  } catch {
    // A logging failure must never crash the app it's trying to help diagnose.
  }
}

const RETENTION_DAYS = 90; // matches webapp/applog.py's own retention window

function cleanupOldLogs() {
  try {
    const logsDir = getLogsDir();
    if (!fs.existsSync(logsDir)) return;
    const cutoff = Date.now() - RETENTION_DAYS * 24 * 60 * 60 * 1000;
    for (const name of fs.readdirSync(logsDir)) {
      const m = name.match(/^(\d{4}-\d{2}-\d{2})\.log$/);
      if (!m) continue;
      if (new Date(m[1] + "T00:00:00Z").getTime() < cutoff) {
        fs.unlinkSync(path.join(logsDir, name));
      }
    }
  } catch {
    // Best-effort — a cleanup failure must never prevent the app from starting.
  }
}

module.exports = { logEvent, cleanupOldLogs };
