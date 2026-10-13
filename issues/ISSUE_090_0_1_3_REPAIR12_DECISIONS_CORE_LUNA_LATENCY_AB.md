# ISSUE 090 — 0.1.3 Repair12: Decisions route-speed comparison under real Core/Luna

## Repair11 evidence

On six user-spoken turns first audio from speech end was 1,894, 1,943, 1,411, 1,395, 1,886, and 1,716 ms. Silent Mini route time was ~635–1,084 ms; private PCM prewarming itself was much quicker. The user wants ordinary, already-awake direct responses near 500–800 ms, without corrupting Core authority, voice naturalness, or reliable wake/sleep transitions. The previous standalone Decisions benchmark (~214 ms) did **not** include speech transcription; an individual quick API call cannot be treated as an end-to-end win.

## Hypothesis

Text-based Decisions, started immediately after transcript arrival, may complete before the Mini silent route decision. A viable speed gain would be at most the **positive** difference between when Mini could authorize and when Decisions could have decided, additionally constrained by audio readiness. The route might also disagree, refuse, fail, arrive too late, or require more context. None of these savings are guaranteed and no Decisions-authorized first audio has been measured yet.

## Scope

- Added one opt-in `mini-overlap-luna-decisions-shadow` mode using the **same** model, Core/Luna provider orchestration, audio path, tool dry-run settings, reasoning policy, and independent Mini routing as `mini-overlap-luna`. Only the separately billed, Core-side Decisions observer is enabled in the new arm.
- Kept the original Decisions-only experiment, Mini baseline, all sleep evidence rules, cancellation, PCM gate, and Core permissions unchanged. Decisions predictions never authorize playback, tools, sleep, or delegation.
- Added a bounded, one-per-turn `[Jarvis Repair12 A/B]` log after actual first-audio arrives, with transcript delay, Decisions request latency, estimated total route readiness, Mini route, possible headroom, and disagreement; never logs transcript text in that row. A separate offline local report summarizes baseline vs shadow medians/p90 and explicitly distinguishes hypothetical headroom from observed audio.
- This is an **instrumented A/B test**, not an early-authorization rollout. Do not advertise a latency win yet.

## Validation and safety gates

- Verify baseline and shadow run with identical actual Core/Luna settings. All actions dry-run. Never promote Decisions results to authority based on synthetic tests alone.
- Verify matching sleep handling, plain thanks, significant Core delegation, current-information/memory requests, and interruptions. Review all disagreements, particularly sleep and memory route failures. An HTTP error never becomes an authorization.
- Collect >=20 already-awake, direct turns **per arm** with similar prompts and network conditions, excluding wake and Core/Luna turns from direct latency. Capture median and p90 first audio, Mini route, Decisions readiness, classifications, errors, and additional costs.
- Require user live approval prior to cleanup and Git commit. If A/B suggests material safe headroom, design a separate Repair13 candidate that can actually use Decisions while retaining Core authority and tested failure handling.

## Limitations

- The shadow call adds cost and network demand; it can slightly change actual latency in the experimental arm.
- The speech-end-to-Decisions-ready metric is estimated as renderer-reported speech-end→transcript + host-observed request duration. It is not clock-synchronized with actual client playback and should be interpreted as approximate.
- Route agreement with Mini isn't ground truth. Some Mini route categories are coarse (e.g., direct vs memory/current-data distinctions), and audio-ready latency remains independent.
