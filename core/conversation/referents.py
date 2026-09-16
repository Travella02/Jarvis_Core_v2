"""Deterministic referent resolution over the authoritative ConversationContext."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.conversation.models import ConversationContext, Referent


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ReferentResolution:
    status: ResolutionStatus
    referent: Referent | None = None
    candidates: tuple[Referent, ...] = ()
    reason: str = ""

    @property
    def needs_clarification(self) -> bool:
        return self.status is ResolutionStatus.AMBIGUOUS


class ReferentResolver:
    """Resolve explicit/deictic references without letting subsystems race.

    Priority is intentional: explicit wording > current conversational focus >
    last discussed entity > a single compatible active/recent candidate. If
    multiple materially plausible candidates remain, return AMBIGUOUS rather
    than silently choosing whichever subsystem happens to react first.
    """

    _DEICTIC = {"it", "that", "this", "that one", "this one", "the one"}

    def resolve(
        self,
        context: ConversationContext,
        mention: str,
        *,
        action: str | None = None,
        explicit_entity_id: str | None = None,
    ) -> ReferentResolution:
        normalized = " ".join(mention.strip().lower().split())
        action_normalized = action.strip().lower() if action and action.strip() else None
        known = context.known_referents()

        if explicit_entity_id:
            matches = tuple(item for item in known if item.entity_id == explicit_entity_id)
            if len(matches) == 1 and matches[0].supports(action_normalized):
                return ReferentResolution(
                    ResolutionStatus.RESOLVED,
                    matches[0],
                    matches,
                    "explicit entity id",
                )
            return ReferentResolution(
                ResolutionStatus.UNRESOLVED,
                candidates=matches,
                reason="explicit entity id not found or action incompatible",
            )

        if normalized and normalized not in self._DEICTIC:
            explicit_matches = tuple(
                item
                for item in known
                if item.supports(action_normalized)
                and (
                    normalized == item.entity_id.lower()
                    or normalized == item.label.lower()
                    or item.label.lower() in normalized
                )
            )
            if len(explicit_matches) == 1:
                return ReferentResolution(
                    ResolutionStatus.RESOLVED,
                    explicit_matches[0],
                    explicit_matches,
                    "explicit wording",
                )
            if len(explicit_matches) > 1:
                return ReferentResolution(
                    ResolutionStatus.AMBIGUOUS,
                    candidates=explicit_matches,
                    reason="explicit wording matches multiple referents",
                )

        for candidate, reason in (
            (context.current_focus_entity, "current conversational focus"),
            (context.last_discussed_entity, "last discussed entity"),
        ):
            if candidate is not None and candidate.supports(action_normalized):
                return ReferentResolution(
                    ResolutionStatus.RESOLVED,
                    candidate,
                    (candidate,),
                    reason,
                )

        compatible: list[Referent] = []
        seen: set[str] = set()
        for candidate in (
            context.active_task,
            context.active_job,
            context.active_media,
            *context.recent_referents,
        ):
            if (
                candidate is not None
                and candidate.entity_id not in seen
                and candidate.supports(action_normalized)
            ):
                seen.add(candidate.entity_id)
                compatible.append(candidate)

        if len(compatible) == 1:
            return ReferentResolution(
                ResolutionStatus.RESOLVED,
                compatible[0],
                tuple(compatible),
                "single compatible context referent",
            )
        if len(compatible) > 1:
            return ReferentResolution(
                ResolutionStatus.AMBIGUOUS,
                candidates=tuple(compatible),
                reason="multiple compatible context referents require clarification",
            )
        return ReferentResolution(
            ResolutionStatus.UNRESOLVED,
            reason="no compatible referent in authoritative context",
        )
