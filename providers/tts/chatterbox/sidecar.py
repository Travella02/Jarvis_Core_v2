"""Isolated JSON-line Chatterbox Turbo worker.

This file intentionally has no Jarvis imports. It runs inside the provider's
private Python environment so Chatterbox/PyTorch dependency pins cannot mutate
Jarvis Core's main environment.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import tempfile
import traceback
import wave
from pathlib import Path


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    try:
        # Keep third-party chatter/progress messages away from the JSON-line
        # protocol on stdout. Startup tracebacks still go to stderr and are
        # captured by the parent provider for diagnostics.
        with contextlib.redirect_stdout(sys.stderr):
            import torch
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            model_dir = Path(args.model_dir)
            required = (
                "ve.safetensors",
                "t3_turbo_v1.safetensors",
                "s3gen_meanflow.safetensors",
                "tokenizer_config.json",
                "vocab.json",
                "merges.txt",
                "special_tokens_map.json",
                "added_tokens.json",
                "conds.pt",
            )
            missing = [name for name in required if not (model_dir / name).is_file()]
            if missing:
                raise FileNotFoundError(
                    f"Chatterbox model assets are incomplete at {model_dir}; missing: {', '.join(missing)}"
                )
            model = ChatterboxTurboTTS.from_local(model_dir, device=args.device)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        emit(
            {
                "event": "startup_error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return 1

    emit(
        {
            "event": "ready",
            "device": args.device,
            "sample_rate": int(model.sr),
            "torch": torch.__version__,
            "cuda": bool(torch.cuda.is_available()),
        }
    )

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        request = None
        try:
            request = json.loads(raw)
            request_id = str(request["id"])
            op = request.get("op")
            if op == "health":
                emit({"id": request_id, "ok": True, "status": "ready"})
                continue
            if op == "shutdown":
                emit({"id": request_id, "ok": True})
                return 0
            if op != "synthesize":
                raise ValueError(f"unsupported op: {op}")

            text = str(request.get("text", "")).strip()
            if not text:
                raise ValueError("text cannot be empty")
            reference = request.get("reference_audio_path") or None
            settings = dict(request.get("settings") or {})
            allowed = {"exaggeration", "cfg_weight", "temperature"}
            kwargs = {key: value for key, value in settings.items() if key in allowed}
            if reference:
                kwargs["audio_prompt_path"] = str(reference)
            # Inference mode removes autograd bookkeeping from the persistent
            # local speech worker. It does not change the provider contract or
            # model choice, but reduces avoidable per-utterance overhead.
            with torch.inference_mode(), contextlib.redirect_stdout(sys.stderr):
                wav = model.generate(text, **kwargs)
            samples = wav.squeeze().detach().clamp(-1, 1).mul(32767).to(torch.int16).cpu().numpy()
            temp = tempfile.NamedTemporaryFile(
                prefix=f"jarvis_{request_id}_",
                suffix=".wav",
                dir=output_dir,
                delete=False,
            )
            temp.close()
            path = Path(temp.name)
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(int(model.sr))
                handle.writeframes(samples.tobytes())
            emit(
                {
                    "id": request_id,
                    "ok": True,
                    "path": str(path),
                    "sample_rate": int(model.sr),
                    "sample_count": int(samples.size),
                }
            )
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            emit(
                {
                    "id": str(request.get("id", "unknown")) if isinstance(request, dict) else "unknown",
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
