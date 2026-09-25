# ISSUE 018 — VAD single point of failure

## Symptom
The selected MME microphone showed healthy voice levels in the direct meter, but normal Voice Lab could remain stuck listening because endpoint start depended only on WebRTC VAD.

## Resolution in repair13
Add ORVEX-owned acoustic activity redundancy ahead of endpointing while retaining raw VAD as independent evidence and preserving conservative false-speech rejection.

## Follow-up
Full noise suppression, AEC, and full-duplex barge-in remain future Voice Engine work.
