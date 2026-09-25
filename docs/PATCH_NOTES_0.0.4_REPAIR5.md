# 0.0.4-repair5 - Correct Chatterbox Asset URLs

This repair is intentionally narrow. Whisper/CUDA, the Blackwell Chatterbox runtime, Voice Core, Conversation Core, and Luna are unchanged.

## Fix
Repair4 correctly took ownership of Chatterbox model delivery but built the Hugging Face asset URL with an ambiguous expandable PowerShell string. Live testing surfaced repeated HTTP 404 responses even though the upstream file exists. Repair5 uses a pinned upstream revision, URL-escapes the filename, and constructs the final URL with the PowerShell format operator.

## Preserved behavior
- resumable curl retries
- BITS fallback
- SHA-256 verification for large/critical assets
- atomic final installation
- offline/local `from_local()` provider startup after setup
- provider isolation under `.runtime/voice/chatterbox`
