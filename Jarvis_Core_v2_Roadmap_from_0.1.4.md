# Jarvis Core v2 — Product Roadmap and Memory Strategy

**Planning baseline:** accepted 0.1.4 checkpoint (`f6f8a5a`, as reported in Git history)  
**Roadmap status:** proposal for approval; no code or repository files changed  
**Strategy:** ship a trustworthy, genuinely useful Jarvis in small accepted increments; make memory an early core capability rather than a late cosmetic feature.

## 1. Executive decision

Start **Memory 2.0 in 0.1.6**, immediately after the narrow **0.1.5 Tool Gateway + first real action** milestone. Deliver basic, durable user-controlled memory in 0.1.6; improve retrieval and context use in 0.1.7. Do **not** wait until 0.3.x or a public beta to introduce memory. Equally, do not attempt cross-device sync, autonomous extraction, and semantic search all in the first memory patch.

**Why this order?** The currently accepted code has one `ConversationContext`, typed `ToolRequest`/`ToolResult` contracts, and delegation slots for `MEMORY`, `ACTION`, `CURRENT_DATA`, and `LONG_TASK`. But `core/memory/`, `core/permissions/`, and `core/tasks/` are placeholder directories. A small Core-authorized tool path first establishes the execution/result pattern that memory read/write operations will rely on. Memory itself should then be a first-class Core service, independent of Realtime Mini or Luna.

The canonical September handoff originally scheduled a tool gateway and memory earlier in the version numbers; the actual development order moved heavily toward voice and delegation. This proposal *restores the intended sequence of dependencies* without pretending the old version numbers are still current.

## 2. What already works and what is missing

| Capability | As of accepted 0.1.4 | Next implication |
|---|---|---|
| Realtime Mini + WebRTC conversation, wake/sleep | Live-tested and accepted | Freeze stable configuration; run voice regressions, avoid speculative audio changes |
| Core/Luna delegation | Guided routing has a working accepted checkpoint | Preserve Core authority; test failures and stale responses |
| Conversation context/referents | Established in Core | Reuse it; do not build another transcript/context owner |
| Typed tool contracts | Already present | Add registry, policy, executor, verification and result feedback |
| Durable memory and user-managed recall | Placeholder / not implemented | Build in 0.1.6–0.1.7 |
| Permissions, audit, account identity, sync | Some contracts, many missing implementations | Start with fail-closed single-user policies; expand before users/accounts |
| Native installer and zero-config onboarding | Not yet a distribution-ready product | Required for private alpha |
| Known microphone noise/barge-in false positives | Reproduced; experimental fixes rolled back | Track as accepted alpha limitation; revisit if real-world severity warrants |

**Baseline housekeeping:** The uploaded ZIP contains `VERSION` and `RELEASE_MANIFEST.json` labeling 0.1.3, and `pyproject.toml` labeling 0.1.2, despite the accepted Git checkpoint being 0.1.4. Do a deliberate metadata reconciliation and add a consistency test in the next narrow milestone; do not overwrite history or assert that the archive proves a particular Git commit (a source ZIP is not Git history).

## 3. Near-term, version-by-version roadmap

The versions below are **proposed scopes**. A normal version advances only when the preceding version passes automated testing and the user's live acceptance. Repairs remain within the same candidate (`repair1`, `repair2`, etc.). Changes in product priorities can reorder unstarted milestones by explicit decision.

### 0.1.5 — Core Tool Gateway & first real action (NEXT)

**Goal:** Jarvis does something real and reports whether it worked, without a model receiving operating-system authority.

**Implementation slices**

1. **0.1.5.1:** Typed Core tool registry, controlled dispatcher, explicit action status and trace IDs. Add an initially restrictive local permission policy. Choose one simple, visible action such as **open an HTTPS website in the user's default browser**. Avoid unrestricted shell or browser automation.
2. **0.1.5.2:** Safe retries/idempotency, typed argument validation, cancellation boundaries, verification, structured audit events, and failure messaging. Confirm that a model's *request* never equals permission.
3. **0.1.5.3:** Wire voice and typed paths through the same Core handler and visible UI result. Add regression tests, reconcile version metadata, and document known limitations.

**Done when:** “Jarvis, open YouTube” can open the intended URL exactly once; rejection and OS failure are reported truthfully; no unauthorized local or network operations occur; existing conversation performance and sleep remain stable.

**Out of scope:** Arbitrary code execution, app-control scripting, account access, purchases, broad automation, and new mic algorithms.

### 0.1.6 — Memory 2.0, phase 1: durable and user-controlled

**Goal:** Jarvis remembers explicitly saved facts and preferences across restarts.

**Implementation slices**

