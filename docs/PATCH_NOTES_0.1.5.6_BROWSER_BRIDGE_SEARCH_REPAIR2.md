# Jarvis Core v2 0.1.5.6 Browser Bridge — Search Speech Repair 2

**Status:** candidate; requires live acceptance before cleanup or commit.

## Scope
- Repair Core's independent search-intent authorization for STT outputs where a spoken
  `search` is transcribed phonetically (such as `sirch`).
- Require the user to have named a supported search site and the model-proposed query
  terms in the same transcript to use phonetic fallback.
- Preserve exact-match authorization for normal speech, and all existing security gates.
- Add unit/integration regression tests with a fake browser extension (no hardware/audio).

## Installation
Extract to project root; run `python .\apply_0_1_5_6_browser_bridge_search_repair2.py`.
The installer validates the SHA256 of the original existing file (LF-normalized for Windows)
and refuses edits on drift. It backs up replaced files under `.patch_backups`.

## Acceptance workflow
1. `python -m unittest discover -s tests -q`
2. `npm run desktop:build`
3. Reuse the same launch flags and extension id as Browser Bridge startup repair 1.
4. Wake Jarvis, say `Open YouTube`, then `Search YouTube for Sidemen`.
   It must reuse the existing YouTube tab if one matching tab is connected.
5. Verify normal question latency, no accidental actions for negated or hypothetical speech,
   and audible failure reporting for genuinely unsupported requests.
6. Live accept; only then clean patch/backup directories and checkpoint commit.

## Source compatibility
Built against the v0.1.5.6 Browser Bridge candidate after Startup Repair 1.
If installer says `STOP: Changed source`, do not bypass it; upload the current checkpoint
for a tailored patch. Do not force merge or overwrite.
