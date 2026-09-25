"""Resumable Qwen3-TTS model download helper for the isolated runtime."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from huggingface_hub import snapshot_download


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    parser.add_argument("--local-dir", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    args = parser.parse_args()
    target = Path(args.local_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    last: Exception | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            print(f"Qwen3-TTS model download attempt {attempt}/{args.attempts}...")
            snapshot_download(
                repo_id=args.repo,
                local_dir=str(target),
                max_workers=4,
            )
            required = (target / "config.json", target / "model.safetensors")
            if not all(path.is_file() and path.stat().st_size > 0 for path in required):
                raise RuntimeError("snapshot completed without required model files")
            print(f"Qwen3-TTS model assets ready: {target}")
            return 0
        except Exception as exc:  # pragma: no cover - network path
            last = exc
            print(f"WARNING: download attempt {attempt} failed: {type(exc).__name__}: {exc}")
            if attempt < args.attempts:
                time.sleep(min(2 * attempt, 10))
    raise SystemExit(f"Unable to download Qwen3-TTS model after {args.attempts} attempts: {last}")


if __name__ == "__main__":
    raise SystemExit(main())
