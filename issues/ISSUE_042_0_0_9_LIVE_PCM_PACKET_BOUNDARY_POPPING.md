# ISSUE 042 — GPT-Live PCM packet boundaries could produce audible popping

## Symptom

During the first real 0.0.9 GPT-Live A/B session, Meridian sounded substantially more natural than the local Qwen path but intermittent clicks/pops were audible during speech and interruption.

The lab was configured for 16 kHz Live PCM while the selected HyperX output device ran at 44.1 kHz.

## Investigation

The GPT-Live WebSocket delivers raw PCM audio as one continuous ordered stream, but packet boundaries are arbitrary. The existing `SoundDeviceAudioOutput` adapter resampled each `AudioFrame` independently. That behavior is correct for isolated fixed-duration provider frames, but GPT-Live network packets are not independent waveforms.

Resetting linear interpolation at every packet boundary can change the interpolation phase and boundary endpoint. The next independently-resampled packet can therefore begin at a slightly discontinuous sample value, which is audible as a click/pop. Small network timing gaps can also starve an output stream if raw WebSocket chunks are written directly without a playback cushion.

Interruption had a second hard edge: queued not-yet-written PCM was discarded immediately while the device could still be rendering a non-zero waveform.

## V1 reference review

The read-only V1 0.3.6 checkpoint was reviewed before repair. V1 did not contain this local SoundDevice/GPT-Live resampling path, so there was no implementation to port directly. The relevant V1 playback-race issues (ISSUE-043, ISSUE-046, ISSUE-047) established the architectural lesson that provider generation, network/server drain, local buffering, and physical playback are distinct layers. 0.0.9 Repair1 therefore keeps continuity/jitter/interruption handling in the local provider-neutral audio integration rather than teaching GPT-Live or Conversation Core about Windows playback details.

## Root cause

- GPT-Live WebSocket PCM was treated as packet-local audio instead of one continuous waveform.
- Device-rate conversion reset interpolation state for each packet.
- The prototype had no fixed-frame playback conditioner/jitter cushion for arbitrary Live packet sizes.
- Barge-in discarded queued audio without a local fade-to-zero boundary.

## Repair

0.0.9 Repair1:

- changes the GPT-Live PCM default from 16 kHz to OpenAI's default 24 kHz PCM16 mono mode;
- introduces a provider-neutral `StreamingPCM16PlaybackBuffer` that reframes arbitrary PCM chunks into stable 20 ms blocks and prebuffers 40 ms before playback/rebuffer;
- adds a stateful streaming PCM16 resampler in the SoundDevice output adapter so packetization no longer changes the resampled waveform;
- keeps resampling/device adaptation outside GPT-Live and outside Conversation Core;
- adds a 5 ms fade-to-zero when a user barges in, while discarding only not-yet-consumed queued PCM;
- preserves Meridian as the current A/B voice;
- leaves the local Whisper/Luna/Qwen path available and does not add a dependency.

## Regression protection

Automated tests prove:

- GPT-Live defaults to 24 kHz PCM;
- resampling the same source as one chunk or irregular network chunks yields identical output bytes;
- arbitrary Live chunks are reframed into exact 20 ms PCM blocks;
- interruption drops queued audio and emits a bounded fade-to-zero frame;
- the existing Live WebSocket transport still passes at 24 kHz;
- the full repository regression remains green.

## Acceptance

The real acceptance criterion is audible: rerun Meridian using the exact five-phrase 0.0.9 A/B conversation and confirm popping/clicking is eliminated or materially reduced without making interruption feel sluggish.
