import ast
import inspect
import unittest

import apps.voice_lab as voice_lab


class Repair5fVoiceLabCallbackTests(unittest.TestCase):
    def test_continuous_run_session_defines_every_subscribed_local_callback(self):
        source = inspect.getsource(voice_lab.run_session)
        tree = ast.parse(source)
        function = tree.body[0]

        local_functions = {
            node.name
            for node in function.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertIn("on_rejected", local_functions)
        self.assertIn("on_confirmed", local_functions)
        self.assertIn("on_acoustic_rescue", local_functions)

    def test_confidence_confirmed_subscription_uses_local_callback(self):
        source = inspect.getsource(voice_lab.run_session)
        self.assertIn(
            '"voice.speech.confidence_confirmed", on_confirmed',
            source,
        )


if __name__ == "__main__":
    unittest.main()
