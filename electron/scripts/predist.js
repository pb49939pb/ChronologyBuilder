// Runs automatically before `npm run dist` (npm's own pre<script> convention) — re-freezes the
// Python backend from CURRENT webapp/ source before every package build. Without this, `npm run
// dist` only re-packages whatever's already sitting in electron/vendor/backend-mac(/win)/, which
// can silently go stale relative to webapp/ (found the hard way on 2026-07-26 — see
// TEST_RESULTS.md: a backend frozen before the versioning/logging work shipped for two releases
// missing all of it, including the version badge itself, with nothing visibly wrong at build time).
const { spawnSync } = require("child_process");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const pythonPath = process.platform === "win32"
  ? path.join(repoRoot, "webapp", ".venv", "Scripts", "python.exe")
  : path.join(repoRoot, "webapp", ".venv", "bin", "python");

const result = spawnSync(pythonPath, [path.join(repoRoot, "scripts", "build_backend.py")], {
  stdio: "inherit",
});

if (result.status !== 0) {
  console.error("Backend freeze failed — see output above. Not proceeding with electron-builder.");
  process.exit(result.status || 1);
}
