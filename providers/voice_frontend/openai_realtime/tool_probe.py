"""Explicitly opt-in text-only ungated tool *selection* probe. Never executes Luna/actions.

Kept separate from the production bridge so a model tool request cannot mutate anything.
"""
from __future__ import annotations
import json

TOOL_PROBE_INSTRUCTIONS = """You are Jarvis in a TEXT-ONLY developer tool-selection test. No speech is possible.
For simple general questions, answer directly in one concise sentence.
For requests requiring expert coding/architecture/complex analysis, call ask_luna.
For requests requiring an actual external action, including background builds, call test_action.
Do not call either tool for basic arithmetic, common knowledge, or casual conversation.
Never assert an action started or completed. The probe tools are dry-run only.
If a tool returns not_executed, explain that fact accurately, without pretending the task was done.
Do not narrate 'let me think' or announce a tool call before calling it.
"""
BUFFERED_TOOL_INSTRUCTIONS = """You are Jarvis in a developer audio-buffering test.
Answer simple knowledge and conversation requests directly in speech.
For complex architecture, analysis, and coding requests select ask_luna.
For requests to execute an action select test_action. These two tools are DRY RUN and cannot execute work.
Never imply a task was started, completed, or that Luna actually ran.
Avoid unverified pre-tool claims. Follow tool output truthfully.
"""

TOOL_PROBE_TOOLS = [
 {"type":"function", "name":"ask_luna",
  "description":"Select this for requests requiring genuinely deeper expert reasoning, coding, architectural planning or extensive analysis. This developer probe only tests selection, and does NOT execute Luna.",
  "parameters":{"type":"object","properties":{"question":{"type":"string","description":"User's underlying analysis question."}},"required":["question"],"additionalProperties":False}},
 {"type":"function", "name":"test_action",
  "description":"Select this whenever the user requests execution of an external action, including a durable background job. Dry-run, no permissions or executors run.",
  "parameters":{"type":"object","properties":{"request":{"type":"string"},"execution":{"type":"string","enum":["immediate","background"]}},"required":["request","execution"],"additionalProperties":False}},
]
# Only the parallel streaming experiment adds the separate lifecycle tool.
# A sleep request is a local presence transition, NOT an external action and NOT
# a dry-run operation; it is handled exclusively by the Electron lifecycle owner.
OVERLAP_SLEEP_TOOL = {
 "type":"function", "name":"sleep_jarvis",
 "description":"Choose for a clear request to end this conversation or put Jarvis to sleep, including a polite thank-you followed by an explicit closing. Gratitude alone, a quoted closing phrase, a negated sleep request, or an ongoing question is NOT an ending. Never speak before selecting this lifecycle tool.",
 "parameters":{"type":"object","properties":{
     "sleep_evidence":{"type":"string","description":"Quote the user's exact words establishing a clear request to sleep/end the conversation. Do not invent evidence; do not use simple gratitude."}
 },"required":["sleep_evidence"],"additionalProperties":False},
}
OVERLAP_PROBE_TOOLS = [*TOOL_PROBE_TOOLS, OVERLAP_SLEEP_TOOL]
OVERLAP_PROBE_INSTRUCTIONS = """You are Jarvis in a silent parallel authorization experiment.
For a clear request to end the interaction, go to sleep, or sign off, call sleep_jarvis with the user's exact closing words as sleep_evidence. This remains true when gratitude comes BEFORE the dismissal, as in 'Thanks Jarvis, that is all'. Do not produce conversational text or a farewell before or after it.
Gratitude alone (e.g. 'thanks, Jarvis') must NOT put Jarvis to sleep; continue normal conversation. If the user asks another question, handle that question instead of sleeping. A quoted dismissal or a negated sleep request is not an instruction to sleep.
For complex coding/architecture/analysis use ask_luna (dry run). For external actions use test_action (dry run). For simple facts, arithmetic and ordinary conversation, answer directly.
Never claim that Luna or an action ran. No real external tools execute in this experiment.
"""

def overlap_probe_response_policy() -> dict:
    return {"max_output_tokens":512,"instructions":OVERLAP_PROBE_INSTRUCTIONS,
            "output_modalities":["text"],"tools":OVERLAP_PROBE_TOOLS,"tool_choice":"auto",
            "metadata":{"jarvis_stage":"overlap_probe"}}

ALLOWED_PROBE_TOOLS = frozenset({"ask_luna","test_action"})

def dry_run_result(name: str, arguments: object) -> dict:
    """Never execute provider calls, tools, filesystem writes, or other side effects."""
    if name not in ALLOWED_PROBE_TOOLS:
        return {"status":"blocked", "executed":False, "error":"unrecognized_probe_tool"}
    if name == "ask_luna":
        return {"status":"not_executed", "executed":False,
                "message":"Luna was selected in a dry-run benchmark; no Luna request was sent."}
    execution = arguments.get("execution") if isinstance(arguments,dict) else None
    return {"status":"unavailable", "executed":False,
            "execution":execution if execution in ("immediate","background") else "unspecified",
            "message":"This is a simulated action test. No real action was started or queued."}


def probe_response_policy() -> dict:
    return {"max_output_tokens":512,"instructions":TOOL_PROBE_INSTRUCTIONS,
            "output_modalities":["text"],"tools":TOOL_PROBE_TOOLS,"tool_choice":"auto",
            "metadata":{"jarvis_stage":"tool_probe"}}
