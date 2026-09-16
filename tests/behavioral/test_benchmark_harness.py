import unittest
from pathlib import Path

from core.intelligence import (
    ContextLimits,
    IntelligenceEvent,
    IntelligenceEventType,
    IntelligenceProvider,
    ProviderHealth,
    ProviderHealthState,
    ProviderMetadata,
    load_cases,
    run_benchmark,
)
from core.tools import ToolRequest


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests" / "behavioral" / "corpus" / "intelligence_provider_seed.json"


class CorpusFakeProvider(IntelligenceProvider):
    @property
    def metadata(self):
        return ProviderMetadata(provider="fake", model="benchmark")

    def supports_tools(self):
        return True

    def supports_vision(self):
        return False

    def supports_reasoning_levels(self):
        return True

    def context_limits(self):
        return ContextLimits()

    async def cancel(self, request_id):
        return None

    async def health(self):
        return ProviderHealth(ProviderHealthState.HEALTHY)

    async def stream_response(self, context, tools, reasoning_policy, cancellation_token):
        prompt = str(context.messages[-1]["content"])
        if "JARVIS_PROVIDER_OK" in prompt:
            yield IntelligenceEvent(IntelligenceEventType.TEXT_DELTA, text_delta="JARVIS_PROVIDER_OK")
        elif "open a new tab" in prompt.lower():
            yield IntelligenceEvent(
                IntelligenceEventType.TOOL_REQUEST,
                tool_request=ToolRequest(
                    trace=context.trace,
                    tool_name="browser_open_new_tab",
                    operation="invoke",
                    arguments={},
                ),
            )
        else:
            yield IntelligenceEvent(
                IntelligenceEventType.TOOL_REQUEST,
                tool_request=ToolRequest(
                    trace=context.trace,
                    tool_name="jarvis_benchmark_probe",
                    operation="invoke",
                    arguments={"value": "benchmark-tool-ok"},
                ),
            )
        yield IntelligenceEvent(IntelligenceEventType.COMPLETED)


class BenchmarkHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_seed_corpus_runs_through_provider_contract(self) -> None:
        cases = load_cases(CORPUS)
        self.assertEqual(len(cases), 3)
        run = await run_benchmark(CorpusFakeProvider(), cases)
        self.assertTrue(run.passed)
        self.assertEqual(run.passed_count, 3)

    def test_corpus_contains_v1_natural_phrase_regression(self) -> None:
        cases = load_cases(CORPUS)
        matching = [case for case in cases if "open a new tab" in case.prompt.lower()]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].expectation.tool_name, "browser_open_new_tab")


if __name__ == "__main__":
    unittest.main()
