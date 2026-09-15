import dataclasses
import unittest

from core.common.ids import CorrelationContext
from core.tools import ToolDefinition, ToolRequest


class ToolAuthorityBoundaryTests(unittest.TestCase):
    def test_tool_definition_contains_metadata_not_execution_handle(self) -> None:
        field_names = {field.name for field in dataclasses.fields(ToolDefinition)}
        self.assertEqual(field_names, {"name", "description", "input_schema"})
        forbidden = {"execute", "executor", "callback", "handler", "permission"}
        self.assertTrue(field_names.isdisjoint(forbidden))

    def test_tool_request_is_intent_not_callable_authority(self) -> None:
        request = ToolRequest(
            trace=CorrelationContext("corr", "req"),
            tool_name="browser",
            operation="open_tab",
            arguments={"url": "https://example.invalid"},
        )
        self.assertFalse(any(callable(value) for value in request.arguments.values()))
        with self.assertRaises(TypeError):
            request.arguments["url"] = "changed"  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
