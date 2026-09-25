"""Provider-neutral local voice reference library for Jarvis Voice Lab.

Personal/reference audio is runtime user data. This module stores it under an
ignored runtime directory and exposes provider-neutral ``VoiceProfile`` objects
so TTS adapters can consume the selected reference without owning persistence.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import VoiceProfile


SCHEMA_VERSION = 1
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not cleaned:
        raise ValueError("voice profile name must contain at least one letter or number")
    return cleaned[:64]


def _safe_id(value: str, *, field: str) -> str:
    candidate = _slug(value)
    if candidate in {".", ".."}:
        raise ValueError(f"unsafe {field}")
    return candidate


@dataclass(frozen=True, slots=True)
class StoredVoiceReference:
    reference_id: str
    relative_audio_path: str
    transcript: str | None
    language: str
    created_at: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StoredVoiceReference":
        return cls(
            reference_id=str(payload["reference_id"]),
            relative_audio_path=str(payload["relative_audio_path"]),
            transcript=(str(payload["transcript"]) if payload.get("transcript") else None),
            language=str(payload.get("language") or "English"),
            created_at=str(payload.get("created_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "relative_audio_path": self.relative_audio_path,
            "transcript": self.transcript,
            "language": self.language,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class StoredVoiceProfile:
    profile_id: str
    display_name: str
    provider_hint: str | None
    primary_reference_id: str
    references: tuple[StoredVoiceReference, ...]
    settings: Mapping[str, Any]
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))
        if not self.references:
            raise ValueError("stored voice profile must contain at least one reference")
        if self.primary_reference_id not in {item.reference_id for item in self.references}:
            raise ValueError("primary_reference_id does not exist in references")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StoredVoiceProfile":
        if int(payload.get("schema_version", 0)) != SCHEMA_VERSION:
            raise ValueError("unsupported voice profile schema version")
        return cls(
            profile_id=str(payload["profile_id"]),
            display_name=str(payload["display_name"]),
            provider_hint=(str(payload["provider_hint"]) if payload.get("provider_hint") else None),
            primary_reference_id=str(payload["primary_reference_id"]),
            references=tuple(
                StoredVoiceReference.from_dict(item) for item in payload.get("references", [])
            ),
            settings=dict(payload.get("settings") or {}),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "display_name": self.display_name,
            "provider_hint": self.provider_hint,
            "primary_reference_id": self.primary_reference_id,
            "references": [item.to_dict() for item in self.references],
            "settings": dict(self.settings),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class VoiceReferenceLibrary:
    """Small local store for multiple named voices and their reference clips."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def ensure(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def list_profiles(self) -> list[StoredVoiceProfile]:
        if not self.root.is_dir():
            return []
        profiles: list[StoredVoiceProfile] = []
        for manifest in sorted(self.root.glob("*/profile.json")):
            try:
                profiles.append(self._read_manifest(manifest))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return sorted(profiles, key=lambda item: item.display_name.casefold())

    def get(self, profile_id: str) -> StoredVoiceProfile:
        profile_key = _safe_id(profile_id, field="profile_id")
        manifest = self.root / profile_key / "profile.json"
        if not manifest.is_file():
            raise FileNotFoundError(f"voice profile {profile_id!r} was not found in {self.root}")
        return self._read_manifest(manifest)

    def add_reference(
        self,
        *,
        display_name: str,
        source_audio: Path,
        transcript: str | None,
        language: str = "English",
        profile_id: str | None = None,
        provider_hint: str | None = None,
        make_primary: bool = True,
    ) -> StoredVoiceProfile:
        source = Path(source_audio).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        extension = source.suffix.lower()
        if extension not in SUPPORTED_AUDIO_EXTENSIONS:
            raise ValueError(
                f"unsupported reference audio extension {extension!r}; "
                f"supported={sorted(SUPPORTED_AUDIO_EXTENSIONS)}"
            )
        display = display_name.strip()
        if not display:
            raise ValueError("display_name must be non-empty")
        profile_key = _safe_id(profile_id or display, field="profile_id")
        profile_dir = self.ensure() / profile_key
        references_dir = profile_dir / "references"
        references_dir.mkdir(parents=True, exist_ok=True)

        existing: StoredVoiceProfile | None = None
        manifest = profile_dir / "profile.json"
        if manifest.is_file():
            existing = self._read_manifest(manifest)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base_reference_id = f"ref-{timestamp.lower()}"
        reference_id = base_reference_id
        suffix = 2
        while (references_dir / f"{reference_id}{extension}").exists():
            reference_id = f"{base_reference_id}-{suffix}"
            suffix += 1
        destination = references_dir / f"{reference_id}{extension}"
        temp_audio = destination.with_suffix(destination.suffix + ".tmp")
        shutil.copy2(source, temp_audio)
        temp_audio.replace(destination)

        now = _utc_now()
        reference = StoredVoiceReference(
            reference_id=reference_id,
            relative_audio_path=destination.relative_to(profile_dir).as_posix(),
            transcript=(transcript.strip() if transcript and transcript.strip() else None),
            language=(language.strip() or "English"),
            created_at=now,
        )
        references = list(existing.references) if existing else []
        references.append(reference)
        primary = (
            reference.reference_id
            if make_primary or existing is None
            else existing.primary_reference_id
        )
        profile = StoredVoiceProfile(
            profile_id=profile_key,
            display_name=display,
            provider_hint=provider_hint or (existing.provider_hint if existing else None),
            primary_reference_id=primary,
            references=tuple(references),
            settings=dict(existing.settings) if existing else {},
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._write_manifest(manifest, profile)
        return profile

    def resolve_voice_profile(
        self,
        profile_id: str,
        *,
        reference_id: str | None = None,
        provider_hint: str | None = None,
    ) -> VoiceProfile:
        stored = self.get(profile_id)
        chosen_id = reference_id or stored.primary_reference_id
        chosen = next(
            (item for item in stored.references if item.reference_id == chosen_id),
            None,
        )
        if chosen is None:
            raise KeyError(
                f"voice reference {chosen_id!r} does not exist in profile {stored.profile_id!r}"
            )
        profile_dir = self.root / stored.profile_id
        audio_path = (profile_dir / chosen.relative_audio_path).resolve()
        if profile_dir.resolve() not in audio_path.parents or not audio_path.is_file():
            raise FileNotFoundError(audio_path)
        settings = dict(stored.settings)
        settings.update(
            {
                "reference_text": chosen.transcript,
                "language": chosen.language,
                "library_profile_id": stored.profile_id,
                "library_reference_id": chosen.reference_id,
                "x_vector_only": chosen.transcript is None,
            }
        )
        return VoiceProfile(
            profile_id=stored.profile_id,
            display_name=stored.display_name,
            provider_hint=provider_hint or stored.provider_hint,
            reference_audio_path=str(audio_path),
            settings=settings,
        )

    @staticmethod
    def _read_manifest(path: Path) -> StoredVoiceProfile:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StoredVoiceProfile.from_dict(payload)

    @staticmethod
    def _write_manifest(path: Path, profile: StoredVoiceProfile) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
