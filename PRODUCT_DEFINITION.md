# LawFirmAgent — Product Definition

## 1. Problem Statement

A nurse paralegal at a medical malpractice firm spends the majority of her time manually reading thousands of pages of medical records per case (charts, nurses' notes, discharge summaries, imaging reports, faxed outside records, some handwritten) to build chronologies and flag facts relevant to standard-of-care and causation arguments. This is slow, repetitive, and doesn't scale with case volume. The records are PHI, so any tooling must keep data under the firm's control.

**Goal:** build an on-premise, LLM-assisted system that does the first-pass extraction, chronology-building, and flagging work — so she spends her time reviewing and judging instead of reading and transcribing.

**Non-goal:** replacing her judgment. See §5 — this is an augmentation tool, not an autonomous paralegal.

## 2. Feasibility Verdict

**Feasible as an assistive/augmentation tool. Not feasible — and not safe — as an autonomous replacement.**

The limiting factor isn't hardware or model size, it's hallucination rate on clinical text. Published 2025-2026 benchmarks measured LLM hallucination rates on clinical case summarization at **43–64%** without mitigation techniques (grounding/citation-forcing brings this down but doesn't eliminate it), and medical hallucinations are disproportionately dangerous because they tend to come with *high model confidence* — the output doesn't look uncertain, it looks authoritative. In a medical malpractice case, a fabricated or misdated clinical fact that makes it into a chronology or filing is a sanctions and malpractice risk for the firm, not just an embarrassment (see §7 on ABA Formal Opinion 512 and 2025-2026 sanctions cases where attorneys were fined and referred to disciplinary bodies for unverified AI output in filings).

So the right framing is: **the LLM does recall, retrieval, and drafting; she does verification and judgment.** Every fact the system surfaces must be traceable to a specific page/line in a specific source document, and nothing it produces is used until she's checked it against the source. Under that model, this is very achievable with current local/open-weight models, and the productivity win is real — firms using AI-assisted medical record review report 60–90% reductions in first-pass review time in case studies, though independent third-party benchmarks are still thin, so treat those numbers as directional, not guaranteed.

## 3. Does It Need to Run Fully On-Prem?

Yes, and this is a feature, not just a constraint. Two reasons:

1. **HIPAA / Business Associate obligations.** The firm is a HIPAA Business Associate the moment it holds ePHI (which it already is, handling medical records for malpractice litigation). Every additional vendor that touches that data — including a cloud LLM API — is a new subcontractor Business Associate requiring its own BAA, risk assessment, and audit trail. Running the model entirely on hardware the firm controls, with no PHI ever leaving the building or hitting a third-party API, sidesteps that expansion of the compliance surface entirely. This is the single biggest reason to go local rather than "just use a HIPAA-eligible cloud API."
2. **Bar/ethics duty of confidentiality.** Independent of HIPAA, attorneys have a professional confidentiality duty over client/case data. Local-only inference is the cleanest way to satisfy both regimes at once.

"On-prem" in practice means a dedicated workstation (or small server) physically in the firm's office, on an isolated network segment with no general internet route, running the model and the document pipeline locally. It does not need to be literally her day-to-day laptop — in fact it shouldn't be (see §6).

## 4. Where Does the LLM Actually Live?

Recommend a **dedicated workstation**, not her everyday laptop:

- Keeps the PHI-handling environment separate from email/browsing/other software (smaller attack surface, easier to firewall, easier to audit).
- Lets you size the hardware for the model rather than being constrained by whatever machine she already has.
- Survives her laptop being repaired, replaced, or lost.

**Hardware guidance (2026):**

| Tier | Hardware | Model capability |
|---|---|---|
| Minimum viable | 32GB RAM + single 24GB-VRAM GPU (RTX 4090) | 8B–32B models comfortably, 70B at heavy quantization/offload |
| Recommended | RTX 5090 (32GB VRAM) or Mac Studio M-series (64–128GB unified memory) | 70B-class models at good quantization, or multiple mid-size models loaded concurrently |
| Not needed | Multi-GPU server / datacenter cards | This is single-user, not high-throughput — don't over-provision |

A 70B dense model at Q4 quantization needs roughly 40GB of VRAM/unified memory; a single RTX 5090 or an Apple Silicon Mac with enough unified memory both clear that bar. For a single user doing document-grounded extraction (not open-ended reasoning), a well-chosen 32B model is often good enough and considerably cheaper/faster — see §5 for why the task shape matters more than raw parameter count here.

Also budget: NVMe storage (1–2TB — case documents plus multiple model weights add up), full-disk encryption, and a UPS (a bad shutdown mid-ingestion of a case's documents is a headache you don't want).

## 5. Model Selection

Because the core task is **retrieval-augmented extraction over a fixed, provided set of documents** — not open-ended reasoning or novel writing — a well-designed RAG pipeline matters more than chasing the largest model. Recommendations:

- **Primary reasoning/drafting model:** Llama 3.3 70B or Qwen 2.5/3 32B–72B class, run via Ollama or llama.cpp. Qwen's larger context window (100K+ tokens) is a genuine advantage here — case document sets are large, and being able to keep more retrieved context in-window per query reduces stitching errors when building a cross-document chronology.
- **Vision/OCR fallback model:** A vision-language model (e.g., Qwen2.5-VL) for scanned faxes and handwritten notes that break traditional OCR. Expect handwriting recognition to be imperfect — flag low-confidence extractions explicitly rather than silently guessing.
- **Embedding model:** A local embedding model (e.g., BGE-large, nomic-embed-text) for the vector store — keeps the whole pipeline offline, no calls to an embeddings API.

Don't pick one model and stop — plan to re-evaluate every 6–12 months. This space moves fast, and being tied to Ollama/llama.cpp-compatible open-weight models rather than a vendor API keeps you free to swap in a better model later without re-architecting.

**Hallucination rate varies a lot by model, and not in a way you'd guess from parameter count.** On a 2025 clinical-vignette benchmark (300 doctor-written cases), several well-regarded open models — including Qwen-2.5-72B, DeepSeek, and Gemma-2-27B — showed significantly *higher* odds of hallucination than GPT-4o. Bigger/newer doesn't automatically mean more reliable on clinical text specifically. Two implications:

1. **Run local reasoning models in "thinking" mode, not fast/instruct mode.** Across model families, extended-thinking/reasoning mode roughly halves hallucination rates (e.g., one tracked model went from 9.4% to 5.1% with thinking enabled). Qwen3 and DeepSeek-R1 both support a local reasoning mode — use it for extraction, even though it's slower.
2. **Benchmark 2–3 candidate models against a small hand-verified sample of her actual documents before committing to one for the pipeline.** Published leaderboards are a starting point, not a substitute for testing on your real document types (typed EHR exports read very differently than scanned faxes or handwritten notes).

**Grounding is the mitigation for hallucination**, and it's non-negotiable: every extracted fact, date, or summary line the system outputs must carry a citation back to the exact source document and page/line it came from. This does three things — it lets her verify quickly instead of re-reading everything, it turns "trust the AI" into "spot-check the AI," and it gives you an audit trail if a chronology's provenance is ever questioned. Note that citation/quote fidelity is itself one of the *worst*-performing task types even for frontier models (~12% hallucination rate even with reasoning enabled) — which is exactly why grounding alone isn't enough and needs the independent verifier pass below.

**A second, independent verification pass catches what grounding alone misses.** The strongest practical mitigation for this specific task is a generator/verifier split: one pass extracts facts with citations (as above), and a second, separate pass — ideally a *different* model, with no memory of the first pass's reasoning — is given only the claimed fact and the source document, and asked one narrow question: "does this document actually support this claim, yes/no, quote the supporting text." Verification is a much easier, higher-accuracy task for an LLM than generation is, which is why splitting the work helps. Using two different models (e.g., extract with Qwen3, verify with Llama 3.3 or DeepSeek-R1) is stronger than having one model check its own work, since two different models are less likely to share the same blind spot. Published results on this pattern (Chain-of-Verification / proposer-checker architectures) show real but partial gains (one study: F1 0.39→0.48) — it reduces, but does not replace, her manual spot-check. See the updated architecture in §6.

## 6. Architecture

```
[ Intake ]                [ Processing Workstation — isolated network, no internet egress ]
Case docs (PDF/            │
scan/fax/EHR export)  ───▶  1. Ingestion & OCR
                              - Docling / Unstructured / marker-pdf for layout-aware parsing
                              - Vision-model fallback for scans/handwriting
                              - Low-confidence extractions flagged, not silently accepted
                            │
                            2. Chunking + local embedding → local vector store (Qdrant/Chroma)
                            │
                            3. Retrieval-augmented query layer
                              - Chronology builder: pulls dated events across all docs in a case
                              - Entity/provider extractor
                              - Topic/keyword flaggers (e.g., specific meds, complications,
                                deviations attorneys ask about)
                              - Cross-document contradiction/gap detector
                            │
                            4. Extraction pass — Model A (reasoning/thinking mode)
                               generates draft output, every claim tagged with source
                               doc + page/line citation
                            │
                            5. Verification pass — Model B (different model, fresh
                               context, no memory of Model A's reasoning): given each
                               claimed fact + the cited source text only, answers
                               "does the document actually support this, yes/no,
                               quote the text." Unconfirmed claims are flagged
                               low-confidence, not dropped or silently kept.
                            │
                            6. Review UI (Open WebUI or lightweight custom app)
                              - She reviews every item (low-confidence ones surfaced first),
                                edits, accepts/rejects each
                              - Nothing exported/finalized without her sign-off
                            │
                            7. Audit log: every document accessed, every query run,
                               every output generated, every verification result,
                               every edit made, timestamped
```

Everything to the right of "Intake" runs on the isolated workstation. No component makes outbound internet calls once set up (model weights and embedding models are downloaded once during setup, then the network can be locked down).

The extraction/verification split (steps 4–5) is the practical answer to "can we reduce hallucination by having it read each file more than once" — see §5 for why an independent verifier pass, not just re-running the same model, is the stronger version of that idea.

## 7. Compliance & Legal Guardrails

These aren't optional hardening — they're the actual point of doing this on-prem, and they need firm sign-off, not just a home-lab setup:

- **Get the firm's IT/compliance function (and a supervising attorney) to formally review and approve this before it touches a live case.** This is a system that will process client PHI in the course of legal representation. Even though it's built by a spouse, once it's used for firm work it's the firm's system, subject to the firm's HIPAA obligations, malpractice insurance considerations, and bar supervision duties (ABA Formal Opinion 512 explicitly puts supervisory responsibility for AI tool use on attorneys). Treat firm approval as a hard prerequisite, not a formality — this is the single most important non-technical step.
- **HIPAA technical safeguards:** AES-256 encryption at rest, TLS 1.2+ for anything in transit (even internal), MFA on the workstation and any review UI, role-based access limited to her (and IT admin as needed), automatic session timeout, full audit logging of access and queries.
- **No internet egress from the processing workstation** post-setup — firewall rule, not just policy. This matters concretely, not just in theory: local testing found that Ollama ships a "cloud" feature (remote inference + web search) that is *enabled by default* in the current version, controllable via an `OLLAMA_NO_CLOUD=1` setting. An empirical check (monitoring live network connections during real requests) showed no external connections during normal local use, but the fact that a locally-run tool defaults to having an outbound-capable feature at all is exactly why the firewall rule has to be the real control, not trust in any given tool's default configuration — defaults change between versions, and every component in the stack (inference server, OCR tooling, embedding model, vector DB) needs the same "verify it's not phoning home, then block it at the network level anyway" treatment before this touches PHI.
  - **Stronger version of this control, for a Linux + NVIDIA GPU deployment specifically:** run everything in containers on a Docker network with `internal: true`, so "no route to the internet" is enforced structurally by the container runtime rather than by a firewall rule someone has to remember to keep in place. See `DEPLOYMENT.md` and `docker-compose.yml` — investigated 2026-07-22. Important caveat: this does **not** apply to an Apple Silicon deployment (including the Mac Studio option in §4) — Docker Desktop/Apple's own `container` tool cannot pass the Metal GPU through to a container as of 2026, so a containerized Ollama would fall back to CPU-only inference (~3-5x slower). On Apple Silicon hardware, keep running Ollama natively (as this project already does) and rely on the firewall-rule approach instead — full details and the reasoning in `DEPLOYMENT.md`.
- **Physical security:** locked office/room, disk encryption, encrypted backups, no unencrypted PHI on removable media.
- **Retention/deletion policy** aligned with the firm's existing litigation-hold and records-retention rules — this system shouldn't become an uncontrolled second copy of case files that outlives the case.
- **Bar/ethics duty of independent verification** (ABA Formal Opinion 512, and the wave of 2025–2026 sanctions cases for unverified AI citations/facts in filings): nothing the system produces goes into a filing, demand letter, or attorney work product without being independently verified against the source document by a human. Build this into the workflow (e.g., a UI that won't let her "export" a chronology item without an explicit per-item confirmation), don't just rely on it as a stated policy.
- **Incident response plan** for the (unlikely but real) case of a breach or misconfiguration — who gets notified, how fast, per the firm's existing breach-notification obligations.
- **Recurring security activities, not just a one-time Phase 0 gate.** HHS's proposed 2026 HIPAA Security Rule update (NPRM published December 2024, not yet finalized as of this writing) eliminates the current "addressable vs. required" distinction — MFA, encryption, vulnerability scanning, and incident response planning move from optional-with-a-workaround to flatly mandatory for every covered entity and business associate. It also signals specific cadences worth adopting now rather than waiting for the rule to finalize: **vulnerability scanning at least every 6 months** (internal and external), **penetration testing at least annually**, and **risk analysis at least annually and after any material environment change** (a new model, new hardware, a new integration — not just once at initial approval). See `RESEARCH_NOTES.md` for the full research behind this addition.

## 8. What Gets Automated vs. What Stays Human

**Automatable (first-pass, always cited, always reviewed):**
- Ingesting and normalizing mixed-format documents (PDFs, scans, faxes)
- Building a draft chronological timeline of dated medical events across the full document set
- Extracting providers, facilities, dates of treatment, medications, procedures
- Flagging documents/passages matching attorney-specified topics (e.g., mentions of a specific drug, complication, or deviation from protocol)
- Surfacing possible contradictions or gaps between documents (e.g., a note referencing a test result that doesn't appear elsewhere in the record)
- Producing a draft narrative summary per document or per case as a starting point for her to edit

**Stays human (not automatable, and shouldn't be attempted):**
- Final judgment on standard-of-care breaches and causation
- Weighing clinical significance / expert credibility
- Deciding what actually goes in a chronology or filing
- Sign-off on anything leaving the system

Bias the automated layer toward **recall over precision** — it's much better for the system to over-surface candidate facts/passages for her to reject than to quietly filter something out that turns out to matter. A missed smoking-gun fact is a worse failure mode than an extra false positive she spends ten seconds dismissing.

## 9. Phased Rollout

1. **Phase 0 — Approval.** Firm IT/compliance and a supervising attorney review and sign off on the architecture, BAA/compliance posture, and use policy before any live case data touches it.
2. **Phase 1 — Pilot on a closed case.** Run the full pipeline on a case that's already resolved. Audit every generated fact against source documents by hand to measure real accuracy/hallucination rate on your actual document types (not just published benchmarks).
3. **Phase 2 — Shadow mode on a live case.** Run alongside her normal process, not instead of it, and compare. Refine prompts, retrieval, and the review UI based on where it actually saves time vs. where it creates rework.
4. **Phase 3 — Primary workflow.** Becomes her default first pass, with the human-verification step remaining mandatory. Track time saved and spot-check accuracy on an ongoing sample.
5. **Phase 4 — Maintenance.** Quarterly model re-evaluation, security/compliance review, and audit log review.

## 10. Success Metrics

- Time from case intake to completed reviewed chronology (target: material reduction vs. baseline, e.g. days → hours for first-pass extraction).
- Verified accuracy rate on a random audit sample of generated facts/citations (should be tracked continuously, not just at pilot).
- Zero PHI egress events (firewall/audit log confirms no outbound data).
- Zero instances of unverified AI-sourced facts reaching a filing or client-facing document.

## 11. Key Risks

| Risk | Mitigation |
|---|---|
| Hallucinated/misdated clinical facts (measured 43–64% on clinical summarization without mitigation) | Citation-grounding + independent second-model verification pass (§5, §6) + mandatory human verification before any use |
| Missed evidence (false negatives) | Bias retrieval/flagging toward recall; treat over-surfacing as the safe failure mode |
| Chain-of-custody / evidentiary integrity questions | Immutable audit log of ingestion, queries, and edits |
| Becomes unsupported "shadow IT" if not formally adopted by the firm | Get explicit firm IT/compliance/attorney sign-off before live-case use (see §7) |
| Model quality drifts or better options emerge | Keep the pipeline model-agnostic (Ollama/llama.cpp-compatible), re-evaluate every 6–12 months |
| Firm liability if the system leaks PHI or produces an unverified error that reaches a filing | Treat as the firm's system once in use, not a personal project — same insurance/liability posture as any other firm technology |

## 12. Open Questions to Resolve Before Building

- Does the firm already have a policy on staff-introduced AI tools? Does this need to go through a formal vendor/tool approval process even though it's "homegrown"?
- What's the actual document mix (typed EHR exports vs. scanned faxes vs. handwritten notes)? This determines how much OCR/vision-model investment is needed up front.
- Who else at the firm would use this if the pilot succeeds — is this staying single-user, or should it be architected (even if not built yet) to support more than one paralegal later?
- What's the firm's existing retention/destruction policy for case documents, and how does this system's local storage need to comply with it?

## Sources Consulted

- [Law Firm HIPAA Compliance: Requirements, Checklist, and Best Practices](https://www.accountablehq.com/post/law-firm-hipaa-compliance-requirements-checklist-and-best-practices)
- [HIPAA Business Associate Status for Law Firms](https://www.accountablehq.com/post/hipaa-business-associate-status-for-law-firms-compliance-requirements-explained)
- [HIPAA-Compliant Private LLMs: 5 Architectures](https://petronellatech.com/blog/hipaa-compliant-private-llms-5-architectures-2026/)
- [ABA Formal Opinion 512: The Paradigm for Generative AI in Legal Practice](https://library.law.unc.edu/2025/02/aba-formal-opinion-512-the-paradigm-for-generative-ai-in-legal-practice/)
- [AI Hallucination Legal Cases: A Sanctions Tracker (2026)](https://gc.ai/blog/ai-hallucination-legal-cases)
- [Local LLM for legal documents: what works, what doesn't (honest review)](https://dev.to/trinh_trankhanhduy_3429/local-llm-for-legal-documents-what-works-what-doesnt-honest-review-20d7)
- [Local AI for Lawyers: Private Legal Research Setup](https://localaimaster.com/blog/local-ai-lawyers)
- [Local LLM Hardware Requirements in 2026](https://overchat.ai/ai-hub/llm-hardware-requirements)
- [Air-Gapped AI Deployment: Complete Offline Setup Guide (2026)](https://localaimaster.com/blog/air-gapped-ai-deployment)
- [Healthcare OCR Tools: The Best AI Document Processing for Medical Records in 2026](https://www.llamaindex.ai/insights/healthcare-ocr-tools)
- [Stop Feeding Your RAG Garbage PDFs: Docling for Physician Developers](https://www.doctorswhocode.blog/blog/docling-rag-tutorial)
- [Tavrn: Top AI Software for Personal Injury Practices (2026)](https://www.tavrn.ai/blog/top-ai-software-for-personal-injury-practices)
- [Dodonai: AI Medical Record Review Software](https://www.dodon.ai/use-cases/medical-record-review/)
- MedRxiv (2025), clinical case summarization hallucination rate study (43–64% depending on mitigation)
- [Multi-model assurance analysis showing LLMs are highly vulnerable to adversarial hallucination attacks during clinical decision support — Nature Communications Medicine](https://www.nature.com/articles/s43856-025-01021-3)
- [LLM Hallucination Index 2026: Why Claude 4.6 Sonnet Dominates](https://medium.com/@anyapi.ai/llm-hallucination-index-2026-why-claude-4-6-7b2d13ed9f0c)
- [AI Hallucination Rate Benchmarks 2026: 5-Model Study](https://www.digitalapplied.com/blog/ai-model-hallucination-rate-benchmarks-2026-study)
- [Self-Consistency Hallucination Detection](https://www.emergentmind.com/topics/self-consistency-based-hallucination-detection)
- [Chain-of-Verification (CoVe) Framework](https://www.emergentmind.com/topics/chain-of-verification-cove)
- [MARCH: Multi-Agent Reinforced Self-Check for LLM Hallucination](https://arxiv.org/html/2603.24579)