1. Define provider-neutral `MemoryRecord`, storage/repository, and `MemoryService` interfaces. Keep the source of truth in Core, **not** an LLM session, transcript buffer, or vector index.
2. Persist in a transactional, migratable local store (SQLite is a practical candidate). Namespace by account/profile from day one, even if alpha initially has one local profile. Do not casually promise encryption if plaintext SQLite is used during development; put an encryption/security gate before external distribution.
3. Store record type, value, timestamps, provenance/source, user-confirmed vs inferred flag, confidence, retention scope, and supersession history. Protect against duplicate writes and partial/crashed writes.
4. Support explicit **remember / what do you remember / correct or update / forget** operations through voice *and* typed requests. Confirm only completed writes; never claim memory was saved when it was not.
5. Keep memory out of normal raw transcripts by default. No silent retention of secrets or sensitive personal data.

**Done when:** “Remember that I prefer concise answers,” followed by a full restart, then “What response style do I prefer?” works; editing and forgetting work and are verified after restart; user A cannot retrieve user B's memory in isolation tests.

### 0.1.7 — Memory 2.0, phase 2: useful retrieval and control

**Goal:** Relevant memory improves natural conversations without becoming intrusive.

**Implementation slices**

1. Context-aware retrieval with structured and exact/full-text matching first; introduce semantic indexing *only when measured benefits justify its complexity*. Never make vectors the authoritative record.
2. Relevance limits, context-budget caps, provenance, and conflict handling. Avoid dumping the entire store into Mini/Luna prompts.
3. Separate durable facts, projects, preferences, episodic events, and short-lived working context. Do not promote speculative model inferences into known truths.
4. User-review surface within the minimal orb-centered UI: view/edit/delete, memory off, per-record local-only/sync-eligible settings, retention controls.
5. Resume one simple, previously discussed project after restart with correct references and no invented progress. Add test fixtures for hallucinated memories, conflicting statements, forgetting, and recovery.

**Done when:** recall succeeds on a predefined test corpus (target >=90% relevant recall), no cross-user disclosure occurs, no false claims of saved facts occur, and delete/update persist through restart. Track both correctness and retrieval latency.

### 0.1.8 — Current information & browser basics

**Goal:** Jarvis can answer timely questions with a real lookup and source attribution.

- Add a Core-owned read-only search/current-data provider abstraction and one reliable integration, with timeouts and explicit unavailable outcomes.
- Return source metadata and timestamps where available. Make “I looked this up” mean an actual lookup happened.
- Permit opening a selected result via the authorized tool gateway; maintain simple, visible actions first.

**Done when:** current-data questions either produce real sourced results or a truthful failure, without hallucinated citations or extra unauthorized actions.

### 0.1.9 — Account, permissions & device foundation

**Goal:** Establish the identity and security boundary required before real multi-user distribution.

- Authenticate users through a trusted backend; never expose ORVEX provider secrets to clients.
- Bind memory, actions, costs, and devices to the authenticated account; local speaker recognition is *not* authorization.
- Implement approval/confirmation levels, per-device capabilities, audit and device revocation fundamentals.
- Handle sign-in/sign-out, recovery, session expiry, and unauthorized requests safely. Support opt-out/local-only memory selection.

**Done when:** an unsigned user cannot use account-gated Jarvis; cross-account tool/memory access fails closed; revoke/sign-out invalidates subsequent access; action confirmations and audit survive app restart where necessary.

### 0.2.0 — Daily-driver private desktop alpha

**Goal:** A small group can install Jarvis, sign in, speak/type, use a few real features, and report issues without developer assistance.

- Installer/update path, guided microphone setup, recoverable connection errors, startup health checks, robust logs that avoid exposing secrets.
- Keep the current minimalist orb + transcript + text input; deeper settings live inside the orb rather than a dashboard redesign.
- One reliable command, explicit durable memory, real current-data retrieval, account boundary, and stable Core/Luna delegation.
- Test fresh installs, restarts, no-network behavior, microphone failures, multiple sessions, and 30–60-minute use.

**Done when:** a nondeveloper completes setup, can use the end-to-end path on a supported Windows device, and can recover from ordinary failures without the terminal.

## 4. Expansion roadmap (provisional; subject to actual alpha feedback)

| Version / phase | Priority | Expected capability | Release gate |
|---|---|---|---|
| **0.2.1** | Productivity | Reminders and a first calendar integration behind permissions | Correct reminders; no accidental schedule changes; verified external state |
| **0.2.2** | Memory sync | Selective encrypted sync, device enrollment/revocation, conflict resolution, recovery | No cross-account leaks; local-only memory never syncs; restore after device replacement |
| **0.2.3** | Computer & browser skills | Broader OS/app controls; restricted automation; guarded failure recovery | Idempotent safe actions, explicit approvals, no unrestricted shell execution |
| **0.2.4** | Personalization | Editable personality traits, response length separately controlled; orb-inside settings and memories | Personalization does not change authority or accidentally increase verbosity |
| **0.2.x** | Durable tasks | Background tasks, retries, inspection, cancellation, resource budgets | Restart-safe execution; no stale result or duplicate side effect |
| **0.3.0** | Invite-only beta | Multi-user operations, telemetry/privacy, updates, support, security review, usage metering | Supported-device reliability; all critical issues resolved |
| **0.4.0** | Public beta / commercial readiness | Server-side entitlement and quota enforcement, billing, privacy/terms, support workflows | Costs controlled and accounts secure; onboarding and abuse tests pass |
| **0.5.x** | Product breadth | Expand integrations, device support, voice tuning informed by feedback | Each capability proven via tests, not demonstrations only |
| **1.0.0** | General availability | Trustworthy assistant users can depend on | Explicit launch gates below all met |

