# ISSUE 073 — Unsafe to release pre-tool audio in gate-free WebRTC tool responses

Repair1–3 exposed premature spoken acknowledgements before authoritative Core tool results. WebRTC playout cannot be retroactively revoked. A tool-enabled model may emit message audio and only later output a function call, so merely removing the mandatory routing inference is not a safe production change.

The fast benchmark disables tools at response and backend boundaries, preserving a truthful and fast direct-only test. Future gated-audio publication or reliable early ownership must be independently validated before enabling tool-capable gate-free Jarvis. Keep Core execution and permissions independent of the Realtime model.
