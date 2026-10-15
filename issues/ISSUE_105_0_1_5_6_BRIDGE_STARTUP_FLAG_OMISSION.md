# ISSUE 105 — Browser-bridge launch failed on wake

Observed: new 0.1.5.6 browser-bridge A/B mode raised an ASGI RuntimeError upon wake;
Core Luna required overlap and delegation orchestration.

Root cause: the mode was added to MODELS and the Luna flag but omitted from overlap
and PCM-trim selection sets in `scripts/realtime_ab.py`.

Resolution: unify overlap and PCM-trim flag predicates against validated mode
prefixes and exercise launch environment contracts for all registered modes.

Status: automated validation expected; LIVE TESTS PENDING.
