import asyncio
import unittest
from dataclasses import dataclass

from core.common.ids import CorrelationContext
from core.conversation import ConversationContext, EventBus
from core.voice import PlaybackLedger, VoicePresenceState, VoiceTurnResult
from core.voice.conversation_control import ContinuousVoiceSession, WakeSleepConfig
from core.voice.telemetry import VoiceLatencyTrace


@dataclass
class Capture:
    text: str
    onset_delay: float = 0.0
    lexical_delay: float | None = 0.002
    final_delay: float = 0.0
    speech_presence: bool = True


class FakeConversation:
    def __init__(self):
        self.context = ConversationContext("conv", "user")
        self.event_bus = EventBus()


class FakeEngine:
    def __init__(self, captures, *, response_delay=0.08, playback_fraction=0.5):
        self.conversation = FakeConversation()
        self.captures = list(captures)
        self.response_delay = response_delay
        self.playback_fraction = playback_fraction
        self.prompts = []
        self.interrupt_calls = 0
        self.capture_cancel_calls = 0
        self._response_phase = None

    async def listen_once(self, *, lexical_interrupt_probe=False):
        if not self.captures:
            await asyncio.Event().wait()
        capture = self.captures.pop(0)
        await asyncio.sleep(capture.onset_delay)
        trace = CorrelationContext.create()
        if capture.speech_presence:
            self.conversation.event_bus.emit(
                "voice.speech.started",
                origin="fake",
                trace=trace,
                conversation_id="conv",
                payload={"authority": "silero-neural-vad"},
            )
        if lexical_interrupt_probe and capture.lexical_delay is not None:
            await asyncio.sleep(capture.lexical_delay)
            self.conversation.event_bus.emit(
                "voice.speech.lexical_confirmed",
                origin="fake",
                trace=trace,
                conversation_id="conv",
                payload={"text": capture.text, "source": "fake"},
            )
        await asyncio.sleep(capture.final_delay)
        latency = VoiceLatencyTrace()
        latency.mark("speech_started")
        latency.mark("speech_ended")
        latency.mark("stt_final")
        return capture.text, latency, trace

    async def respond_to_transcript(self, transcript, **_kwargs):
        self.prompts.append(transcript)
        self._response_phase = "thinking"
        before_playback = self.response_delay * self.playback_fraction
        after_playback = self.response_delay - before_playback
        await asyncio.sleep(before_playback)
        if self.interrupt_calls == 0:
            self._response_phase = "speaking"
            self.conversation.event_bus.emit(
                "voice.response.playback_starting",
                origin="fake",
                conversation_id="conv",
            )
        await asyncio.sleep(after_playback)
        interrupted = self.interrupt_calls > 0
        ledger = PlaybackLedger(queued_bytes=200, played_bytes=0 if interrupted else 200)
        if interrupted:
            ledger.interrupt()
        self._response_phase = None
        return VoiceTurnResult(
            transcript=transcript,
            response_text=f"answer to {transcript}",
            status="interrupted" if interrupted else "completed",
            latency_ms={},
            playback=ledger,
            turn_id="turn",
            speech_metrics={},
            heard_text="" if interrupted else f"answer to {transcript}",
            interruption_playback_ms=0.0 if interrupted else None,
            interruption_phase="thinking" if interrupted else None,
        )

    async def interrupt_response(self, _reason=""):
        self.interrupt_calls += 1
        return True

    async def cancel_capture(self, _reason=""):
        self.capture_cancel_calls += 1
        return True


class ContinuousVoiceSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_sentence_wake_then_followup_needs_no_second_wake_word(self):
        engine = FakeEngine(
            [
                Capture("Hey Jarvis, what is a neutron star?"),
                Capture("Why is it so dense?", onset_delay=0.12),
            ],
            response_delay=0.03,
        )
        session = ContinuousVoiceSession(
            engine=engine,
            config=WakeSleepConfig(idle_timeout_seconds=1.0),
        )
        result = await session.run(max_completed_turns=2)
        self.assertEqual(
            engine.prompts,
            ["what is a neutron star?", "Why is it so dense?"],
        )
        self.assertEqual(result.wake_count, 1)
        self.assertEqual(result.final_presence, VoicePresenceState.AWAKE)

    async def test_non_speech_candidate_does_not_cancel_without_neural_presence(self):
        engine = FakeEngine(
            [
                Capture("Jarvis, explain Venus"),
                Capture(
                    "noise candidate",
                    onset_delay=0.005,
                    lexical_delay=None,
                    final_delay=0.2,
                    speech_presence=False,
                ),
            ],
            response_delay=0.04,
        )
        session = ContinuousVoiceSession(
            engine=engine,
            config=WakeSleepConfig(idle_timeout_seconds=1.0),
        )
        result = await session.run(max_completed_turns=1)
        self.assertEqual(engine.prompts, ["explain Venus"])
        self.assertEqual(engine.interrupt_calls, 0)
        self.assertEqual(result.interruption_count, 0)

    async def test_lexical_speech_while_thinking_cancels_before_playback(self):
        engine = FakeEngine(
            [
                Capture("Jarvis, explain Venus"),
                Capture("Actually stop and explain Mars", onset_delay=0.003, lexical_delay=0.003),
            ],
            response_delay=0.20,
            playback_fraction=0.75,
        )
        session = ContinuousVoiceSession(
            engine=engine,
            config=WakeSleepConfig(idle_timeout_seconds=1.0),
        )
        result = await session.run(max_completed_turns=1)
        self.assertEqual(engine.prompts, ["explain Venus"])
        self.assertEqual(engine.interrupt_calls, 1)
        self.assertEqual(result.interruption_count, 1)

    async def test_lexical_speech_while_speaking_triggers_barge_in(self):
        engine = FakeEngine(
            [
                Capture("Jarvis, explain Venus"),
                Capture("Wait, explain it simply", onset_delay=0.12, lexical_delay=0.003),
            ],
            response_delay=0.20,
            playback_fraction=0.25,
        )
        session = ContinuousVoiceSession(
            engine=engine,
            config=WakeSleepConfig(idle_timeout_seconds=1.0),
        )
        result = await session.run(max_completed_turns=1)
        self.assertEqual(engine.prompts, ["explain Venus"])
        self.assertEqual(engine.interrupt_calls, 1)
        self.assertEqual(result.interruption_count, 1)


    async def test_final_lexical_transcript_cancels_when_early_probe_is_unavailable(self):
        engine = FakeEngine(
            [
                Capture("Jarvis, explain Venus"),
                Capture(
                    "Actually explain Mars instead",
                    onset_delay=0.003,
                    lexical_delay=None,
                    final_delay=0.02,
                ),
            ],
            response_delay=0.20,
            playback_fraction=0.75,
        )
        session = ContinuousVoiceSession(
            engine=engine,
            config=WakeSleepConfig(idle_timeout_seconds=1.0),
        )
        result = await session.run(max_completed_turns=1)
        self.assertEqual(engine.prompts, ["explain Venus"])
        self.assertEqual(engine.interrupt_calls, 1)
        self.assertEqual(result.interruption_count, 1)



if __name__ == "__main__":
    unittest.main()
