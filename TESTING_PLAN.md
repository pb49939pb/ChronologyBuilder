# LawFirmAgent — Local Testing Plan

## 0. What This Doc Is

A step-by-step plan for prototyping the extraction/verification pipeline on **this machine** (a personal Apple M3 MacBook, 16GB unified memory) before any real case documents are involved. This is a dev sandbox for testing whether the approach works at all — it is **not** the eventual deployment target. Per §4 of `PRODUCT_DEFINITION.md`, the actual firm system should live on a dedicated workstation, and per §7/§9, nothing here touches real PHI or a live case until the firm formally approves the project (Phase 0). Everything in this doc uses synthetic or already-public test text only.

## 1. Hardware Reality Check: M3, 16GB

16GB of unified memory is shared between macOS, every other running app, and the model — there's no dedicated VRAM to fall back on. Rule of thumb: keep total model weight size under roughly 40-50% of total RAM so there's room for the OS, context window, and everything else you have open. That puts the realistic ceiling on this machine at **7B–8B parameter models at 4-bit quantization** (~4.5–5GB of weights). Practical implications:

- **This machine cannot run the 32B–70B models recommended in §5 of the product doc for the real deployment.** That's expected and fine — this machine's job is to validate the pipeline logic (extraction prompts, citation grounding, verifier pattern, evaluation approach), not to be the final model.
- **Running two 8B models loaded simultaneously (for the generator/verifier split) will be tight-to-infeasible on 16GB.** Ollama's default behavior swaps models in and out of memory automatically (`OLLAMA_KEEP_ALIVE`, default 5 min), so the practical approach here is **sequential, not concurrent**: run the extraction pass, let Ollama unload or explicitly unload that model, then load the verifier model. Slower, but it works and it's exactly what a resource-constrained deployment would also need to do.
- Close other memory-heavy apps (browser with many tabs, etc.) before running longer tests — swapping to disk will make everything much slower and isn't representative of real performance.

## 2. Environment Setup (done as of 2026-07-21)

Ollama was installed and verified working on this machine. Notes specific to this setup, since a couple of things deviated from the default instructions:

- **Homebrew is not installed on this machine.** Ollama was installed directly via the official installer script (`curl -fsSL https://ollama.com/install.sh | sh`), which downloads `Ollama.app` to `/Applications` on macOS.
- **The installer's step that symlinks the `ollama` CLI to `/usr/local/bin` requires `sudo`**, which needs an interactive password prompt not available in this environment. Workaround used: symlinked the CLI into a user-writable directory instead:
  ```
  mkdir -p ~/bin
  ln -sf /Applications/Ollama.app/Contents/Resources/ollama ~/bin/ollama
  export PATH="$HOME/bin:$PATH"
  ```
  This `export PATH` line has since been added to `~/.zshrc` permanently, so any new Terminal window/tab picks it up automatically — no manual step needed anymore. (Alternative if preferred later: `sudo ln -sf /Applications/Ollama.app/Contents/Resources/ollama /usr/local/bin/ollama` once manually, the standard way.)
- **The server now auto-starts on login via a LaunchAgent** — no manual step needed anymore. Set up at `~/Library/LaunchAgents/com.lawfirmagent.ollama.plist`:
  - Runs `/Applications/Ollama.app/Contents/Resources/ollama serve` with `OLLAMA_NO_CLOUD=1` and `OLLAMA_HOST=127.0.0.1:11434` set explicitly.
  - `RunAtLoad` + `KeepAlive` — starts automatically at login, and relaunches automatically if it ever crashes or is killed (verified: killing the process directly had launchd restart it within ~3 seconds).
  - Logs to `~/Library/Logs/ollama-serve.log` (stdout) and `~/Library/Logs/ollama-serve.err.log` (stderr) — check these if `ollama list` ever fails to connect.
  - Useful commands:
    ```
    launchctl list | grep lawfirmagent          # check it's loaded/running
    launchctl bootout gui/$(id -u)/com.lawfirmagent.ollama   # stop it and unload
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lawfirmagent.ollama.plist  # (re)load it
    ```
  - (For reference, the old manual way — no longer needed day-to-day — was `OLLAMA_NO_CLOUD=1 nohup ollama serve > /tmp/ollama_serve.log 2>&1 & disown`.)
- **`OLLAMA_NO_CLOUD=1` is required, not optional, for this project.** Ollama ships a "cloud" feature (remote inference + web search) that is **enabled by default** in this version (confirmed via the startup log: `OLLAMA_NO_CLOUD:false`, `Ollama cloud disabled: false` before we set the flag). Nothing in normal local `/api/generate` use triggers it, and an empirical check (monitoring `lsof` connections on the server process during a live request) showed every connection was `localhost→localhost`, no external IPs — but always start the server with this flag set going forward as defense-in-depth, and re-verify after any Ollama version upgrade, since defaults can change. This is the software-level control; §7 of the product doc's "no internet egress, firewall rule not just policy" is still the authoritative control for the real deployment — don't rely on this flag alone once real PHI is involved.
  It listens on `127.0.0.1:11434` and stays running in the background. If it's ever not running, `ollama list` will fail with a connection error — just re-run the line above.

## 3. What's Been Verified So Far

