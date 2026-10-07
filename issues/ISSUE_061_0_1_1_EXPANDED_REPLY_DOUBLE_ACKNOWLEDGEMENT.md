# ISSUE 061 — Expanded Reply Double Acknowledgement

## Symptom

A deliberately detailed request could sound like two assistant turns joined together: Realtime first said a waiting acknowledgement (for example, “Sure, let me think about this for a second”), invoked the expansion tool, then began the actual detailed answer with another acknowledgement such as “Absolutely”.

## Cause

The desktop used a second function-call round trip only to switch response budgets. Although the prompt asked the model to make that tool call as the initial/only output, Realtime instructions are not a hard guarantee and the model could emit audio before the tool call.

## Repair

The desktop manual-response path no longer exposes the expansion tool. It receives enough safety headroom up front and uses response-specific instructions to choose concise versus deliberately detailed spoken shape in one response. Legacy/A-B labs keep the optional expansion tool for compatibility.

## Lesson

Do not add a second model response solely to select presentation length when one sufficiently bounded response can carry the complete answer. Extra conversational hops create visible/audible seams even when the underlying model is fast.
