"""0.0.9 GPT-Live A/B voice-frontend lab.

This is intentionally a development lab, not the production wake/sleep client.
It proves the provider boundary, full-duplex audio transport, and client
delegation into the existing authoritative Conversation Core/Luna path.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from time import monotonic

from core.common.cancellation import CancellationToken
from core.common.ids import CorrelationContext
from core.conversation.engine import VOICE_RESPONSE_INSTRUCTION
from core.intelligence import IntelligenceContext, IntelligenceEventType, ReasoningPolicy
from core.runtime import IntelligenceProviderRouter, JarvisRuntime, RuntimeSettings
from core.voice import AudioFormat, AudioFrame, AudioSampleFormat
from core.voice.frontend import VoiceFrontendEventType, VoiceFrontendSessionConfig
from core.voice.live_bridge import LiveConversationBridge
from integrations.audio.sounddevice_io import SoundDeviceAudioInput, SoundDeviceAudioOutput
from integrations.audio.streaming_pcm import StreamingPCM16PlaybackBuffer
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig
from providers.voice_frontend.openai_live import OpenAIGPTLiveConfig, OpenAIGPTLiveProvider
from providers.voice_frontend.openai_live.provider import LIVE_CONVERSATION_INSTRUCTIONS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_PHRASES = (
    "Jarvis, tell me something interesting about space.",
    "Why does that happen?",
    "Explain it more simply.",
    "Tell me another interesting fact.",
    "Tell me a short joke.",
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Jarvis 0.0.9 GPT-Live A/B voice frontend lab")
    result.add_argument("--turns", type=int, default=5, help="Delegated backend turns before automatic shutdown")
    result.add_argument("--input-device", type=int, default=None)
    result.add_argument("--output-device", type=int, default=None)
    result.add_argument("--voice", default=None, help="GPT-Live built-in voice API name")
    result.add_argument("--live-model", default=None)
    result.add_argument("--luna-model", default=None)
    result.add_argument("--luna-service-tier", default=None)
    result.add_argument("--no-prewarm", action="store_true")
    result.add_argument("--tail-seconds", type=float, default=4.0, help="Playback grace after final backend result")
    result.add_argument("--max-seconds", type=float, default=180.0, help="Safety timeout for the lab session")
    result.add_argument("--doctor", action="store_true", help="Print provider configuration without network/audio")
    return result


async def _prewarm_luna(provider: OpenAIProvider) -> None:
    started = monotonic()
    first_text_ms = None
    context = IntelligenceContext(
        trace=CorrelationContext.create(),
        messages=(
            {"role": "developer", "content": VOICE_RESPONSE_INSTRUCTION},
            {"role": "user", "content": "Reply with exactly one word: Ready."},
        ),
        metadata={"input_channel": "voice", "conversation_id": "gpt-live-lab-prewarm"},
    )
    async for event in provider.stream_response(
        context,
        (),
        ReasoningPolicy(level="none", allow_escalation=False),
        CancellationToken(),
    ):
        if event.event_type is IntelligenceEventType.TEXT_DELTA and first_text_ms is None:
            first_text_ms = (monotonic() - started) * 1000.0
    elapsed_ms = (monotonic() - started) * 1000.0
    first_label = f"{first_text_ms:.0f} ms TTFT" if first_text_ms is not None else "no text delta"
    print(f"Luna warmup: {elapsed_ms:.0f} ms ({first_label}; output discarded).")


def _build_runtime(args: argparse.Namespace) -> tuple[JarvisRuntime, OpenAIProvider]:
    intelligence_config = OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env")
    updates = {"voice_transport": "websocket"}
    if args.luna_model:
        updates["model"] = args.luna_model
    if args.luna_service_tier:
        updates["service_tier"] = args.luna_service_tier
    intelligence_config = replace(intelligence_config, **updates)
    luna = OpenAIProvider(intelligence_config)

    runtime_settings = RuntimeSettings.from_env(env_file=PROJECT_ROOT / ".env")
    router = IntelligenceProviderRouter(default_route=runtime_settings.default_intelligence_route)
    router.register(runtime_settings.default_intelligence_route, luna, make_default=True)
    runtime = JarvisRuntime(settings=runtime_settings, provider_router=router)
    runtime.start()
    runtime.create_conversation(
        user_id="local-development-user",
        speaker_id="gpt-live-lab-user",
        device_id="gpt-live-lab",
    )
    return runtime, luna


async def doctor(args: argparse.Namespace) -> int:
    config = OpenAIGPTLiveConfig.from_env(env_file=PROJECT_ROOT / ".env")
    if args.voice:
        config = replace(config, voice=args.voice)
    if args.live_model:
        config = replace(config, model=args.live_model)
    provider = OpenAIGPTLiveProvider(config)
    health = await provider.health()
    print(f"Version: {(PROJECT_ROOT / 'VERSION').read_text(encoding='utf-8').strip()}")
    print(f"Frontend: {provider.metadata.provider} | model={provider.metadata.model}")
    print(f"Voice: {config.voice} | audio={config.audio_rate_hz} Hz PCM16 mono")
    print(f"Delegation: client -> Jarvis Core -> configured intelligence provider")
    print(f"Health: {health.status} | {health.detail or '-'}")
    print("Doctor performs no microphone capture, model request, or network connection.")
    return 0 if health.ready else 2


async def run(args: argparse.Namespace) -> int:
    if args.turns <= 0:
        raise ValueError("--turns must be positive")
    if args.tail_seconds < 0 or args.max_seconds <= 0:
        raise ValueError("--tail-seconds must be non-negative and --max-seconds must be positive")

    runtime, luna = _build_runtime(args)
    conversation = runtime.conversation
    assert conversation is not None

    live_config = OpenAIGPTLiveConfig.from_env(env_file=PROJECT_ROOT / ".env")
    if args.voice:
        live_config = replace(live_config, voice=args.voice)
    if args.live_model:
        live_config = replace(live_config, model=args.live_model)
    live_provider = OpenAIGPTLiveProvider(live_config)
    live_health = await live_provider.health()
    if not live_health.ready:
        runtime.close()
        await luna.close()
        raise RuntimeError(f"GPT-Live is not ready: {live_health.status} - {live_health.detail or ''}")

    audio_format = AudioFormat(
        sample_rate_hz=live_config.audio_rate_hz,
        channels=1,
        sample_format=AudioSampleFormat.PCM_S16LE,
    )
    audio_input = SoundDeviceAudioInput(args.input_device)
    audio_output = SoundDeviceAudioOutput(args.output_device)
    input_info = await audio_input.selected_device()
    output_info = await audio_output.selected_device()

    print("Jarvis Core v2 0.0.9 GPT-Live A/B Lab")
    print(f"Input:  [{input_info.device_id}] {input_info.name} | native={input_info.default_sample_rate_hz or '-'} Hz -> Live={audio_format.sample_rate_hz} Hz")
    print(f"Output: [{output_info.device_id}] {output_info.name} | native={output_info.default_sample_rate_hz or '-'} Hz")
    print(f"Voice frontend: {live_config.model} | voice={live_config.voice} | client delegation")
    print(f"Backend: {luna.metadata.model} | Luna remains inside Jarvis Core")
    print("Local Whisper/Qwen path is unchanged and remains the rollback/A-B baseline.")
    print("\nSay these five phrases for the acceptance comparison:")
    for index, phrase in enumerate(TEST_PHRASES, start=1):
        print(f"  {index}. {phrase}")
    print("     Action for #4: start speaking before Jarvis finishes the response to #3.")

    if not args.no_prewarm:
        await _prewarm_luna(luna)

    session_config = VoiceFrontendSessionConfig(
        instructions=LIVE_CONVERSATION_INSTRUCTIONS,
        voice=live_config.voice,
        sample_rate_hz=live_config.audio_rate_hz,
        history=(),
        store=False,
    )
    session = await live_provider.open_session(session_config)
    bridge = LiveConversationBridge(conversation=conversation, session=session)
    print(f"GPT-Live session ready: {session.session_id or '[provider id unavailable]'}")
    print("Listening now. GPT-Live is full duplex; interrupt naturally on phrase 4.\n")

    capture_token = CancellationToken()
    playback_token = CancellationToken()
    trace = CorrelationContext.create()
    playback_buffer = StreamingPCM16PlaybackBuffer(
        sample_rate_hz=audio_format.sample_rate_hz,
        frame_ms=20,
        prebuffer_ms=40,
        fade_ms=5,
    )
    completed_turns = 0
    completion_event = asyncio.Event()
    latest_usage_seconds = 0.0
    caption_speaker: str | None = None
    session_started_local = monotonic()
    last_input_end_ms = 0
    pending_first_audio_after_input = True

    def on_backend_completed(event) -> None:
        nonlocal completed_turns
        completed_turns += 1
        backend_ms = event.payload.get("backend_ms", "?")
        print(f"\n[Jarvis Core backend complete: {backend_ms} ms | delegated turn {completed_turns}/{args.turns}]")
        if completed_turns >= args.turns:
            completion_event.set()

    unsubscribe = runtime.event_bus.subscribe("voice.frontend.delegation.completed", on_backend_completed)

    async def output_frames():
        sequence = 0
        async for payload in playback_buffer.frames():
            if playback_token.is_cancelled:
                return
            if not payload:
                continue
            yield AudioFrame(
                trace=trace,
                sequence=sequence,
                format=audio_format,
                payload=payload,
            )
            sequence += 1

    async def capture_loop() -> None:
        async for frame in audio_input.stream(
            trace=trace,
            audio_format=audio_format,
            frame_ms=20,
            cancellation_token=capture_token,
        ):
            await session.send_audio(frame.payload)

    async def event_loop() -> None:
        nonlocal latest_usage_seconds, caption_speaker, last_input_end_ms, pending_first_audio_after_input
        async for event in session.events():
            if event.event_type is VoiceFrontendEventType.INPUT_TRANSCRIPT_DELTA:
                last_input_end_ms = max(last_input_end_ms, int(event.end_ms or 0))
                pending_first_audio_after_input = True
                if caption_speaker != "user":
                    # If the user starts speaking while Jarvis owns the caption
                    # lane, treat it as conversational barge-in. Drop only audio
                    # that has not reached the device yet and ramp the local PCM
                    # stream to zero instead of hard-cutting a waveform.
                    if caption_speaker == "assistant":
                        playback_buffer.interrupt()
                    print("\nYou: ", end="", flush=True)
                    caption_speaker = "user"
                print(event.text, end="", flush=True)
            elif event.event_type is VoiceFrontendEventType.OUTPUT_TRANSCRIPT_DELTA:
                if caption_speaker != "assistant":
                    print("\nJarvis: ", end="", flush=True)
                    caption_speaker = "assistant"
                print(event.text, end="", flush=True)
            elif event.event_type is VoiceFrontendEventType.OUTPUT_AUDIO:
                if pending_first_audio_after_input and last_input_end_ms:
                    local_input_end = session_started_local + last_input_end_ms / 1000.0
                    approx_ms = max(0.0, (monotonic() - local_input_end) * 1000.0)
                    print(f"\n[approx speech-end -> first Live audio packet: {approx_ms:.0f} ms]", flush=True)
                    pending_first_audio_after_input = False
                playback_buffer.append(event.audio)
            elif event.event_type is VoiceFrontendEventType.DELEGATION_REQUESTED:
                print(f"\n[GPT-Live delegated to Jarvis Core: {event.delegation_id or '?'}]", flush=True)
            elif event.event_type is VoiceFrontendEventType.USAGE_UPDATED:
                latest_usage_seconds = max(latest_usage_seconds, float(event.usage_seconds or 0.0))
            elif event.event_type is VoiceFrontendEventType.ERROR:
                print(f"\n[GPT-Live error] {event.detail or 'unknown error'}", flush=True)
            await bridge.handle_event(event)

    capture_task = asyncio.create_task(capture_loop(), name="gpt-live-capture")
    playback_task = asyncio.create_task(audio_output.play(output_frames(), playback_token), name="gpt-live-playback")
    events_task = asyncio.create_task(event_loop(), name="gpt-live-events")

    async def completion_shutdown() -> None:
        await completion_event.wait()
        if args.tail_seconds:
            await asyncio.sleep(args.tail_seconds)

    completion_task = asyncio.create_task(completion_shutdown(), name="gpt-live-completion")
    timeout_task = asyncio.create_task(asyncio.sleep(args.max_seconds), name="gpt-live-timeout")

    try:
        done, _ = await asyncio.wait(
            {completion_task, timeout_task, events_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if timeout_task in done and not completion_event.is_set():
            print(f"\n[Lab safety timeout after {args.max_seconds:.0f}s]")
        if events_task in done and not completion_event.is_set():
            exc = events_task.exception()
            if exc:
                raise exc
    finally:
        capture_token.cancel("GPT-Live lab ending")
        playback_token.cancel("GPT-Live lab ending")
        await bridge.close()
        await session.close()
        playback_buffer.close()
        await audio_output.stop()
        for task in (capture_task, completion_task, timeout_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(capture_task, completion_task, timeout_task, return_exceptions=True)
        if not events_task.done():
            events_task.cancel()
        await asyncio.gather(events_task, return_exceptions=True)
        with suppress(Exception):
            playback_result = await asyncio.wait_for(playback_task, timeout=2.0)
            buffer_stats = playback_buffer.stats
            print(
                f"\nPlayback: source_audio={playback_result.source_duration_ms_written:.0f} ms | "
                f"device_latency={playback_result.output_latency_ms or 0.0:.1f} ms | "
                f"interrupt_fades={buffer_stats.interruptions} | "
                f"dropped_unplayed={buffer_stats.dropped_bytes} bytes"
            )
        unsubscribe()
        await luna.close()
        runtime.close()

    print(f"Final GPT-Live usage observed: {latest_usage_seconds:.1f} seconds")
    print(f"Delegated backend turns completed: {completed_turns}")
    print("Status: ok" if completed_turns >= args.turns else "Status: incomplete")
    return 0 if completed_turns >= args.turns else 1


async def async_main(args: argparse.Namespace) -> int:
    if args.doctor:
        return await doctor(args)
    return await run(args)


def main() -> int:
    args = parser().parse_args()
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nGPT-Live lab interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
