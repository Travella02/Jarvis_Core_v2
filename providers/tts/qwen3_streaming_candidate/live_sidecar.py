"""Resident binary-PCM sidecar for Repair24's Qwen streaming candidate.

Runs inside the isolated candidate Python 3.12 environment. Protocol traffic is
kept on stdout while third-party model logs are redirected to stderr.
"""
from __future__ import annotations

import argparse
import hashlib
from contextlib import redirect_stdout
import json
import random
import sys
import time
from pathlib import Path

PROTO = sys.stdout.buffer


def emit(payload: dict) -> None:
    PROTO.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
    PROTO.flush()


def _reset_rng(seed: int | None, np, torch) -> None:
    """Reset common RNGs before one synthesis request.

    None intentionally does nothing so Repair27 remains the control behavior.
    """
    if seed is None:
        return
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", required=True)
    p.add_argument("--emit-every-frames", type=int, default=4)
    p.add_argument("--decode-window-frames", type=int, default=80)
    p.add_argument("--fixed-seed", type=int, default=None)
    p.add_argument("--cancel-dir", required=True)
    args = p.parse_args()
    if args.fixed_seed is not None and not 0 <= args.fixed_seed <= 0xFFFFFFFF:
        p.error("--fixed-seed must be between 0 and 4294967295")

    try:
        with redirect_stdout(sys.stderr):
            import numpy as np
            import torch
            from qwen_tts import Qwen3TTSModel

            model_dir = Path(args.model_dir)
            if not (model_dir / "config.json").is_file():
                raise FileNotFoundError(f"model not found: {model_dir}")

            load_started = time.perf_counter()
            model = Qwen3TTSModel.from_pretrained(
                str(model_dir),
                device_map="cuda:0",
                dtype=torch.bfloat16,
                attn_implementation="sdpa",
            )
            if hasattr(model, "enable_streaming_optimizations"):
                model.enable_streaming_optimizations(
                    decode_window_frames=args.decode_window_frames,
                    use_compile=True,
                    compile_mode="reduce-overhead",
                )
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            load_s = time.perf_counter() - load_started
        emit({
            "event": "ready",
            "ok": True,
            "load_s": round(load_s, 4),
            "fixed_seed": args.fixed_seed,
            "seed_strategy": "per-request-reset" if args.fixed_seed is not None else "upstream-random",
        })
    except Exception as exc:
        emit({"event": "startup_error", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1

    prompt = None
    language = "English"
    voice_key = None
    cancel_dir = Path(args.cancel_dir)
    cancel_dir.mkdir(parents=True, exist_ok=True)

    def cancel_flag(request_id: str) -> Path:
        digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        return cancel_dir / f"{digest}.cancel"

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        request = json.loads(raw)
        request_id = str(request.get("id") or "unknown")
        op = request.get("op")
        try:
            if op == "shutdown":
                emit({"id": request_id, "ok": True, "event": "shutdown"})
                return 0
            if op == "prepare_voice":
                reference = Path(str(request.get("reference") or ""))
                if not reference.is_file():
                    raise FileNotFoundError(reference)
                language = str(request.get("language") or "English")
                x_vector_only = bool(request.get("x_vector_only", True))
                key = (str(reference.resolve()), language, x_vector_only)
                if key != voice_key:
                    started = time.perf_counter()
                    with redirect_stdout(sys.stderr):
                        prompt = model.create_voice_clone_prompt(
                            ref_audio=str(reference),
                            ref_text=None,
                            x_vector_only_mode=x_vector_only,
                        )
                        if torch.cuda.is_available():
                            torch.cuda.synchronize()
                    voice_key = key
                    prepare_s = time.perf_counter() - started
                else:
                    prepare_s = 0.0
                emit({"id": request_id, "ok": True, "event": "voice_ready", "prepare_s": round(prepare_s, 4)})
                continue
            if op == "warmup":
                if prompt is None:
                    raise RuntimeError("voice must be prepared before warmup")
                text = str(request.get("text") or "").strip()
                if not text:
                    raise ValueError("warmup text cannot be empty")
                started = time.perf_counter()
                first_chunk_s = None
                chunks = 0
                with redirect_stdout(sys.stderr):
                    iterator = model.stream_generate_voice_clone(
                        text=text,
                        language=language,
                        voice_clone_prompt=prompt,
                        emit_every_frames=args.emit_every_frames,
                        decode_window_frames=args.decode_window_frames,
                        overlap_samples=0,
                    )
                    for chunk, _sr in iterator:
                        if first_chunk_s is None:
                            first_chunk_s = time.perf_counter() - started
                        chunks += 1
                    if torch.cuda.is_available():
                        torch.cuda.synchronize()
                emit({
                    "id": request_id,
                    "ok": True,
                    "event": "warmup_complete",
                    "first_chunk_s": None if first_chunk_s is None else round(first_chunk_s, 4),
                    "total_s": round(time.perf_counter() - started, 4),
                    "chunks": chunks,
                })
                continue
            if op == "synthesize":
                if prompt is None:
                    raise RuntimeError("voice must be prepared before synthesis")
                text = str(request.get("text") or "").strip()
                if not text:
                    raise ValueError("text cannot be empty")
                started = time.perf_counter()
                chunks = 0
                was_cancelled = False
                flag = cancel_flag(request_id)
                flag.unlink(missing_ok=True)
                _reset_rng(args.fixed_seed, np, torch)
                iterator = None
                try:
                    with redirect_stdout(sys.stderr):
                        iterator = model.stream_generate_voice_clone(
                            text=text,
                            language=language,
                            voice_clone_prompt=prompt,
                            emit_every_frames=args.emit_every_frames,
                            decode_window_frames=args.decode_window_frames,
                            overlap_samples=0,
                        )
                        for chunk, sr in iterator:
                            # Normal barge-in is cooperative: stop the generator
                            # between streaming chunks but keep the loaded model,
                            # compiled kernels, and prepared voice resident.
                            if flag.exists():
                                was_cancelled = True
                                break
                            audio = np.asarray(chunk, dtype=np.float32).reshape(-1)
                            if audio.size == 0:
                                continue
                            pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype("<i2", copy=False).tobytes()
                            chunks += 1
                            emit({
                                "id": request_id,
                                "ok": True,
                                "event": "audio_chunk",
                                "index": chunks,
                                "sample_rate": int(sr),
                                "bytes": len(pcm),
                                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 1),
                            })
                            PROTO.write(pcm)
                            PROTO.flush()
                            if flag.exists():
                                was_cancelled = True
                                break
                finally:
                    flag.unlink(missing_ok=True)
                    close = getattr(iterator, "close", None)
                    if callable(close):
                        close()
                emit({
                    "id": request_id,
                    "ok": True,
                    "event": "cancelled" if was_cancelled else "complete",
                    "chunks": chunks,
                    "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 1),
                })
                continue
            raise ValueError(f"unsupported op: {op!r}")
        except Exception as exc:
            emit({"id": request_id, "ok": False, "event": "error", "error": f"{type(exc).__name__}: {exc}"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