- **Model pulled:** `llama3.1:8b` (Meta's Llama 3.1, 8B parameters, Q4 quantization, 4.9GB on disk).
- **Smoke test:** basic prompt ("capital of France") returned a correct answer in ~16s including cold model load.
- **Realistic task test:** gave it a synthetic clinical note —

  > *"Pt seen 03/14/2024 for follow-up. Jane Doe reports persistent lower back pain since fall on 02/10/2024. Denies numbness or tingling. Plan: MRI ordered, PT referral."*

  — and asked it to extract patient name, visit date, and chief complaint as JSON. It returned a correct, well-formed result in 4.5 seconds at ~18 tokens/second (via direct API call, not the interactive CLI, to get clean output and timing).

**Read:** this is a genuinely encouraging first signal — an 8B model on a 16GB laptop handled a realistic extraction task correctly and fast. It says nothing yet about hallucination rate on harder or longer documents, which is the real question — that's what the rest of this plan is for.

## 4. Model Shortlist to Try Next (all fit in 16GB)

| Model | Ollama tag | Size (Q4) | Why try it |
|---|---|---|---|
| Llama 3.2 3B | `llama3.2:3b` | ~2GB | Fast baseline / cheap sanity checks, lower quality ceiling |
| Llama 3.1 8B | `llama3.1:8b` | ~4.9GB | Already installed; solid general baseline |
| Qwen 2.5 7B Instruct | `qwen2.5:7b` | ~4.7GB | Qwen family scored well on some 2026 hallucination trackers; worth a head-to-head vs Llama on the same test documents |
| Qwen 3 8B (thinking mode) | `qwen3:8b` | ~5GB | Has a reasoning/"thinking" mode — per the product doc, reasoning mode roughly halves hallucination rate in published benchmarks. Slower per response; worth measuring the accuracy/speed tradeoff directly |
| Phi-4-mini | `phi4-mini` | ~2.5GB | Small, fast; useful as a cheap verifier-pass candidate if 7-8B-vs-7-8B proves too slow running sequentially |

Pull any of these the same way: `ollama pull <tag>`.

## 5. Step-by-Step Plan

**Step 1 — Build a small synthetic test set (do this before anything else).**
Write 5-10 short fake "clinical note" style paragraphs by hand (or ask an LLM to generate them) covering the kinds of facts that matter: dates, providers, medications, complaints, procedures, a couple of deliberately tricky cases (a date that's easy to misread, two similar-sounding medications, a note that contradicts an earlier one). Write down the *correct* extracted facts yourself first — this is your answer key. **Never use real case documents for this step** — the point is a repeatable, known-answer test, and real PHI has no business on a personal laptop before Phase 0 approval anyway.

**Step 2 — Run extraction prompts against the test set, score by hand.**
For each synthetic note, run the same extraction prompt through `llama3.1:8b` and record: did it get every fact right, did it invent anything not in the text, did it miss anything. This gives you a real (if small) hallucination rate on your own test documents rather than relying on published benchmarks.

**Step 3 — Repeat Step 2 with Qwen 2.5 7B and Qwen 3 8B (thinking mode) on the exact same test set.**
Compare accuracy and speed across the three. This is the "benchmark 2-3 candidates" step called for in §5 of the product doc — do it here, cheaply, before deciding what the real deployment should run.

**Step 4 — Prototype the verifier pass.**
Take the facts your best-performing model extracted in Step 2/3, and write a second, separate prompt that gives a *different* model only the claimed fact and the source note, asking "does this note actually support this claim — yes/no, quote the supporting text." Run it with whichever model you didn't use for extraction. Check whether the verifier correctly catches any mistakes you deliberately know are wrong (this is why your answer key from Step 1 matters — you can salt the test set with a note or two where you already know the "obvious" extraction would be subtly wrong).

**Step 5 — Note what breaks.**
Specifically watch for: dates transposed or misread, similar-sounding medication names swapped, facts merged across two different notes when given multiple documents at once, and confident-sounding answers on ambiguous/missing information (the model should say "not stated" rather than guessing — test this explicitly with a note that omits a field it's asked for).

**Step 6 — Decide if this hardware is sufficient for continued prototyping, or if it's time to move to real hardware.**
If accuracy on the synthetic set looks promising and speed is tolerable, this laptop is fine to keep prototyping pipeline logic (prompt design, citation formatting, the review-UI flow) on. It is **not** a substitute for testing on the actual dedicated workstation hardware from §4 of the product doc once you're ready to test with larger models (32B+) or real document volumes — plan to redo the accuracy benchmarking on that hardware/those models before Phase 1 of the rollout, since larger models may behave differently than what's tested here.

## 6. Explicitly Out of Scope for This Testing Phase

- Any real case documents or real PHI of any kind.
- OCR/scanned-document pipeline (Docling/Unstructured) — start with clean typed text first to isolate model behavior from parsing quality.
- The review UI and audit logging — those matter for the real system but aren't needed to answer "is the model good enough."
- Firm approval workflow (§7/§9 Phase 0) — this testing is personal exploration to inform that conversation, not a substitute for it.

## 7. One-Time Git Setup (once the GitHub repo exists)

This repo ships tracked git hooks under `hooks/` (not the usual untracked `.git/hooks/`, so they
travel with the repo and everyone gets them). Git doesn't use this directory automatically — run
once, right after cloning:

```
git config core.hooksPath hooks
```

This enables `hooks/pre-push`, a lightweight, non-blocking reminder that the patch version bumps
automatically once a push lands (the actual automatic bump is `.github/workflows/bump-version.yml`,
which runs server-side after the push — a local pre-push hook can't reliably inject a new commit
into a push that's already in flight, so this is intentionally not where the real bump happens).
