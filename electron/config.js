// Two deployment topologies this shell needs to support, controlled by env vars (see
// DESKTOP_PACKAGING.md and TOWER_SETUP.md for the reasoning):
//
// LAWFIRMAGENT_MODE=local (default) — spawn Flask + Ollama on THIS machine, then show them in a
//   window. Used for dev/testing here, and for a future single-machine "everything bundled" build.
//
// LAWFIRMAGENT_MODE=remote — spawn nothing; just open a window pointed at an already-running
//   instance elsewhere (the actual target setup: a dedicated "tower" on a private, air-gapped
//   wired link, with this Electron shell running on the wife's everyday Windows laptop).
const MODE = process.env.LAWFIRMAGENT_MODE || "local";
const REMOTE_URL = process.env.LAWFIRMAGENT_REMOTE_URL || "http://192.168.50.1:5050";
const LOCAL_PORT = Number(process.env.LAWFIRMAGENT_PORT || 5050);
const OLLAMA_PORT = 11434;
const LOCAL_URL = `http://127.0.0.1:${LOCAL_PORT}`;
// Must match webapp/app.py's own MODEL default — single source of truth would need a shared
// config file across the Node/Python boundary, not worth it for one constant; kept in sync by hand.
const MODEL_NAME = process.env.LAWFIRMAGENT_MODEL || "llama3.1:8b";

module.exports = { MODE, REMOTE_URL, LOCAL_PORT, OLLAMA_PORT, LOCAL_URL, MODEL_NAME };
