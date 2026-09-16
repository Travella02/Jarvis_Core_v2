"""Run the deterministic 0.0.3 Conversation Core benchmark."""

from __future__ import annotations

from core.conversation import run_conversation_benchmark


def main() -> int:
    results = run_conversation_benchmark()
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        suffix = f" - {result.detail}" if result.detail and not result.passed else ""
        print(f"[{marker}] {result.name}{suffix}")
    passed = sum(item.passed for item in results)
    print(f"Result: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
