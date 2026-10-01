# Jarvis Core v2 0.0.5 Repair5b

## Scope
Silero VAD setup reliability only. Runtime speech/VAD behavior is unchanged.

Repair5a moved past the Windows Schannel revocation-offline error, but the
redirected Hugging Face Xet/CDN transfer can still be reset on some networks.

Repair5b:
- supports a verified local model via `-SourcePath`;
- accepts a verified model dropped in the project root;
- tries curl with HTTP/1.1 and resume support;
- falls back to PowerShell Invoke-WebRequest;
- falls back to Windows BITS;
- prints an official browser/manual fallback if all network clients fail.

Every path still requires the exact pinned byte count and SHA-256.
