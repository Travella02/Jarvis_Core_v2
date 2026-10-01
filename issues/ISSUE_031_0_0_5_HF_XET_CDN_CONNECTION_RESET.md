# ISSUE 031 — Hugging Face Xet/CDN connection reset during Silero setup

Observed after Repair5a:
`curl: (35) Recv failure: Connection was reset`

This is distinct from the earlier certificate-revocation problem. The HTTPS
certificate path is no longer the blocker; the redirected model transfer is
being reset.

Repair5b makes setup client-independent and adds a verified local/manual install
path. No runtime voice behavior changes.
