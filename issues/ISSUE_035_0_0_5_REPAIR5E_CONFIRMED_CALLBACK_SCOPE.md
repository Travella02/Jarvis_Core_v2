# ISSUE 035 — Repair5e normal Voice Lab path references undefined on_confirmed

Repair5e placed `on_confirmed()` in the legacy half-duplex session while the
continuous session subscribed to `voice.speech.confidence_confirmed` using the
same name without a local definition.

Result: normal Voice Lab startup raises NameError before provider warmup.

Repair5f restores the intended confidence callbacks to the continuous session and
adds a source-level regression test for callback scope.
