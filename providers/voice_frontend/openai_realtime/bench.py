"""Development-only Realtime A/B billing diagnostics.

Estimates OpenAI Realtime charges from response.done usage. No prompt,
transcript or secret is persisted; Core LLM and external-tool charges are NOT
included. Cached tokens are part of input totals, never added twice.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# USD per one million tokens, published 2026-10-09. Check before production use.
PRICES = {
    "gpt-realtime-2.1-mini": {"input_text": .60, "input_audio": 10.0, "input_image": .80,
                               "cached_text": .06, "cached_audio": .30, "cached_image": .08,
                               "output_text": 2.40, "output_audio": 20.0},
    "gpt-realtime-2.1": {"input_text": 4.0, "input_audio": 32.0, "input_image": 5.0,
                          "cached_text": .40, "cached_audio": .40, "cached_image": .50,
                          "output_text": 24.0, "output_audio": 64.0},
}
PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"


def _number(raw: Any) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0:
        return None
    return int(raw)


def _details(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class UsageEstimate:
    cost_usd: float | None
    text_in: int | None = None
    audio_in: int | None = None
    image_in: int | None = None
    cached_in: int | None = None
    text_out: int | None = None
    audio_out: int | None = None
    total_in: int | None = None
    total_out: int | None = None
    note: str = ""


def estimate_realtime_cost(model: str, usage: dict[str, Any] | None) -> UsageEstimate:
    usage = _details(usage)
    inp = _details(usage.get("input_token_details"))
    out = _details(usage.get("output_token_details"))
    cin = _details(inp.get("cached_tokens_details"))
    vals = dict(text_in=_number(inp.get("text_tokens")),
                audio_in=_number(inp.get("audio_tokens")),
                image_in=_number(inp.get("image_tokens")),
                cached_in=_number(inp.get("cached_tokens")),
                text_out=_number(out.get("text_tokens")),
                audio_out=_number(out.get("audio_tokens")),
                total_in=_number(usage.get("input_tokens")),
                total_out=_number(usage.get("output_tokens")))
    if model not in PRICES:
        return UsageEstimate(None, **vals, note="unpriced_model")
    if vals["total_in"] is None or vals["total_out"] is None:
        return UsageEstimate(None, **vals, note="usage_missing")
    # Totals with no modality breakdown are not safe for a dollar estimate.
    if vals["total_in"] and (vals["text_in"] is None or vals["audio_in"] is None):
        return UsageEstimate(None, **vals, note="input_modalities_missing")
    if vals["total_out"] and (vals["text_out"] is None or vals["audio_out"] is None):
        return UsageEstimate(None, **vals, note="output_modalities_missing")
    text_in = vals["text_in"] or 0
    audio_in = vals["audio_in"] or 0
    image_in = vals["image_in"] or 0
    text_out = vals["text_out"] or 0
    audio_out = vals["audio_out"] or 0
    if text_in + audio_in + image_in != vals["total_in"] or text_out + audio_out != vals["total_out"]:
        return UsageEstimate(None, **vals, note="unclassified_tokens")
    cache_all = vals["cached_in"] or 0
    if cache_all:
        cache_parts = [_number(cin.get(name)) for name in ("text_tokens", "audio_tokens", "image_tokens")]
        if any(n is None for n in cache_parts) or sum(cache_parts) != cache_all:
            return UsageEstimate(None, **vals, note="cached_breakdown_missing")
    else:
        cache_parts = [0, 0, 0]
    if any(c > v for c, v in zip(cache_parts, (text_in, audio_in, image_in))):
        return UsageEstimate(None, **vals, note="cache_exceeds_input")
    prices = PRICES[model]
    cost = (
        sum((n-c) * prices["input_"+m] + c * prices["cached_"+m]
            for n, c, m in zip((text_in, audio_in, image_in), cache_parts, ("text", "audio", "image")))
        + text_out * prices["output_text"]
        + audio_out * prices["output_audio"]
    ) / 1_000_000
    return UsageEstimate(cost, **vals, note="estimated")


@dataclass
class TurnBench:
    model: str
    route: str = "unknown"
    user_chars: int | None = None
    user_words: int | None = None
    reply_chars: int | None = None
    reply_words: int | None = None
    first_audio_ms: int | None = None
    core_calls: int = 0
    tool_calls: list[str] = field(default_factory=list)
    realtime_cost: float = 0.0
    priced_responses: int = 0
    unpriced_responses: int = 0


class RealtimeBenchmark:
    def __init__(self, model: str):
        self.model = model
        self.turns: dict[int, TurnBench] = {}
        self.response_ids: set[str] = set()
        self.active_turn = 0
        self.unassigned_cost = 0.0

    def turn(self, turn: int) -> TurnBench:
        if turn not in self.turns:
            self.turns[turn] = TurnBench(self.model)
        return self.turns[turn]

    def on_user(self, turn: int, text: str) -> None:
        if turn <= 0: return
        item = self.turn(turn)
        item.user_chars, item.user_words = len(text), len(text.split())

    def on_route(self, turn: int, route: str) -> None:
        if turn <= 0: return
        self.active_turn = turn
        self.turn(turn).route = route

    def on_latency(self, turn: int, first_audio_ms: Any) -> None:
        if turn <= 0: return
        self.turn(turn).first_audio_ms = _number(first_audio_ms)

    def on_reply(self, turn: int, text: str) -> str:
        item = self.turn(turn)
        item.reply_chars, item.reply_words = len(text), len(text.split())
        return (f"[Jarvis A/B Turn] turn={turn} | model={self.model} | route={item.route} | "
                f"user_chars={item.user_chars if item.user_chars is not None else 'n/a'} | "
                f"user_words={item.user_words if item.user_words is not None else 'n/a'} | "
                f"reply_chars={item.reply_chars} | reply_words={item.reply_words} | "
                f"core_calls={item.core_calls} | first_audio_ms={item.first_audio_ms if item.first_audio_ms is not None else 'n/a'} | "
                f"realtime_est_usd=${item.realtime_cost:.6f} | "
                f"unpriced_responses={item.unpriced_responses} | core_cost=excluded")

    def on_core(self, turn: int, tool_name: str) -> None:
        if turn <= 0: return
        item = self.turn(turn)
        item.core_calls += 1
        item.tool_calls.append(tool_name)

    def on_response(self, response: dict[str, Any], *, turn: int, stage: str) -> str | None:
        rid = str(response.get("id") or "")
        if rid and rid in self.response_ids:
            return None
        if rid: self.response_ids.add(rid)
        usage = _details(response.get("usage"))
        estimate = estimate_realtime_cost(self.model, usage)
        if turn > 0:
            item = self.turn(turn)
            if estimate.cost_usd is None:
                item.unpriced_responses += 1
            else:
                item.realtime_cost += estimate.cost_usd
                item.priced_responses += 1
        elif estimate.cost_usd is not None:
            self.unassigned_cost += estimate.cost_usd
        tools = [str(it.get("name")) for it in response.get("output", [])
                 if isinstance(it, dict) and it.get("type") == "function_call"]
        if turn > 0 and tools:
            self.turn(turn).tool_calls.extend(tools)
        fmt = lambda x: 'n/a' if x is None else str(x)
        dollars = f"${estimate.cost_usd:.6f}" if estimate.cost_usd is not None else f"n/a({estimate.note})"
        return (f"[Jarvis A/B Usage] turn={turn or 'n/a'} | model={self.model} | stage={stage} | "
                f"status={response.get('status', 'unknown')} | "
                f"input_total={fmt(estimate.total_in)} | input_text={fmt(estimate.text_in)} | "
                f"input_audio={fmt(estimate.audio_in)} | cached={fmt(estimate.cached_in)} | "
                f"output_total={fmt(estimate.total_out)} | output_text={fmt(estimate.text_out)} | "
                f"output_audio={fmt(estimate.audio_out)} | function_calls={','.join(tools) or 'none'} | "
                f"estimated_usd={dollars}")

    def summary(self) -> str:
        cost = sum(item.realtime_cost for item in self.turns.values()) + self.unassigned_cost
        return (f"[Jarvis A/B Session] model={self.model} | turns={len(self.turns)} | "
                f"core_calls={sum(i.core_calls for i in self.turns.values())} | "
                f"realtime_est_usd=${cost:.6f} | "
                f"unpriced_responses={sum(i.unpriced_responses for i in self.turns.values())} | "
                f"other_costs=excluded")
