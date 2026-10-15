"""Windows-native, test-only audible notification for held Core/Luna results.

Use the default Windows wave output (normally the same headphones as Jarvis).
No API calls, AI-generated audio, temporary files, or regular-session sounds.
"""
from __future__ import annotations

import io
import math
import os
import struct
import sys
import wave


def hold_cue_wav() -> bytes:
    """Create two clearly audible PCM notes, with a brief gap and soft edges."""
    rate = 22_050
    segments = ((880.0, .23), (0.0, .08), (1175.0, .27))
    samples: list[int] = []
    for frequency, seconds in segments:
        frames = round(rate * seconds)
        for index in range(frames):
            if frequency == 0:
                samples.append(0)
                continue
            fade = min(1.0, index / (rate * .012), (frames - 1 - index) / (rate * .025))
            amplitude = .52 * max(0.0, fade)
            samples.append(round(amplitude * 32767.0 * math.sin(2 * math.pi * frequency * index / rate)))
    destination = io.BytesIO()
    with wave.open(destination, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(struct.pack('<' + str(len(samples)) + 'h', *samples))
    return destination.getvalue()


def play_native_hold_cue() -> str:
    """Call in a worker thread. Return only a safe status (never device details)."""
    if os.environ.get('JARVIS_SILENT_TEST_CUES') == '1':
        return 'silenced_by_test_setting'
    if sys.platform != 'win32':
        return 'unsupported_platform'
    try:
        import winsound
        # SND_MEMORY is synchronous: it reliably plays the complete WAV. Run
        # in asyncio.to_thread so the Core event loop remains responsive.
        winsound.PlaySound(hold_cue_wav(), winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        return 'playback_api_completed'
    except Exception:
        return 'playback_api_failed'


if __name__ == '__main__':
    print('Playing Jarvis test-only cue on the Windows default audio output...')
    print('cue_status=' + play_native_hold_cue())
