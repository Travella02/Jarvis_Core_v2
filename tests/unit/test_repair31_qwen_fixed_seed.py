import unittest
from unittest.mock import Mock

from providers.tts.qwen3_streaming_candidate import (
    Qwen3StreamingConfig,
    Qwen3StreamingProvider,
)
from providers.tts.qwen3_streaming_candidate.live_sidecar import _reset_rng


class _FakeCuda:
    def __init__(self):
        self.seed = None
    def is_available(self):
        return True
    def manual_seed_all(self, seed):
        self.seed = seed


class _FakeTorch:
    def __init__(self):
        self.seed = None
        self.cuda = _FakeCuda()
    def manual_seed(self, seed):
        self.seed = seed


class _FakeNumpyRandom:
    def __init__(self):
        self.value = None
    def seed(self, seed):
        self.value = seed


class _FakeNumpy:
    def __init__(self):
        self.random = _FakeNumpyRandom()


class Repair31QwenFixedSeedTests(unittest.TestCase):
    def test_default_preserves_repair27_random_sampling(self):
        config = Qwen3StreamingConfig()
        self.assertIsNone(config.fixed_seed)
        provider = Qwen3StreamingProvider(config)
        self.assertEqual(provider.metadata.extra["seed_strategy"], "upstream-random")

    def test_fixed_seed_metadata_reports_per_request_reset(self):
        provider = Qwen3StreamingProvider(Qwen3StreamingConfig(fixed_seed=12345))
        self.assertEqual(provider.metadata.extra["fixed_seed"], 12345)
        self.assertEqual(provider.metadata.extra["seed_strategy"], "per-request-reset")

    def test_reset_rng_seeds_numpy_torch_and_cuda(self):
        np = _FakeNumpy()
        torch = _FakeTorch()
        _reset_rng(12345, np, torch)
        self.assertEqual(np.random.value, 12345)
        self.assertEqual(torch.seed, 12345)
        self.assertEqual(torch.cuda.seed, 12345)

    def test_none_seed_is_noop(self):
        np = _FakeNumpy()
        torch = _FakeTorch()
        _reset_rng(None, np, torch)
        self.assertIsNone(np.random.value)
        self.assertIsNone(torch.seed)
        self.assertIsNone(torch.cuda.seed)

    def test_invalid_seed_is_rejected(self):
        with self.assertRaises(ValueError):
            Qwen3StreamingConfig(fixed_seed=-1)
        with self.assertRaises(ValueError):
            Qwen3StreamingConfig(fixed_seed=0x100000000)


if __name__ == "__main__":
    unittest.main()
