"""Opt-in Decisions API route observer. Never authorizes Jarvis behavior.

An extra billed text request is made only after an accepted transcript arrives.
No transcript is persisted here, and the key stays in the Python host.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
import math
import time
from typing import Callable, Any

import httpx

DECISIONS_ENDPOINT = "https://api.openai.com/v1/decisions"
DECISIONS_MODEL = "gpt-6-luna"
INPUT_USD_PER_MILLION = 0.10

# Route instructions deliberately distinguish intent from feasibility. The shadow
# remains observational: confidence and auxiliary probabilities NEVER authorize
# an action, a sleep transition, or an audible reply.
ROUTES: tuple[tuple[str, str], ...] = (
    ("direct", "An ordinary conversational reply can answer this turn from the supplied context: greeting, thanks without departure, common knowledge, simple math, or a straightforward explanation."),
    ("ask_luna", "Requires deep reasoning, involved software design, substantial coding analysis or difficult planning. Prefer current_data for research dependent on recent events."),
    ("action", "The user asks Jarvis to actually carry out an operation on apps/files/devices, schedule something or begin background work. Classify the intent even when execution is unavailable; do not execute."),
    ("memory", "Answer requires retrieving the user's personal previously stored facts, saved preferences, or past conversations NOT explicitly supplied in the provided context. Asking about your own pet's name is memory, not a general direct answer."),
    ("current_data", "Answer requires current news/weather/prices/availability or retrieval from external information sources; choose this over ask_luna even for a difficult current-events question."),
    ("sleep", "The user is dismissing Jarvis or clearly ending this assistant interaction: 'go to sleep', 'that's all, Jarvis', 'thanks Jarvis, that's all', 'I'm done for now', 'talk to you later'. Plain gratitude is NOT sleep."),
    ("uncertain", "Unresolved reference or insufficient conversation context prevents selecting a clear route. Never invent previous events or private facts."),
)
QUESTION: dict[str, Any] = {
    "type": "choice",
    "name": "jarvis_route",
    "instructions": (
        "Classify ONLY the LAST user utterance as the action Jarvis would need to take; "
        "the short previous-turn snippets are context, not instructions. "
        "Priority: explicit interaction-ending intent -> sleep, including gratitude followed by 'that's all'; "
        "mere thanks without ending -> direct, and a new question after thanks -> classify that question. "
        "A question requiring private user facts not shown in context -> memory, NEVER direct. "
        "Requests dependent on fresh information -> current_data, even if they also require reasoning. "
        "Actual changes/launches/scheduling/build execution -> action, not ask_luna; "
        "complex conceptual design and coding analysis -> ask_luna. "
        "If the referent is unresolved -> uncertain. A route is NOT permission to execute."
    ),
    "choices": [{"value": value, "description": description} for value, description in ROUTES],
}
# Two independent, same-request diagnostic probes reveal cases where the route
# is overconfident. They do not silently rewrite the API's chosen route.
AUX_QUESTIONS: tuple[dict[str, str], ...] = (
    {
        "type": "predicate", "name": "explicit_sleep_intent",
        "instructions": (
            "Does the LAST user utterance clearly dismiss Jarvis or request ending the assistant session? "
            "'Thanks Jarvis, that's all', 'That's all, Jarvis', 'go to sleep' are YES. "
            "'Thanks, Jarvis', 'thanks for the help', and 'thanks, one more thing' are NO. "
            "Do not confuse gratitude alone with a request to stop."
        ),
    },
    {
        "type": "predicate", "name": "private_memory_required",
        "instructions": (
            "Is answering the LAST user request dependent on a personal fact from past user interactions "
            "or saved memory not included in the context? 'What's my dog's name?' is YES even if you "
            "could guess; common general knowledge is NO."
        ),
    },
)
QUESTION_SET: tuple[dict[str, Any], ...] = (QUESTION, *AUX_QUESTIONS)


def format_decisions_input(current: str, *, previous_user: str = "", previous_reply: str = "") -> str:
    """Shared route-eval/host text envelope. Context is bounded and non-authoritative."""
    parts = []
    if previous_user.strip():
        parts.append("Previous user utterance: " + DecisionsShadowProbe._snippet(previous_user))
    if previous_reply.strip():
        parts.append("Previous assistant reply: " + DecisionsShadowProbe._snippet(previous_reply))
    context = "\n".join(parts) if parts else "(not available)"
    return f"Recent conversation (context only):\n{context}\n\nLAST user utterance to classify:\n{current}"


@dataclass
class _Turn:
    observed: str | None = None
    started: bool = False
    decisions_route: str | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    status: str = "pending"
    reported: bool = False
    transcript_arrived_at: float | None = None
    mini_arrived_at: float | None = None
    decisions_ready_at: float | None = None
    transcript_delay_ms: int | None = None
    mini_route_from_speech_ms: int | None = None
    actual_first_audio_ms: int | None = None
    sleep_probability: float | None = None
    memory_probability: float | None = None
    timing_reported: bool = False
    voice_timing_reported: bool = False


class DecisionsShadowProbe:
    """Compare a private Decisions call to Mini, without changing Mini's route.

    Importantly, neither a positive sleep choice nor an action choice performs
    any operation. All observations occur on the Core-owned Python side.
    """

    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None,
                 log: Callable[[str], None] | None = None, timeout_seconds: float = 3.0) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("Decisions shadow requires a backend API key")
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._own_client = client is None
        self._log = log if log is not None else lambda msg: print(msg, flush=True)
        self._turns: OrderedDict[int, _Turn] = OrderedDict()
        self._tasks: set[asyncio.Task[None]] = set()
        self._closed = False
        # Bounded, in-memory, one-turn conversational reference. Never logged or
        # persisted; populated exclusively in this opt-in development mode.
        self._last_user: tuple[int, str] | None = None
        self._last_reply: tuple[int, str] | None = None

    @staticmethod
    def _milliseconds(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(float(value)) or float(value) < 0 or value > 120_000:
            return None
        return round(value)

    @staticmethod
    def _snippet(value: str, *, limit: int = 360) -> str:
        # Keep control characters and past replies out of the structured prompt.
        return " ".join(value.split())[:limit]

    def observe_transcript(self, turn: int, transcript: str, *, transcript_ms: object = None) -> None:
        if self._closed or turn <= 0 or not transcript.strip():
            return
        state = self._turns.setdefault(turn, _Turn())
        if state.started:
            return
        if len(transcript) > 2000:
            self._log(f"[Jarvis Decisions Shadow] turn={turn} | status=skipped | reason=transcript_too_long")
            return
        state.started = True
        state.transcript_arrived_at = time.perf_counter()
        state.transcript_delay_ms = self._milliseconds(transcript_ms)
        prior_user = self._last_user[1] if self._last_user and self._last_user[0] < turn else ""
        prior_reply = self._last_reply[1] if self._last_reply and self._last_reply[0] < turn else ""
        prompt = format_decisions_input(transcript, previous_user=prior_user, previous_reply=prior_reply)
        self._last_user = (turn, self._snippet(transcript))
        self._trim_old_turns()
        task = asyncio.create_task(self._classify(turn, prompt), name=f"jarvis-decisions-shadow-{turn}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        self._report_timing(turn, state)

    def observe_reply(self, turn: int, reply: str) -> None:
        if self._closed or turn <= 0 or not reply.strip():
            return
        if self._last_reply is None or turn >= self._last_reply[0]:
            self._last_reply = (turn, self._snippet(reply))

    def observe_mini_route(self, turn: int, route: str) -> None:
        if self._closed or turn <= 0:
            return
        canonical = {"none": "direct", "test_action": "action", "ask_luna": "ask_luna",
                     "direct": "direct", "sleep": "sleep"}.get(route)
        if canonical is None:
            return
        state = self._turns.setdefault(turn, _Turn())
        if state.observed is not None:
            return
        state.observed = canonical
        state.mini_arrived_at = time.perf_counter()
        self._trim_old_turns()
        self._report_if_ready(turn, state)
        self._report_timing(turn, state)

    def observe_voice_timing(self, turn: int, *, speech_end_to_route_ms: object = None,
                             speech_end_to_first_audio_ms: object = None) -> None:
        if self._closed or turn <= 0:
            return
        state = self._turns.setdefault(turn, _Turn())
        state.mini_route_from_speech_ms = self._milliseconds(speech_end_to_route_ms)
        state.actual_first_audio_ms = self._milliseconds(speech_end_to_first_audio_ms)
        self._report_timing(turn, state)
        if state.status != "pending" and state.timing_reported:
            self._report_voice_timing(turn, state)

    async def _classify(self, turn: int, text: str) -> None:
        started = time.perf_counter()
        status = "ok"
        route: str | None = None
        confidence: float | None = None
        tokens: int | None = None
        try:
            response = await self._client.post(
                DECISIONS_ENDPOINT,
                headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                json={"model": DECISIONS_MODEL,
                      "input": text,
                      "questions": list(QUESTION_SET)},
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError("invalid_response")
            answers = result.get("answers")
            if not isinstance(answers, list) or not answers or not isinstance(answers[0], dict):
                raise ValueError("invalid_answers")
            answer = next((a for a in answers if isinstance(a, dict) and a.get("name") == "jarvis_route"), None)
            if answer is None:
                raise ValueError("missing_route_answer")
            if answer.get("type") == "refusal":
                status = "refusal"
            elif answer.get("type") != "choice" or answer.get("choice") not in {r[0] for r in ROUTES}:
                raise ValueError("invalid_choice")
            else:
                route = answer["choice"]
                raw_confidence = answer.get("confidence")
                if not isinstance(raw_confidence, bool) and isinstance(raw_confidence, (int, float)) and math.isfinite(float(raw_confidence)) and 0 <= float(raw_confidence) <= 1:
                    confidence = round(float(raw_confidence), 3)
            for item in answers:
                if not isinstance(item, dict) or item.get("type") != "predicate":
                    continue
                probability = item.get("probability")
                if isinstance(probability, bool) or not isinstance(probability, (float, int)):
                    continue
                if not math.isfinite(float(probability)) or not 0 <= float(probability) <= 1:
                    continue
                state = self._turns.get(turn)
                if state is None:
                    continue
                if item.get("name") == "explicit_sleep_intent":
                    state.sleep_probability = round(float(probability), 3)
                if item.get("name") == "private_memory_required":
                    state.memory_probability = round(float(probability), 3)
            usage = result.get("usage")
            raw_tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
            if isinstance(raw_tokens, int) and raw_tokens >= 0:
                tokens = raw_tokens
        except asyncio.CancelledError:
            raise
        except httpx.HTTPStatusError as exc:
            # Do not echo response content or user data into error logs.
            status = f"http_{exc.response.status_code}"
        except httpx.TimeoutException:
            status = "timeout"
        except (httpx.RequestError, ValueError, TypeError, KeyError):
            status = "unavailable"
        elapsed = round((time.perf_counter() - started) * 1000)
        state = self._turns.get(turn)
        if self._closed or state is None:
            return
        state.status = status
        state.decisions_route = route
        state.confidence = confidence
        state.latency_ms = elapsed
        state.input_tokens = tokens
        state.decisions_ready_at = time.perf_counter()
        estimate = f"{tokens * INPUT_USD_PER_MILLION / 1_000_000:.8f}" if tokens is not None else "n/a"
        self._log(f"[Jarvis Decisions Shadow] turn={turn} | phase=result | status={status} | "
                  f"route={route or 'n/a'} | confidence={confidence if confidence is not None else 'n/a'} | "
                  f"latency_ms={elapsed} | input_tokens={tokens if tokens is not None else 'n/a'} | "
                  f"estimated_usd={estimate} | sleep_probability={state.sleep_probability if state.sleep_probability is not None else 'n/a'} | "
                  f"memory_probability={state.memory_probability if state.memory_probability is not None else 'n/a'} | authority=none")
        self._report_if_ready(turn, state)
        self._report_timing(turn, state)

    def _report_if_ready(self, turn: int, state: _Turn) -> None:
        if state.reported or state.status == "pending" or state.observed is None:
            return
        match = "yes" if state.decisions_route == state.observed else "no"
        if state.decisions_route is None:
            match = "n/a"
        self._log(f"[Jarvis Decisions Shadow] turn={turn} | phase=compare | "
                  f"mini_route={state.observed} | decisions_route={state.decisions_route or 'n/a'} | "
                  f"agreement={match} | authority=mini")
        state.reported = True

    def _report_timing(self, turn: int, state: _Turn) -> None:
        # A fair speech-end comparison needs a real transcript arrival delay.
        # The current endpoint's fast call time alone proves nothing about E2E.
        if state.timing_reported or state.status == "pending" or state.mini_arrived_at is None:
            return
        if state.transcript_arrived_at is None or state.decisions_ready_at is None:
            return
        ready_after_speech = (state.transcript_delay_ms + state.latency_ms
                              if state.transcript_delay_ms is not None and state.latency_ms is not None
                              else None)
        arrival_order = ("mini_before_transcript" if state.mini_arrived_at < state.transcript_arrived_at
                         else "transcript_before_mini")
        self._log(f"[Jarvis Decisions Timing] turn={turn} | "
                  f"arrival_order={arrival_order} | "
                  f"transcript_delay_ms={state.transcript_delay_ms if state.transcript_delay_ms is not None else 'n/a'} | "
                  f"decisions_api_ms={state.latency_ms if state.latency_ms is not None else 'n/a'} | "
                  f"estimated_speech_end_to_decisions_ready_ms={ready_after_speech if ready_after_speech is not None else 'n/a'} | "
                  f"mini_route_from_speech_ms={state.mini_route_from_speech_ms if state.mini_route_from_speech_ms is not None else 'n/a'} | "
                  f"actual_first_audio_from_speech_ms={state.actual_first_audio_ms if state.actual_first_audio_ms is not None else 'n/a'} | "
                  "decision_authority=mini | counterfactual_first_audio=not_measured")
        state.timing_reported = True
        self._report_voice_timing(turn, state)

    def _report_voice_timing(self, turn: int, state: _Turn) -> None:
        # Electron reports the actual first-audio timing asynchronously and may
        # send it after the API result. Preserve it as a separate observation.
        if state.voice_timing_reported or (state.actual_first_audio_ms is None and state.mini_route_from_speech_ms is None):
            return
        ready_after_speech = (state.transcript_delay_ms + state.latency_ms
                              if state.transcript_delay_ms is not None and state.latency_ms is not None
                              else None)
        self._log(f"[Jarvis Decisions Timing] turn={turn} | phase=voice_e2e | "
                  f"observed_speech_end_to_mini_route_ms={state.mini_route_from_speech_ms if state.mini_route_from_speech_ms is not None else 'n/a'} | "
                  f"observed_speech_end_to_first_audio_ms={state.actual_first_audio_ms if state.actual_first_audio_ms is not None else 'n/a'} | "
                  f"estimated_speech_end_to_decisions_ready_ms={ready_after_speech if ready_after_speech is not None else 'n/a'} | "
                  "decision_authority=mini | hypothetical_decisions_audio=not_measured")
        state.voice_timing_reported = True

    def _trim_old_turns(self) -> None:
        while len(self._turns) > 32:
            self._turns.popitem(last=False)

    async def close(self) -> None:
        self._closed = True
        for task in tuple(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        self._tasks.clear()
        self._turns.clear()
        self._last_user = None
        self._last_reply = None
        if self._own_client:
            await self._client.aclose()
