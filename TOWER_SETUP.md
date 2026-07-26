# Feasibility: dedicated "tower" + private wired link to her laptop

Prompted by: "a little desktop tower or something she can USB connect to (or any wired connection),
where the app runs exclusively on the tower and isn't connected to the internet. Is this an
acceptable idea? Is it doable?"

**Verdict: yes — sound, doable, and actually the strongest version of this project's core security
requirement.** This isn't a novel or risky idea; it's a well-established pattern (a dedicated
compute appliance reached over a private point-to-point link), and it maps directly onto what
`PRODUCT_DEFINITION.md` §3/§4 already recommends — a dedicated workstation, physically separate
from her everyday laptop, on an isolated network segment with no general internet route. This makes
that concrete and buyable rather than abstract.

## The architecture this implies

Two machines, two different jobs:

- **The tower**: a headless (no monitor/keyboard needed day-to-day) Windows PC running Ollama + the
  Flask backend. Does all the actual work — text extraction, model inference, holds the case
  documents. Never touches the internet, ever, not even briefly.
- **Her laptop**: her everyday Windows machine. Runs the Electron app (`electron/` in this repo),
  in `remote` mode — it doesn't spawn anything locally, it just opens a window pointed at the
  tower's address over the private link. She gets the "click an icon, it just works" experience;
  the tower does the heavy lifting.

This is *why* Electron's `local`/`remote` mode split (built and tested — see `TEST_RESULTS.md`,
"Electron conversion") matters here beyond just being a nice-to-have: switching between "everything
on one machine" and "this machine is a thin client to that one" is a one-line config change
(`LAWFIRMAGENT_MODE=remote`, `LAWFIRMAGENT_REMOTE_URL=http://<tower-ip>:5050`), not a rewrite.

## The "wired connection, no internet" part — confirmed sound

The right-sized version of this is a **direct Ethernet cable between the tower and her laptop, with
no router in between at all** — not connected to her home/office network, not connected to a switch,
just a cable straight from one machine's network port to the other's. This is a standard, well-worn
pattern (often called a "direct cable connection"), not something unusual:

- Modern network adapters auto-negotiate ("auto-MDIX"), so an ordinary Ethernet cable works — no
  special "crossover" cable needed.
- Since there's no router to hand out addresses, each machine gets a manually-assigned static IP on
  the same subnet (e.g. tower = `192.168.50.1`, laptop = `192.168.50.2`), configured in Windows'
  network settings in a couple of clicks.
- **Critically: leave the default gateway blank on both ends.** This is the concrete, structural
  version of the "no internet route" requirement — not a firewall rule to configure and maintain,
  but the absence of any path out at all. Even if something on the tower tried to reach the
  internet, there's nowhere for that traffic to go.
- If her laptop doesn't have a built-in Ethernet port (common on thin, modern Windows laptops), a
  small USB-to-Ethernet adapter (a few dollars, sold everywhere) is the practical way to make the
  "wired connection" happen — this is likely what "USB connect" was picturing, and it's the
  simplest, most reliable option. (Plain USB-C networking/tethering between two arbitrary PCs is
  less standardized and more prone to driver quirks — recommend the USB-to-Ethernet-adapter +
  plain Ethernet cable path over that.)

**For genuine air-gapping, the tower's WiFi and Bluetooth should be disabled in Device Manager, not
just left unconnected** — software-disabled is good, but the strongest version is buying a machine
that doesn't have wireless hardware installed in the first place (many plain business-desktop
towers ship this way by default, unlike laptops/NUCs, which almost always include WiFi). This is a
genuine advantage of a desktop tower over a mini-PC/NUC form factor for this specific use case.

## Hardware recommendation

Current (2026) options, researched fresh rather than assumed, spanning a few price/performance
tiers — this directly extends the hardware-tier table already in `PRODUCT_DEFINITION.md` §4:

| Option | Approx. price | What it gets you |
|---|---|---|
| Small-form-factor tower + RTX 4060 Ti (16GB) | ~$900-1,200 | Widely available prebuilt (HP, Best Buy, etc. all sell mini-tower configurations with this card) — comfortably runs 7B-13B models fast, a real step up from this dev laptop |
| Framework Desktop (128GB unified memory) | ~$2,000 | Runs 70B-class models at 20+ tok/s — the best "one box, no assembly" option if she might eventually need a bigger/smarter model |
| Mac Mini M4 Pro (64GB) | ~$2,000 | Compact, silent, ~30W — runs 70B at 10-15 tok/s, comparable to today's 8B-on-this-laptop speed but a much smarter model; only relevant if "tower" doesn't have to mean Windows specifically |

**Recommendation: the RTX 4060 Ti mini-tower tier.** It's the cheapest of the three, most directly
matches "a little desktop tower," is a normal Windows PC (matching the target platform decision
already made), and — per the hardware-scaling discussion in this project's history — a discrete
GPU's memory bandwidth is what actually drives real inference speed gains, not raw size. This
class of card comfortably outperforms today's dev-laptop speeds (~15 tok/s) for the current 8B
model, with real headroom to move up to a 13B-class model later without a hardware change.

## What needs to be true on the tower, software-wise

- **Ollama**: confirmed (researched fresh) that Ollama's Windows installer sets it up as a native
  background service that starts automatically on boot — no manual `ollama serve`, no login
  required, matching the "power it on and it's just ready" requirement. Still needs
  `OLLAMA_NO_CLOUD=1` set explicitly (same reasoning as the existing macOS LaunchAgent config) — a
  Windows environment-variable-for-a-service equivalent, not yet built, is on the list below.
- **The Flask backend**: needs the equivalent of a boot-time auto-start on Windows (a scheduled
  task set to run at startup, or registered as a Windows service) — not yet built; this project's
  Windows-specific packaging (PyInstaller build of the backend) is already flagged as an open item
  in `DESKTOP_PACKAGING.md`.
- **Windows Firewall on the tower**: restrict the Flask/Ollama ports to only the private link's
  network adapter, not "all networks" — defense in depth even though there's no gateway to route
  through anyway.
- **Client pairing (built 2026-07-21, see `webapp/pairing.py`)**: this activates automatically the
  moment `LAWFIRMAGENT_BIND_HOST` is set to something other than `127.0.0.1`/`localhost` for tower
  exposure — no separate flag to remember. The Electron client generates a random key on its own
  first launch and attaches it to every request; the tower has no paired key on its own first boot,
  so whichever key arrives first gets permanently trusted, and every later request must match it
  exactly. This is a real guarantee specifically because of the point-to-point cable topology above
  (nothing else can reach the tower before the laptop does) — it authenticates "a device holding
  this key," not the laptop's hardware, so it isn't a substitute for the firewall scoping above.
  **Re-pairing** (e.g. the laptop is replaced): delete `paired_client_key.token` from the tower's
  app-data directory and restart both apps while the two machines are cabled together in isolation
  again — the same discipline as the original setup, since whichever device reaches the tower next
  after that file is deleted becomes the new trusted one.

## Net assessment

This is a good idea, not just an acceptable one — it's a stronger, more literal version of the
"dedicated workstation, isolated network segment" requirement this project already committed to,
and it resolves a real tension the plain single-laptop approach had (running a multi-GB model +
Ollama on her actual everyday laptop, competing with everything else she uses that machine for).
The main remaining work is the same Windows-packaging gap already tracked in
`DESKTOP_PACKAGING.md` (a PyInstaller backend build, boot-time auto-start, all untestable without
real Windows hardware in hand) — nothing about the tower/networking idea itself is a blocker.
