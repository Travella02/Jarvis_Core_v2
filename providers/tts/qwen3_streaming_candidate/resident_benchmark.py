"""Repair23 resident warm-request benchmark for the Qwen streaming candidate.

Runs inside the isolated candidate Python 3.12 runtime. The model is loaded once,
streaming optimizations are enabled once, one synthesis is consumed as warmup,
and then multiple requests are measured in the same process.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _cuda_sync(torch) -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def _make_iterator(model, *, text: str, language: str, prompt, emit_every_frames: int, decode_window_frames: int):
    return model.stream_generate_voice_clone(
        text=text,
        language=language,
        voice_clone_prompt=prompt,
        emit_every_frames=emit_every_frames,
        decode_window_frames=decode_window_frames,
        overlap_samples=0,
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", required=True)
    p.add_argument("--reference", required=True)
    p.add_argument("--reference-text", default="")
    p.add_argument("--text", required=True)
    p.add_argument("--language", default="English")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--emit-every-frames", type=int, default=4)
    p.add_argument("--decode-window-frames", type=int, default=80)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--no-playback", action="store_true")
    args = p.parse_args()

    if args.runs < 1:
        raise ValueError("--runs must be at least 1")

    import numpy as np
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel
    if not args.no_playback:
        import sounddevice as sd
    else:
        sd = None

    model_dir = Path(args.model_dir)
    reference = Path(args.reference)
    output_dir = Path(args.output_dir)
    if not (model_dir / "config.json").is_file():
        raise FileNotFoundError(f"model not found: {model_dir}")
    if not reference.is_file():
        raise FileNotFoundError(reference)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading RESIDENT streaming candidate model...", flush=True)
    load_started = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        str(model_dir),
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    _cuda_sync(torch)
    load_s = time.perf_counter() - load_started
    print(f"Resident model loaded in {load_s:.3f}s", flush=True)

    # Match the accepted Repair20 live behavior: x-vector-only by default.
    prompt_started = time.perf_counter()
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(reference),
        ref_text=None,
        x_vector_only_mode=True,
    )
    _cuda_sync(torch)
    prompt_s = time.perf_counter() - prompt_started
    print(f"Voice-clone prompt prepared in {prompt_s:.3f}s", flush=True)

    if hasattr(model, "enable_streaming_optimizations"):
        model.enable_streaming_optimizations(
            decode_window_frames=args.decode_window_frames,
            use_compile=True,
            compile_mode="reduce-overhead",
        )

    # Warmup uses the exact measured text on purpose. This isolates the latency
    # of a hot request after model load + compilation for the same shape/path.
    print("WARMUP_BEGIN (same resident process; output discarded)", flush=True)
    warm_started = time.perf_counter()
    warm_first = None
    warm_chunks = 0
    warm_samples = 0
    warm_sr = None
    for chunk, sr in _make_iterator(
        model,
        text=args.text,
        language=args.language,
        prompt=prompt,
        emit_every_frames=args.emit_every_frames,
        decode_window_frames=args.decode_window_frames,
    ):
        now = time.perf_counter()
        audio = np.asarray(chunk, dtype=np.float32).squeeze()
        if audio.ndim != 1 or audio.size == 0:
            continue
        if warm_first is None:
            warm_first = now - warm_started
        warm_chunks += 1
        warm_samples += int(audio.size)
        warm_sr = int(sr)
    _cuda_sync(torch)
    warm_total = time.perf_counter() - warm_started
    if warm_first is None or warm_sr is None or warm_chunks == 0:
        raise RuntimeError("warmup returned no audio")
    warm_audio_s = warm_samples / warm_sr
    warm_summary = {
        "first_chunk_s": round(warm_first, 4),
        "generation_total_s": round(warm_total, 4),
        "audio_duration_s": round(warm_audio_s, 4),
        "chunks": warm_chunks,
    }
    print("WARMUP_SUMMARY=" + json.dumps(warm_summary, separators=(",", ":")), flush=True)
    print("WARMUP_COMPLETE -- model stays resident", flush=True)

    run_summaries = []
    for run_index in range(1, args.runs + 1):
        _cuda_sync(torch)
        started = time.perf_counter()
        first_chunk_s = None
        first_play_s = None
        previous_arrival = None
        chunks = []
        chunk_stats = []
        sample_rate = None
        stream = None
        print(f"RESIDENT_RUN_BEGIN={run_index}", flush=True)
        try:
            iterator = _make_iterator(
                model,
                text=args.text,
                language=args.language,
                prompt=prompt,
                emit_every_frames=args.emit_every_frames,
                decode_window_frames=args.decode_window_frames,
            )
            for chunk_index, (chunk, sr) in enumerate(iterator, start=1):
                now = time.perf_counter()
                audio = np.asarray(chunk, dtype=np.float32).squeeze()
                if audio.ndim != 1 or audio.size == 0:
                    continue
                sample_rate = int(sr)
                arrival_s = now - started
                if first_chunk_s is None:
                    first_chunk_s = arrival_s
                interval_s = None if previous_arrival is None else now - previous_arrival
                previous_arrival = now
                duration_s = audio.size / sample_rate

                if sd is not None:
                    if stream is None:
                        stream = sd.OutputStream(
                            samplerate=sample_rate,
                            channels=1,
                            dtype="float32",
                        )
                        stream.start()
                        first_play_s = time.perf_counter() - started
                    stream.write(audio.reshape(-1, 1))

                chunks.append(audio.copy())
                chunk_stats.append({
                    "index": chunk_index,
                    "arrival_s": round(arrival_s, 4),
                    "duration_s": round(duration_s, 4),
                    "arrival_interval_s": None if interval_s is None else round(interval_s, 4),
                })
                print(
                    f"run={run_index} chunk={chunk_index:02d} arrival={arrival_s:.3f}s "
                    f"audio={duration_s:.3f}s"
                    + ("" if interval_s is None else f" interval={interval_s:.3f}s"),
                    flush=True,
                )
        finally:
            if stream is not None:
                stream.stop()
                stream.close()

        _cuda_sync(torch)
        total_s = time.perf_counter() - started
        if not chunks or sample_rate is None or first_chunk_s is None:
            raise RuntimeError(f"resident run {run_index} returned no audio")
        combined = np.concatenate(chunks)
        output = output_dir / f"resident_run_{run_index:02d}.wav"
        sf.write(str(output), combined, sample_rate, subtype="PCM_16")
        audio_s = combined.size / sample_rate
        summary = {
            "run": run_index,
            "first_chunk_s": round(first_chunk_s, 4),
            "first_play_s": None if first_play_s is None else round(first_play_s, 4),
            "generation_total_s": round(total_s, 4),
            "audio_duration_s": round(audio_s, 4),
            "rtf": round(total_s / audio_s, 4),
            "chunks": len(chunks),
            "sample_rate": sample_rate,
            "output": str(output),
            "chunk_stats": chunk_stats,
        }
        run_summaries.append(summary)
        print("RESIDENT_RUN_SUMMARY=" + json.dumps(summary, separators=(",", ":")), flush=True)

    hot_first = [r["first_chunk_s"] for r in run_summaries]
    final = {
        "model_load_s": round(load_s, 4),
        "prompt_prepare_s": round(prompt_s, 4),
        "warmup": warm_summary,
        "measured_runs": run_summaries,
        "hot_first_chunk_min_s": round(min(hot_first), 4),
        "hot_first_chunk_avg_s": round(sum(hot_first) / len(hot_first), 4),
        "runs": len(run_summaries),
        "playback": not args.no_playback,
    }
    print("RESIDENT_BENCHMARK_SUMMARY=" + json.dumps(final, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
