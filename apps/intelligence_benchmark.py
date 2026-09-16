"""Run the 0.0.2 provider benchmark corpus against the configured OpenAIProvider."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from core.intelligence import load_cases, run_benchmark
from providers.intelligence.openai import OpenAIProvider, OpenAIProviderConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT_ROOT / "tests" / "behavioral" / "corpus" / "intelligence_provider_seed.json"


async def _run(path: Path) -> int:
    provider = OpenAIProvider(OpenAIProviderConfig.from_env(env_file=PROJECT_ROOT / ".env"))
    run = await run_benchmark(provider, load_cases(path))
    for result in run.results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"[{marker}] {result.case_id}")
        for failure in result.failures:
            print(f"       {failure}")
    print(f"Result: {run.passed_count}/{len(run.results)} passed")
    return 0 if run.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis intelligence provider benchmark")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.corpus))


if __name__ == "__main__":
    raise SystemExit(main())
