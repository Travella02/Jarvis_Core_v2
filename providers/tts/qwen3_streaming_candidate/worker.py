"""Isolated live benchmark for the experimental Qwen3-TTS streaming fork.

This file intentionally has no Jarvis imports. It runs inside the candidate's
separate Python 3.12 runtime and streams PCM chunks directly to sounddevice.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", required=True)
    p.add_argument("--reference", required=True)
    p.add_argument("--reference-text", default="")
    p.add_argument("--text", required=True)
    p.add_argument("--language", default="English")
    p.add_argument("--emit-every-frames", type=int, default=4)
    p.add_argument("--decode-window-frames", type=int, default=80)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    model_dir = Path(args.model_dir)
    reference = Path(args.reference)
    if not (model_dir / "config.json").is_file():
        raise FileNotFoundError(f"model not found: {model_dir}")
    if not reference.is_file():
        raise FileNotFoundError(reference)

    print("Loading streaming candidate model...", flush=True)
    load_started = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        str(model_dir),
        device_map="cuda:0",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
    )
    print(f"Model loaded in {time.perf_counter() - load_started:.2f}s", flush=True)

    reference_text = args.reference_text.strip() or None
    # Match Jarvis repair20's accepted live behavior: x-vector-only by default.
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(reference),
        ref_text=None,
        x_vector_only_mode=True,
    )

    if hasattr(model, "enable_streaming_optimizations"):
        model.enable_streaming_optimizations(
            decode_window_frames=args.decode_window_frames,
            use_compile=True,
            compile_mode="reduce-overhead",
        )

    started = time.perf_counter()
    first_chunk_s = None
    previous_arrival = None
    chunks = []
    sample_rate = None
    stream = None
    chunk_stats = []

    try:
        iterator = model.stream_generate_voice_clone(
            text=args.text,
            language=args.language,
            voice_clone_prompt=prompt,
            emit_every_frames=args.emit_every_frames,
            decode_window_frames=args.decode_window_frames,
            overlap_samples=0,
        )
        for index, (chunk, sr) in enumerate(iterator, start=1):
            now = time.perf_counter()
            audio = np.asarray(chunk, dtype=np.float32).squeeze()
            if audio.ndim != 1 or audio.size == 0:
                continue
            sample_rate = int(sr)
            if stream is None:
                stream = sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32")
                stream.start()
            arrival_s = now - started
            if first_chunk_s is None:
                first_chunk_s = arrival_s
            interval_s = None if previous_arrival is None else now - previous_arrival
            previous_arrival = now
            duration_s = audio.size / sample_rate
            stream.write(audio.reshape(-1, 1))
            chunks.append(audio.copy())
            chunk_stats.append({
                "index": index,
                "arrival_s": round(arrival_s, 4),
                "duration_s": round(duration_s, 4),
                "arrival_interval_s": None if interval_s is None else round(interval_s, 4),
            })
            print(
                f"chunk={index:02d} arrival={arrival_s:.3f}s audio={duration_s:.3f}s"
                + ("" if interval_s is None else f" interval={interval_s:.3f}s"),
                flush=True,
            )
    finally:
        if stream is not None:
            stream.stop()
            stream.close()

    total_s = time.perf_counter() - started
    if not chunks or sample_rate is None or first_chunk_s is None:
        raise RuntimeError("streaming candidate returned no audio")
    combined = np.concatenate(chunks)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output), combined, sample_rate, subtype="PCM_16")
    audio_s = combined.size / sample_rate
    summary = {
        "first_chunk_s": round(first_chunk_s, 4),
        "generation_total_s": round(total_s, 4),
        "audio_duration_s": round(audio_s, 4),
        "rtf": round(total_s / audio_s, 4),
        "chunks": len(chunks),
        "sample_rate": sample_rate,
        "output": str(output),
        "chunk_stats": chunk_stats,
    }
    print("STREAMING_CANDIDATE_SUMMARY=" + json.dumps(summary, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
