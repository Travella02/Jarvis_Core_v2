"""0.1.5.1: fail-closed Core-owned tool dispatch and approved-site browser opener.

NOT a model tool callback. Callers must supply independent Core-side user evidence.
No general URL opening, shell access, raw file access, or implicit authorization.
"""
from __future__ import annotations

import asyncio
import re
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from core.tools.contracts import ToolRequest, ToolResult, ToolResultStatus

# Reviewable exact capability whitelist, not derived from a model argument.
APPROVED_SITES = {"youtube": "https://www.youtube.com/"}
SUPPORTED_TOOL = "desktop_browser"
SUPPORTED_OPERATION = "open_approved_site"


@dataclass(frozen=True, slots=True)
class ConfirmedUserAction:
    """Evidence originating in trusted desktop Core, NEVER AI-generated arguments.

    This 0.1.5.1 contract is temporary single-user, local-desktop only. A
    multi-user identity/permission implementation is required before launch.
    """

    turn_id: str
    transcript: str
    confirmed: bool
    local_desktop: bool


class BrowserLauncher(Protocol):
    def __call__(self, url: str) -> bool: ...


def _requested_site(transcript: str) -> str | None:
    """Conservative explicit-command boundary; not a general speech validator.

    Only an isolated affirmative opening command permits a visible local side
    effect. Quoted instructions, explanatory questions, negations and compound
    actions must remain unexecutable until later confirmation UX exists.
    """
    text = re.sub(r"\s+", " ", transcript.strip().lower()).strip(' .!?')
    # Independent authorization uses only the committed user's exact utterance,
    # NEVER the model's selected tool or model-provided arguments. Keep this
    # grammar intentionally narrow: a direct affirmative request for YouTube,
    # not quoted speech, a negation, a conditional, or a compound instruction.
    # Include optional conversational lead-ins but not conditional or combined
    # requests. A standalone "hey" before the command does not itself provide
    # authorization; the rest of the utterance must still match completely.
    prefix = r"(?:(?:hey\s+)?(?:jarvis|jervis)\s*[,,:]?\s*|hey\s+)?"
    lead_in = r"(?:go\s+ahead\s+and\s+)?"
    request = (
        r"(?:please\s+)?(?:"
        + lead_in + r"(?:open|launch)\s+"
        + r"|(?:can|could|would|will)\s+you\s+(?:please\s+)?" + lead_in + r"(?:open|launch)\s+"
        r")"
        r"(?:the\s+)?youtube(?:\.com)?"
        r"(?:\s+for\s+me)?(?:\s+please)?"
    )
    return "youtube" if re.fullmatch(prefix + request, text) is not None else None


class CoreToolGateway:
    """Explicit registration, policy, execution and bounded per-session replay guard.

    The gateway does not decide whether a request is conversationally useful;
    the model can *suggest* a ToolRequest. Only independent user evidence can
    authorize it. Calls are serialized to prevent duplicate side effects.
    """

    def __init__(self, *, launch_browser: BrowserLauncher | None = None) -> None:
        self._launch = launch_browser or webbrowser.open_new_tab
        self._lock = asyncio.Lock()
        self._replays: dict[tuple[str, str], tuple[str, ToolResult]] = {}

    def available_tools(self) -> tuple[tuple[str, str], ...]:
        return ((SUPPORTED_TOOL, SUPPORTED_OPERATION),)

    async def execute(self, request: ToolRequest, *, evidence: ConfirmedUserAction | None) -> ToolResult:
        def outcome(status: ToolResultStatus, *, code: str | None = None, detail: str | None = None,
                    output: dict | None = None) -> ToolResult:
            return ToolResult(trace=request.trace, tool_name=request.tool_name,
                              operation=request.operation, status=status, output=output or {},
                              provider_call_id=request.provider_call_id,
                              error_code=code, error_message=detail)

        # The tool/operation pair and argument shape must be recognized *before*
        # inspecting any external intent or touching the OS.
        if (request.tool_name, request.operation) not in self.available_tools():
            return outcome(ToolResultStatus.DENIED, code="unknown_capability")
        site = request.arguments.get("site")
        if set(request.arguments) != {"site"} or not isinstance(site, str) or site not in APPROVED_SITES:
            return outcome(ToolResultStatus.DENIED, code="invalid_or_unapproved_site")
        if (evidence is None or not evidence.confirmed or not evidence.local_desktop
                or not request.trace.turn_id or request.trace.turn_id != evidence.turn_id):
            return outcome(ToolResultStatus.DENIED, code="missing_independent_user_authorization")
        if _requested_site(evidence.transcript) != site:
            return outcome(ToolResultStatus.DENIED, code="user_request_does_not_authorize_action")

        replay_key = (evidence.turn_id, request.idempotency_key or request.trace.request_id)
        fingerprint = f"{request.tool_name}/{request.operation}/{site}"
        async with self._lock:
            cached = self._replays.get(replay_key)
            if cached:
                if cached[0] != fingerprint:
                    return outcome(ToolResultStatus.DENIED, code="replay_key_conflict")
                return cached[1]
            try:
                # A true return value means the OS/browser launch was accepted;
                # it does NOT prove the page finished loading or was visible.
                launched = self._launch(APPROVED_SITES[site]) is True
            except Exception:
                launched = False
            result = (outcome(ToolResultStatus.SUCCEEDED, output={
                "site": site, "url": APPROVED_SITES[site],
                "browser_launch_accepted": True, "page_loaded_verified": False,
                "user_message": "I sent YouTube to your default browser.",
            }) if launched else outcome(ToolResultStatus.FAILED, code="browser_launch_failed",
                                      detail="The default browser did not accept the launch request."))
            # Store both success and failure: an ambiguous retry must never
            # silently execute an action twice. Per-instance cache is ephemeral.
            self._replays[replay_key] = (fingerprint, result)
            return result
