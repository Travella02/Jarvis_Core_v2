import unittest

from tests.contract.test_voice_contracts import FakeSTT, FakeTTS
from core.voice import VoiceProviderRegistry


class VoiceRegistryTests(unittest.TestCase):
    def test_provider_swap_does_not_change_core_contract(self):
        first_stt, second_stt = FakeSTT(), FakeSTT()
        first_tts, second_tts = FakeTTS(), FakeTTS()
        registry = VoiceProviderRegistry(first_stt, first_tts)
        self.assertIs(registry.replace_stt(second_stt), first_stt)
        self.assertIs(registry.replace_tts(second_tts), first_tts)
        self.assertIs(registry.stt, second_stt)
        self.assertIs(registry.tts, second_tts)
