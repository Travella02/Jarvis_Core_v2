import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "setup_whisper_cpp.ps1"


class WhisperSetupDownloadPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_large_model_download_uses_curl_retry_and_resume(self) -> None:
        self.assertIn('Get-Command "curl.exe"', self.text)
        self.assertIn('"--retry", "3"', self.text)
        self.assertIn('"--retry-all-errors"', self.text)
        self.assertIn('"--continue-at", "-"', self.text)
        self.assertNotIn('Invoke-WebRequest -Uri $ModelUrl -OutFile $ModelPath', self.text)

    def test_failed_previous_final_file_is_reused_as_partial(self) -> None:
        self.assertIn('$PartialPath = $ModelPath + ".partial"', self.text)
        self.assertIn('Move-Item $ModelPath $PartialPath -Force', self.text)
        self.assertIn('Preserved the existing bytes as a resumable partial download.', self.text)

    def test_bits_is_a_secondary_windows_fallback(self) -> None:
        self.assertIn('Import-Module BitsTransfer', self.text)
        self.assertIn('Start-BitsTransfer', self.text)
        self.assertIn('falling back to BITS', self.text)

    def test_checksum_is_verified_before_atomic_final_install(self) -> None:
        verify_index = self.text.index('$ActualSha1 = Get-FileSha1 $PartialPath')
        move_index = self.text.index('Move-Item $PartialPath $ModelPath -Force')
        self.assertLess(verify_index, move_index)
        self.assertIn('Whisper model SHA1 mismatch after a fresh redownload', self.text)

    def test_bad_resumed_download_gets_one_clean_redownload(self) -> None:
        self.assertIn('Retrying once from byte 0', self.text)
        self.assertIn('Remove-Item $PartialPath -Force', self.text)
        self.assertIn('Fresh Whisper model redownload failed', self.text)


if __name__ == "__main__":
    unittest.main()
