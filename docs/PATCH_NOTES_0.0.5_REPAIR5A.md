# Jarvis Core v2 0.0.5 Repair5a

## Scope
Windows-only Silero VAD setup reliability fix.

## Change
`setup_whisper_vad.ps1` now passes `--ssl-revoke-best-effort` to Windows `curl.exe`.

This addresses Schannel `CRYPT_E_REVOCATION_OFFLINE (0x80092013)` failures when
the certificate revocation server cannot be reached. It does not disable normal
certificate validation. The downloaded Silero model is still required to match
the pinned byte length and SHA-256 before installation.

No runtime voice, STT, VAD, TTS, interruption, wake/sleep, or Luna behavior changed.
