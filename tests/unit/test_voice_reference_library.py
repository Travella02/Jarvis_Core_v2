import tempfile
import unittest
from pathlib import Path

from core.voice import VoiceReferenceLibrary


class VoiceReferenceLibraryTests(unittest.TestCase):
    def _audio(self, root: Path, name: str, payload: bytes = b"RIFFtest") -> Path:
        path = root / name
        path.write_bytes(payload)
        return path

    def test_library_lazily_creates_private_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "references"
            library = VoiceReferenceLibrary(root)
            self.assertFalse(root.exists())
            self.assertEqual(library.ensure(), root)
            self.assertTrue(root.is_dir())

    def test_multiple_named_voices_coexist(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            library = VoiceReferenceLibrary(base / "references")
            first = library.add_reference(
                display_name="Tanner Test",
                source_audio=self._audio(base, "tanner.wav"),
                transcript="This is Tanner.",
                language="English",
                provider_hint="qwen3",
            )
            second = library.add_reference(
                display_name="Jarvis Voice",
                source_audio=self._audio(base, "jarvis.wav", b"RIFFother"),
                transcript="This is Jarvis.",
                language="English",
                provider_hint="qwen3",
            )
            self.assertNotEqual(first.profile_id, second.profile_id)
            self.assertEqual([item.profile_id for item in library.list_profiles()], ["jarvis-voice", "tanner-test"])

    def test_existing_voice_can_hold_multiple_reference_clips(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            library = VoiceReferenceLibrary(base / "references")
            profile = library.add_reference(
                display_name="Tanner",
                source_audio=self._audio(base, "one.wav"),
                transcript="Reference one.",
            )
            updated = library.add_reference(
                display_name="Tanner",
                profile_id=profile.profile_id,
                source_audio=self._audio(base, "two.wav", b"RIFFtwo"),
                transcript="Reference two.",
            )
            self.assertEqual(len(updated.references), 2)
            self.assertEqual(updated.primary_reference_id, updated.references[-1].reference_id)
            self.assertTrue((library.root / "tanner" / "references").is_dir())

    def test_resolve_returns_provider_neutral_voice_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            library = VoiceReferenceLibrary(base / "references")
            stored = library.add_reference(
                display_name="Tanner",
                source_audio=self._audio(base, "voice.wav"),
                transcript="A clean reference sentence.",
                language="English",
                provider_hint="qwen3",
            )
            resolved = library.resolve_voice_profile(stored.profile_id)
            self.assertEqual(resolved.profile_id, "tanner")
            self.assertEqual(resolved.provider_hint, "qwen3")
            self.assertTrue(Path(resolved.reference_audio_path).is_file())
            self.assertEqual(resolved.settings["reference_text"], "A clean reference sentence.")
            self.assertEqual(resolved.settings["language"], "English")
            self.assertFalse(resolved.settings["x_vector_only"])

    def test_profile_without_transcript_resolves_as_xvector_only(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            library = VoiceReferenceLibrary(base / "references")
            stored = library.add_reference(
                display_name="Transcript Free",
                source_audio=self._audio(base, "voice.wav"),
                transcript=None,
            )
            resolved = library.resolve_voice_profile(stored.profile_id)
            self.assertIsNone(resolved.settings["reference_text"])
            self.assertTrue(resolved.settings["x_vector_only"])


if __name__ == "__main__":
    unittest.main()