**Not required to ship early:** full autonomy, local/offline LLM, mobile parity, Iron Man HUD, complex speaker biometrics, perfect microphone noise rejection. They can remain separate later tracks. Keep the public ORVEX product distinct from the separate personal/offline Jarvis Local project.

## 5. Memory architecture to preserve now

```text
User speech / typed text
          |
    Conversation Core (authoritative turns / context)
          |
   Delegation / capability request
          |
     Core MemoryService  <---- Account/profile/permission policy
          |
  Structured repository (local-first, transactional, migratable)
          |
  Exact/full-text index; optional semantic index (derived only)
          |
  Relevant, scoped memory excerpts -> Mini / Luna context
          |
  Answer or verified write/update/delete + audit event
```

**Critical policies**

- User controls what is remembered; first release starts with explicit memory instructions and reviewable saved items.
- Secrets/credentials belong in a separate secure vault, never ordinary promptable memory.
- Store minimal facts, evidence and provenance; **not** unbounded audio/transcripts. A user's “forget” request must delete the actual record and indexes, subject to clearly stated backup retention rules.
- Provider switching must not lose memory or create two sources of truth. Memory access uses Core interfaces; providers only see relevant approved excerpts.
- Keep data local-first where practical, yet be candid that cloud reasoning may receive selected memory text for a response. Later sync must be opt-in/selective and encrypted, with account and device revocation.
- Cross-device sync and memory *are different milestones*. Start with single-device persistence, later add sync without rewriting the record schema.
- Maintain user/profile scoping even before household/multi-speaker support. A voice match alone never authorizes disclosure or action.

## 6. Standard development/acceptance process — every milestone

1. **Baseline:** Confirm last accepted commit, clean Git state, version metadata, and exact project snapshot. Compare relevant V1 lessons without copying V1 wholesale.
2. **Patch:** One focused version/repair; deliver self-contained patch ZIP, root-safe apply script, patch notes, testing guide, issue record, updated tests.
3. **Automated checks:** Focused unit tests, complete test suite, diagnostics, desktop static checks and build. No tests that unexpectedly play sound in routine CI.
4. **Live acceptance:** Exact spoken prompts and expected results. Always repeat the project's five standard wake/sleep/regression phrases (below) plus milestone-specific tests.
5. **Reliability review:** Verify real state changes, result attribution, undo/recovery, privacy, failure behavior, cancellation, cost, and voice-quality/latency regression. Measure against accepted 0.1.4 rather than optimizing a synthetic benchmark alone.
6. **Accepted only:** Remove exact patch installers/ZIPs/backup artifacts, inspect `git status`, rerun checks and commit. Do not progress on a failing candidate.

**Five recurring spoken checks:**

1. “Hey Jarvis, what planet is called the Red Planet?” → wakes and answers Mars in the same utterance.
2. “Go to sleep, Jarvis.” → sleeps without an unnecessary response.
3. “Jarvis, what's seventeen times six?” → wakes and answers 102.
4. “Thanks, Jarvis.” → stays awake and acknowledges naturally.
5. “Thanks Jarvis, that's all.” → sleeps silently.

**Release quality gates (targets to test, not guaranteed measurements):**

- **Trust:** zero unintended privileged actions, zero cross-account disclosure, zero false reports of verified execution/memory writes.
- **Conversation:** direct-turn speed and voice naturalness must not regress materially against accepted 0.1.4; use matched local runs and report p50/p95, not cherry-picked screenshots.
- **Routing:** routine questions stay on Mini, complex requests route to Core/Luna with valid results, and failed Core responses never masquerade as successful.
- **Durability:** save/restart/retrieve/update/delete and crash/retry behavior verified on persistent resources.
- **Distribution:** install/login/device setup tested on a clean Windows environment before private alpha; protect credentials and provider cost in backend, not local UI flags.
- **Known issues:** record microphone noise interruptions, but do not reopen risky audio rewrites without evidence the issue blocks actual adoption.

## 7. Decision log / next concrete step

**Recommendation to approve now:**

- Keep accepted 0.1.4 (`f6f8a5a`) as the voice/delegation baseline; do not replay rejected 0.1.4.2 voice experiments.
- Build 0.1.5 first as **a Core-authorized real action** (an HTTPS URL opener is an appropriate first candidate), not a broad automation release.
- Start durable memory immediately next, in **0.1.6**, and make retrieval genuinely useful in **0.1.7**, before opening the product to a larger audience.
- After the roadmap is approved, convert this file into the repository `docs/ROADMAP.md` via the normal patch workflow rather than editing the user’s accepted snapshot out of band.

*This roadmap is a planning artifact, not a new accepted Jarvis version or a promise of dates. The master handoff remains canonical for non-negotiable architectural and security rules unless the user explicitly changes them.*
