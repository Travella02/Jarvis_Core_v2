"""Run A/B sessions with process-local model selection (never edits .env).

Usage: python scripts/realtime_ab.py mini   or   python scripts/realtime_ab.py full
Stop desktop completely between runs. This launches `npm run desktop` once.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

MODELS = {"mini": ("gpt-realtime-2.1-mini", False),
          "full": ("gpt-realtime-2.1", False),
          "mini-fast": ("gpt-realtime-2.1-mini", True),
          "full-fast": ("gpt-realtime-2.1", True),
          "mini-tools": ("gpt-realtime-2.1-mini", False),
          "full-tools": ("gpt-realtime-2.1", False),
          "mini-buffered": ("gpt-realtime-2.1-mini", False),
          "mini-overlap": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-decisions-shadow": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-trim": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-trim-guided": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-trim-guided-actions": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-trim-guided-semantic": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-trim-guided-managed-browser": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-trim-guided-browser-media": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-trim-cancel-test": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-decisions-shadow": ("gpt-realtime-2.1-mini", False),
          "mini-overlap-luna-cancel-test": ("gpt-realtime-2.1-mini", False)}

def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in MODELS:
        print("Usage: python scripts/realtime_ab.py mini|full|mini-fast|full-fast|mini-tools|full-tools|mini-buffered|mini-overlap|mini-overlap-decisions-shadow|mini-overlap-luna|mini-overlap-luna-trim|mini-overlap-luna-trim-guided|mini-overlap-luna-trim-guided-actions|mini-overlap-luna-trim-guided-semantic|mini-overlap-luna-trim-guided-managed-browser|mini-overlap-luna-trim-cancel-test|mini-overlap-luna-decisions-shadow|mini-overlap-luna-cancel-test", file=sys.stderr)
        return 2
    model, direct_only = MODELS[sys.argv[1]]
    env = os.environ.copy()
    tool_probe = sys.argv[1].endswith("-tools")
    env["JARVIS_REALTIME_MODEL"] = model
    env["JARVIS_REALTIME_TOOL_SELECTION_PROBE"] = "1" if tool_probe else "0"
    buffered_probe = sys.argv[1] == "mini-buffered"
    env["JARVIS_REALTIME_BUFFERED_TOOL_PROBE"] = "1" if buffered_probe else "0"
    overlap_probe = sys.argv[1] in {"mini-overlap", "mini-overlap-decisions-shadow", "mini-overlap-luna", "mini-overlap-luna-trim", "mini-overlap-luna-trim-guided", "mini-overlap-luna-trim-guided-actions", "mini-overlap-luna-trim-guided-semantic", "mini-overlap-luna-trim-guided-managed-browser", "mini-overlap-luna-trim-guided-browser-media", "mini-overlap-luna-trim-cancel-test", "mini-overlap-luna-decisions-shadow", "mini-overlap-luna-cancel-test"}
    decisions_shadow = sys.argv[1] in {"mini-overlap-decisions-shadow", "mini-overlap-luna-decisions-shadow"}
    env["JARVIS_DECISIONS_SHADOW_PROBE"] = "1" if decisions_shadow else "0"
    pcm_trim = sys.argv[1] in {"mini-overlap-luna-trim", "mini-overlap-luna-trim-guided", "mini-overlap-luna-trim-guided-actions", "mini-overlap-luna-trim-guided-semantic", "mini-overlap-luna-trim-guided-managed-browser", "mini-overlap-luna-trim-guided-browser-media", "mini-overlap-luna-trim-cancel-test"}
    env["JARVIS_PCM_TRIM_LEADING_SILENCE"] = "1" if pcm_trim else "0"
    luna_cancel_test = sys.argv[1] in {"mini-overlap-luna-cancel-test", "mini-overlap-luna-trim-cancel-test"}
    luna_probe = sys.argv[1] == "mini-overlap-luna"
    luna_probe = luna_probe or sys.argv[1] in {"mini-overlap-luna-trim", "mini-overlap-luna-trim-guided", "mini-overlap-luna-trim-guided-actions", "mini-overlap-luna-trim-guided-semantic", "mini-overlap-luna-trim-guided-managed-browser", "mini-overlap-luna-trim-guided-browser-media"}
    luna_probe = luna_probe or sys.argv[1] == "mini-overlap-luna-decisions-shadow"
    luna_probe = luna_probe or luna_cancel_test
    env["JARVIS_CORE_LUNA_PROBE"] = "1" if luna_probe else "0"
    env["JARVIS_LUNA_RESULT_HOLD_SECONDS"] = "8" if luna_cancel_test else "0"
    env["JARVIS_0141_DELEGATION_GUIDANCE"] = "1" if sys.argv[1] in {"mini-overlap-luna-trim-guided", "mini-overlap-luna-trim-guided-actions", "mini-overlap-luna-trim-guided-semantic", "mini-overlap-luna-trim-guided-managed-browser", "mini-overlap-luna-trim-guided-browser-media"} else "0"
    env["JARVIS_CORE_ACTIONS_PROBE"] = "1" if sys.argv[1] in {"mini-overlap-luna-trim-guided-actions", "mini-overlap-luna-trim-guided-semantic", "mini-overlap-luna-trim-guided-managed-browser", "mini-overlap-luna-trim-guided-browser-media"} else "0"
    env["JARVIS_SEMANTIC_ACTIONS_PROBE"] = "1" if sys.argv[1] in {"mini-overlap-luna-trim-guided-semantic", "mini-overlap-luna-trim-guided-managed-browser", "mini-overlap-luna-trim-guided-browser-media"} else "0"
    env["JARVIS_MANAGED_BROWSER_PROBE"] = "1" if sys.argv[1] in {"mini-overlap-luna-trim-guided-managed-browser", "mini-overlap-luna-trim-guided-browser-media"} else "0"
    env["JARVIS_BROWSER_MEDIA_PROBE"] = "1" if sys.argv[1] == "mini-overlap-luna-trim-guided-browser-media" else "0"
    env["JARVIS_PHONETIC_WAKE"] = env["JARVIS_BROWSER_MEDIA_PROBE"]
    env["JARVIS_SILENT_TEST_CUES"] = "1"  # A/B tests are silent unless expressly requested otherwise.
    # Matched Core/Luna setting in both Repair12 arms; only the shadow API differs.
    env["JARVIS_REALTIME_OVERLAP_PROBE"] = "1" if overlap_probe else "0"
    env["JARVIS_PARALLEL_SHADOW_PROBE"] = "0"  # isolate models, avoid doubled costs
    env["JARVIS_REALTIME_DIRECT_ONLY_BENCHMARK"] = "1" if direct_only else "0"
    env["JARVIS_DESKTOP_CONVERSATION_TRACE"] = "1"
    print(f"[Jarvis A/B Launch] model={model} | "
          f"mode={('PARALLEL STREAM + REAL CORE LUNA (APPROVED-SITE ACTIONS OPT-IN)' if env['JARVIS_CORE_ACTIONS_PROBE']=='1' else 'PARALLEL STREAM + REAL CORE LUNA (ACTIONS DRY RUN)') if luna_probe else ('PARALLEL STREAM AUTHORIZATION - DRY RUN TOOLS' if overlap_probe else ('BUFFERED AUDIO - DRY RUN TOOLS' if buffered_probe else ('TEXT ONLY - TOOLS DRY RUN' if tool_probe else ('FAST DIRECT ONLY - NO TOOLS' if direct_only else 'SAFE ROUTED'))))} | "
          f"decisions_shadow={'on' if decisions_shadow else 'off'} | core_luna={'on' if luna_probe else 'off'} "
          f"| pcm_trim={'on' if pcm_trim else 'off'}"
          f" | delegation_guidance={'on' if env['JARVIS_0141_DELEGATION_GUIDANCE']=='1' else 'off'}"
          f" | real_browser_actions={'on' if env['JARVIS_CORE_ACTIONS_PROBE']=='1' else 'off'}"
          f" | semantic_actions={'on' if env['JARVIS_SEMANTIC_ACTIONS_PROBE']=='1' else 'off'}"
          f" | managed_browser={'on' if env['JARVIS_MANAGED_BROWSER_PROBE']=='1' else 'off'}"
          f" | media_controls={'on' if env['JARVIS_BROWSER_MEDIA_PROBE']=='1' else 'off'}"
          f" | phonetic_wake={'on' if env['JARVIS_PHONETIC_WAKE']=='1' else 'off'}"
          f" | cancellation_test={'on' if luna_cancel_test else 'off'} | dev_transcripts=on", flush=True)
    root = Path(__file__).resolve().parents[1]
    try:
        return subprocess.call(["npm", "run", "desktop"], cwd=root, env=env, shell=(os.name == "nt"))
    except FileNotFoundError:
        print("npm not found in PATH", file=sys.stderr)
        return 127

if __name__ == "__main__":
    raise SystemExit(main())
