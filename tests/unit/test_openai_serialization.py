import unittest

from core.common.ids import CorrelationContext
from core.intelligence import IntelligenceContext, ReasoningPolicy
from core.tools import ToolDefinition
from providers.intelligence.openai.config import OpenAIProviderConfig
from providers.intelligence.openai.serialization import (
    parse_tool_arguments,
    reasoning_effort,
    serialize_messages,
    serialize_tools,
)


class OpenAISerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trace = CorrelationContext("corr", "req", "turn")
        self.config = OpenAIProviderConfig(api_key="test-key")

    def test_messages_are_plain_provider_payloads(self) -> None:
        context = IntelligenceContext(
            trace=self.trace,
            messages=(
                {"role": "developer", "content": "Be concise."},
                {"role": "user", "content": "Hello"},
            ),
        )
        self.assertEqual(
            serialize_messages(context),
            [
                {"role": "developer", "content": "Be concise."},
                {"role": "user", "content": "Hello"},
            ],
        )

    def test_tools_use_responses_function_shape_without_executor(self) -> None:
        tools = serialize_tools(
            (
                ToolDefinition(
                    name="browser_open_new_tab",
                    description="Request a new browser tab",
                    input_schema={"type": "object", "properties": {}},
                ),
            )
        )
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[0]["name"], "browser_open_new_tab")
        self.assertIn("parameters", tools[0])
        self.assertNotIn("function", tools[0])
        self.assertNotIn("executor", tools[0])

    def test_reasoning_policy_maps_provider_neutral_levels(self) -> None:
        self.assertEqual(reasoning_effort(ReasoningPolicy(level="auto"), self.config), "medium")
        self.assertEqual(reasoning_effort(ReasoningPolicy(level="quick"), self.config), "low")
        self.assertEqual(reasoning_effort(ReasoningPolicy(level="standard"), self.config), "medium")
        self.assertEqual(reasoning_effort(ReasoningPolicy(level="high"), self.config), "high")
        self.assertEqual(reasoning_effort(ReasoningPolicy(level="extreme"), self.config), "max")

    def test_tool_arguments_must_be_json_object(self) -> None:
        self.assertEqual(parse_tool_arguments('{"value":"ok"}'), {"value": "ok"})
        with self.assertRaises(ValueError):
            parse_tool_arguments("[]")
        with self.assertRaises(ValueError):
            parse_tool_arguments("not-json")


if __name__ == "__main__":
    unittest.main()
