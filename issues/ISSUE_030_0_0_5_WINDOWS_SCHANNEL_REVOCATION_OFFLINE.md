# ISSUE 030 — Windows Schannel revocation server offline blocks VAD model setup

Observed on Windows curl:
`CRYPT_E_REVOCATION_OFFLINE (0x80092013)`

The HTTPS transfer can reach 100%, but Schannel returns a non-zero exit because
the certificate revocation endpoint is unavailable. The setup script therefore
removes the partial download and reports failure.

Repair5a uses curl's `--ssl-revoke-best-effort`, which keeps certificate
verification while allowing the download to proceed when only the revocation
server is unreachable. The model remains pinned by exact byte count and SHA-256.
