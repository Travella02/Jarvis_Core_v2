"""Authoritative conversation/context data model for Jarvis Core v2."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from core.common.ids import CorrelationContext, new_id
from core.intelligence import IntelligenceContext


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class InputChannel(str, Enum):
    TYPED = "typed"
    VOICE = "voice"
    SYSTEM = "system"


class TranscriptRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ReferentKind(str, Enum):
    ENTITY = "entity"
    MEDIA = "media"
    TASK = "task"
    JOB = "job"
    TOOL_ACTION = "tool_action"
    APPROVAL = "approval"
    UI = "ui"


class HeardResponseState(str, Enum):
    NONE = "none"
    PARTIAL = "partial"
    COMPLETE = "complete"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class Referent:
    """A context object that words such as 'it' or 'that' may refer to."""

    entity_id: str
    kind: ReferentKind
    label: str
    source: str = "conversation"
    supported_actions: frozenset[str] = field(default_factory=frozenset)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.entity_id.strip():
            raise ValueError("entity_id must be non-empty")
        if not self.label.strip():
            raise ValueError("label must be non-empty")
        actions = frozenset(item.strip().lower() for item in self.supported_actions if item.strip())
        object.__setattr__(self, "supported_actions", actions)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "observed_at", _aware(self.observed_at))

    def supports(self, action: str | None) -> bool:
        if action is None:
            return True
        normalized = action.strip().lower()
        return not self.supported_actions or normalized in self.supported_actions

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "kind": self.kind.value,
            "label": self.label,
            "source": self.source,
            "supported_actions": sorted(self.supported_actions),
            "metadata": dict(self.metadata),
            "observed_at": self.observed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Referent":
        return cls(
            entity_id=str(data["entity_id"]),
            kind=ReferentKind(str(data["kind"])),
            label=str(data["label"]),
            source=str(data.get("source", "conversation")),
            supported_actions=frozenset(str(item) for item in data.get("supported_actions", ())),
            metadata=dict(data.get("metadata", {})),
            observed_at=datetime.fromisoformat(str(data["observed_at"])),
        )


@dataclass(frozen=True, slots=True)
class TranscriptEntry:
    entry_id: str
    role: TranscriptRole
    content: str
    channel: InputChannel
    turn_id: str | None
    created_at: datetime = field(default_factory=_utc_now)
    interrupted: bool = False

    def __post_init__(self) -> None:
        if not self.entry_id.strip():
            raise ValueError("entry_id must be non-empty")
        if not self.content.strip():
            raise ValueError("content must be non-empty")
        object.__setattr__(self, "created_at", _aware(self.created_at))

    @classmethod
    def create(
        cls,
        *,
        role: TranscriptRole,
        content: str,
        channel: InputChannel,
        turn_id: str | None,
        interrupted: bool = False,
    ) -> "TranscriptEntry":
        return cls(
            entry_id=new_id("msg"),
            role=role,
            content=content,
            channel=channel,
            turn_id=turn_id,
            interrupted=interrupted,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "role": self.role.value,
            "content": self.content,
            "channel": self.channel.value,
            "turn_id": self.turn_id,
            "created_at": self.created_at.isoformat(),
            "interrupted": self.interrupted,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TranscriptEntry":
        return cls(
            entry_id=str(data["entry_id"]),
            role=TranscriptRole(str(data["role"])),
            content=str(data["content"]),
            channel=InputChannel(str(data["channel"])),
            turn_id=str(data["turn_id"]) if data.get("turn_id") is not None else None,
            created_at=datetime.fromisoformat(str(data["created_at"])),
            interrupted=bool(data.get("interrupted", False)),
        )


@dataclass(slots=True)
class ConversationContext:
    """The single authoritative working context for one conversation.

    Providers receive snapshots of this object; they never own or mutate it.
    Subsystems should publish/update referents here instead of maintaining a
    competing interpretation of conversational focus.
    """

    conversation_id: str
    user_id: str
    speaker_id: str | None = None
    device_id: str | None = None
    current_focus_entity: Referent | None = None
    last_discussed_entity: Referent | None = None
    recent_referents: list[Referent] = field(default_factory=list)
    active_media: Referent | None = None
    active_task: Referent | None = None
    active_job: Referent | None = None
    last_tool_action: Referent | None = None
    pending_approval: Referent | None = None
    visible_ui_focus: Referent | None = None
    temporal_context: dict[str, Any] = field(default_factory=dict)
    working_memory_summary: str = ""
    recent_transcript: list[TranscriptEntry] = field(default_factory=list)
    heard_response_state: HeardResponseState = HeardResponseState.NONE
    heard_response_text: str = ""
    max_recent_referents: int = 32
    max_recent_transcript: int = 64

    def __post_init__(self) -> None:
        if not self.conversation_id.strip():
            raise ValueError("conversation_id must be non-empty")
        if not self.user_id.strip():
            raise ValueError("user_id must be non-empty")
        if self.max_recent_referents <= 0 or self.max_recent_transcript <= 0:
            raise ValueError("context history limits must be positive")

    @classmethod
    def create(
        cls,
        *,
        user_id: str,
        speaker_id: str | None = None,
        device_id: str | None = None,
    ) -> "ConversationContext":
        return cls(
            conversation_id=new_id("conversation"),
            user_id=user_id,
            speaker_id=speaker_id,
            device_id=device_id,
        )

    def record_referent(
        self,
        referent: Referent,
        *,
        focus: bool = False,
        discussed: bool = True,
    ) -> None:
        self.recent_referents = [
            item for item in self.recent_referents if item.entity_id != referent.entity_id
        ]
        self.recent_referents.insert(0, referent)
        del self.recent_referents[self.max_recent_referents :]
        if discussed:
            self.last_discussed_entity = referent
        if focus:
            self.current_focus_entity = referent

    def set_active_media(self, referent: Referent | None, *, focus: bool = False) -> None:
        if referent is not None and referent.kind is not ReferentKind.MEDIA:
            raise ValueError("active_media must be a media referent")
        self.active_media = referent
        if referent is not None:
            self.record_referent(referent, focus=focus, discussed=focus)

    def set_active_task(self, referent: Referent | None, *, focus: bool = False) -> None:
        if referent is not None and referent.kind is not ReferentKind.TASK:
            raise ValueError("active_task must be a task referent")
        self.active_task = referent
        if referent is not None:
            self.record_referent(referent, focus=focus, discussed=focus)

    def set_active_job(self, referent: Referent | None, *, focus: bool = False) -> None:
        if referent is not None and referent.kind is not ReferentKind.JOB:
            raise ValueError("active_job must be a job referent")
        self.active_job = referent
        if referent is not None:
            self.record_referent(referent, focus=focus, discussed=focus)

    def append_transcript(self, entry: TranscriptEntry) -> None:
        self.recent_transcript.append(entry)
        if len(self.recent_transcript) > self.max_recent_transcript:
            del self.recent_transcript[: -self.max_recent_transcript]

    def known_referents(self) -> tuple[Referent, ...]:
        ordered = (
            self.current_focus_entity,
            self.last_discussed_entity,
            *self.recent_referents,
            self.active_task,
            self.active_job,
            self.active_media,
            self.last_tool_action,
            self.pending_approval,
            self.visible_ui_focus,
        )
        result: list[Referent] = []
        seen: set[str] = set()
        for item in ordered:
            if item is None or item.entity_id in seen:
                continue
            seen.add(item.entity_id)
            result.append(item)
        return tuple(result)

    def to_intelligence_context(self, trace: CorrelationContext) -> IntelligenceContext:
        messages: list[dict[str, Any]] = []
        if self.working_memory_summary.strip():
            messages.append(
                {
                    "role": "system",
                    "content": f"Working memory summary: {self.working_memory_summary.strip()}",
                }
            )
        messages.extend(
            {"role": entry.role.value, "content": entry.content}
            for entry in self.recent_transcript
        )
        metadata = {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "speaker_id": self.speaker_id,
            "device_id": self.device_id,
            "current_focus_entity_id": (
                self.current_focus_entity.entity_id if self.current_focus_entity else None
            ),
            "temporal_context": dict(self.temporal_context),
        }
        return IntelligenceContext(trace=trace, messages=tuple(messages), metadata=metadata)

    def to_dict(self) -> dict[str, Any]:
        def maybe(item: Referent | None) -> dict[str, Any] | None:
            return item.to_dict() if item else None

        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "speaker_id": self.speaker_id,
            "device_id": self.device_id,
            "current_focus_entity": maybe(self.current_focus_entity),
            "last_discussed_entity": maybe(self.last_discussed_entity),
            "recent_referents": [item.to_dict() for item in self.recent_referents],
            "active_media": maybe(self.active_media),
            "active_task": maybe(self.active_task),
            "active_job": maybe(self.active_job),
            "last_tool_action": maybe(self.last_tool_action),
            "pending_approval": maybe(self.pending_approval),
            "visible_ui_focus": maybe(self.visible_ui_focus),
            "temporal_context": dict(self.temporal_context),
            "working_memory_summary": self.working_memory_summary,
            "recent_transcript": [item.to_dict() for item in self.recent_transcript],
            "heard_response_state": self.heard_response_state.value,
            "heard_response_text": self.heard_response_text,
            "max_recent_referents": self.max_recent_referents,
            "max_recent_transcript": self.max_recent_transcript,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ConversationContext":
        def maybe(value: Any) -> Referent | None:
            return Referent.from_dict(value) if isinstance(value, Mapping) else None

        return cls(
            conversation_id=str(data["conversation_id"]),
            user_id=str(data["user_id"]),
            speaker_id=str(data["speaker_id"]) if data.get("speaker_id") is not None else None,
            device_id=str(data["device_id"]) if data.get("device_id") is not None else None,
            current_focus_entity=maybe(data.get("current_focus_entity")),
            last_discussed_entity=maybe(data.get("last_discussed_entity")),
            recent_referents=[Referent.from_dict(item) for item in data.get("recent_referents", ())],
            active_media=maybe(data.get("active_media")),
            active_task=maybe(data.get("active_task")),
            active_job=maybe(data.get("active_job")),
            last_tool_action=maybe(data.get("last_tool_action")),
            pending_approval=maybe(data.get("pending_approval")),
            visible_ui_focus=maybe(data.get("visible_ui_focus")),
            temporal_context=dict(data.get("temporal_context", {})),
            working_memory_summary=str(data.get("working_memory_summary", "")),
            recent_transcript=[
                TranscriptEntry.from_dict(item) for item in data.get("recent_transcript", ())
            ],
            heard_response_state=HeardResponseState(str(data.get("heard_response_state", "none"))),
            heard_response_text=str(data.get("heard_response_text", "")),
            max_recent_referents=int(data.get("max_recent_referents", 32)),
            max_recent_transcript=int(data.get("max_recent_transcript", 64)),
        )
