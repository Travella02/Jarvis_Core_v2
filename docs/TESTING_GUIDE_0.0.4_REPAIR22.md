# Repair22 testing

1. Run the normal Jarvis unit suite. Expected baseline after this patch: 168 tests, all passing.
2. Install the isolated experimental runtime:
   `powershell -ExecutionPolicy Bypass -File scripts\setup_qwen3_tts_streaming_candidate.ps1`
3. Run:
   `python -m apps.qwen_streaming_candidate --voice-profile tanner-test`
4. Listen for continuous playback and capture the console output, especially `first_chunk_s`, `generation_total_s`, `audio_duration_s`, `rtf`, and per-chunk arrival timings.
5. Do not integrate the candidate into Voice Lab or commit 0.0.4 based only on installation success. Live audio/timing acceptance is required.
