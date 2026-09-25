import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup_whisper_cpp.ps1"


class WhisperSetupToolchainPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_cuda_build_pins_visual_studio_2022_generator_and_x64(self) -> None:
        self.assertIn('Generator = "Visual Studio 17 2022"', self.text)
        self.assertIn('Architecture = "x64"', self.text)
        self.assertIn('"-G", $CudaToolchain.Generator', self.text)
        self.assertIn('"-A", $CudaToolchain.Architecture', self.text)
        self.assertIn('CMAKE_GENERATOR_INSTANCE=', self.text)
        self.assertIn('Toolset = "cuda=$CudaRoot,host=x64"', self.text)
        self.assertIn('"-T", $CudaToolchain.Toolset', self.text)

    def test_vs2022_discovery_requires_cpp_tooling(self) -> None:
        self.assertIn('"[17.0,18.0)"', self.text)
        self.assertIn('Microsoft.VisualStudio.Component.VC.Tools.x86.x64', self.text)
        self.assertIn('Visual Studio 2022 Build Tools with Desktop development with C++', self.text)
        self.assertIn('extras\\visual_studio_integration\\MSBuildExtensions', self.text)
        self.assertIn('Visual Studio integration files were not found', self.text)

    def test_backend_specific_build_tree_avoids_failed_generator_cache(self) -> None:
        self.assertIn('("build-" + $Backend)', self.text)
        self.assertIn('Reset-IncompatibleCMakeCache', self.text)


if __name__ == "__main__":
    unittest.main()
