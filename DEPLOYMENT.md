# Containerized deployment — feasibility, tradeoffs, and how to use it

Prompted by: "figure out if we can start up the model and app in a single container/VM that's not
connected to the internet, as a HIPAA risk-mitigation strategy." Short answer: yes, and
`docker-compose.yml` at the repo root is a ready design for it — but it's the wrong move on *this*
machine specifically, for a concrete, current reason. Read on before running it.

**Not yet tested end-to-end.** No container runtime (Docker/Podman/OrbStack/Colima) is installed on
this dev machine, and installing Docker Desktop requires an interactive macOS System
Extension-approval step that can't be scripted — so this compose file is a well-reasoned design
based on documented Docker/Ollama/NVIDIA patterns, not something that's been run and verified here.
Treat it as a strong starting point to validate on the actual target hardware, not a finished,
tested deployment.

## The real tradeoff: GPU passthrough

Docker Desktop on macOS runs containers inside a lightweight Linux VM. That VM has **no path to
the host's Metal GPU** — confirmed as still true in 2026, even on current-generation Apple Silicon
Macs. Apple's own native `container` tool has the same limitation for the same underlying reason
(the GPU lacks the IOMMU support a hypervisor needs for secure passthrough). Practically: if Ollama
runs inside a container on an Apple Silicon Mac, it falls back to CPU-only inference — commonly
reported as a **3-5x slowdown** versus running natively with Metal acceleration, which is exactly
what this project already has today (Ollama via a LaunchAgent, `OLLAMA_NO_CLOUD=1`, bound to
`127.0.0.1:11434`).

So: **on this dev machine, or any Apple Silicon deployment (including a Mac Studio, one of the
hardware options in `PRODUCT_DEFINITION.md` §4), don't containerize Ollama.** The performance cost
is real and the security benefit is marginal — a container's network isolation on macOS is enforced
by the same host kernel/firewall you already control directly, so wrapping it in Docker mostly adds
a privileged VM + daemon as extra attack surface, for a boundary you can already draw with a
firewall rule. That's a worse trade, not a better one.

**On a Linux + NVIDIA GPU workstation (the other option in §4), the calculus flips.** The NVIDIA
Container Toolkit gives mature, low-overhead GPU passthrough — no such penalty — and Docker's
`internal: true` network mode gives you something the current setup doesn't: a network boundary
enforced structurally by the container runtime itself, not by a firewall rule you have to remember
to keep in place. That's a genuine, worthwhile HIPAA risk-mitigation improvement, and it's what
`docker-compose.yml` is written for.

## Recommendation by target hardware

| Target | Recommendation |
|---|---|
| This Mac (dev/prototyping) | Keep the current native setup (LaunchAgent + `OLLAMA_NO_CLOUD=1` + host firewall). Don't containerize. |
| Production Mac Studio (Apple Silicon) | Same as above — run Ollama natively for Metal acceleration. Optionally containerize *only* the Flask app (it doesn't need a GPU) pointing at the native Ollama instance via `LAWFIRMAGENT_OLLAMA_URL=http://host.docker.internal:11434/api/generate` — modest isolation benefit, no performance cost, but also modest value given the app has no internet-facing behavior to isolate in the first place. |
| Production Linux + NVIDIA GPU workstation | Use `docker-compose.yml` as-is. This is the strongest version of the "no internet route" guarantee available: the `lawfirmagent_internal` network has `internal: true`, so containers on it have no path to the internet at all — not a firewall rule to configure and remember, a property Docker enforces at the bridge/iptables level. |

## Using docker-compose.yml (Linux + NVIDIA target)

```bash
docker compose up -d --build
docker compose exec ollama ollama pull llama3.1:8b   # first run only — model weights persist in the ollama_models volume
```

App is then reachable at `http://127.0.0.1:5050` on that machine only — not the LAN, not the
internet (`ports: - "127.0.0.1:5050:5050"` binds the published port to the host's own loopback
interface specifically).

**Verify the no-egress claim yourself, don't just trust the config** — same principle already
applied to the native setup (see `TESTING_PLAN.md` §2, and the general "verify + firewall, don't
trust defaults" note in `PRODUCT_DEFINITION.md` §7):

```bash
# From inside the ollama container, this should fail / time out — internal: true means no route out
docker compose exec ollama sh -c "wget -T 5 -O /dev/null https://google.com || echo BLOCKED"

# Confirm the network really has no gateway to the outside world
docker network inspect lawfirmagent_internal | grep -i internal
```

## Why this belongs in the compliance story

This directly strengthens the recurring-security-activity plan already in `PRODUCT_DEFINITION.md`
§7 (vulnerability scanning / pentesting / risk analysis cadence, per the 2026 HIPAA Security Rule
NPRM): a network boundary enforced by the container runtime itself is a stronger, more auditable
control than "we configured a firewall rule and are trusting it stays configured" — worth calling
out explicitly to firm IT/compliance during the Phase 0 review, once real deployment hardware is
chosen.
