# 0.0.9 Repair4 Testing Guide - GPT-Live vs Realtime A/B

## 1. Focused automated tests
Run the Repair4 focused command supplied with the patch. All tests must pass.

## 2. Full regression
Run `python -m unittest discover -s tests -v` and require `OK` with only previously accepted skips.

## 3. Diagnostics
Run `python -m core.diagnostics`. `Frontend A/B` must include `openai-gpt-realtime` and final `Status: ok`.

## 4. Realtime 2.1 flagship A/B
Run:

`python -m apps.gpt_realtime_webrtc_lab --turns 5 --voice cedar --realtime-model gpt-realtime-2.1 --reasoning-effort low`

In the browser select the same HyperX mic/headphones used for GPT-Live, then say exactly:

1. `Jarvis, tell me something interesting about space.`
2. `Why does that happen?`
3. `Explain it more simply.`
4. While Jarvis is still speaking #3: `Tell me another interesting fact.`
5. `Tell me a short joke.`

Judge naturalness, first-response feel, interruption quality, artifacts/pops, unnecessary waiting acknowledgements, and whether simple questions are answered directly.

## 5. Realtime 2.1 Mini cost A/B
Run the same test with:

`python -m apps.gpt_realtime_webrtc_lab --turns 5 --voice cedar --realtime-model gpt-realtime-2.1-mini --reasoning-effort low --port 8767`

Compare voice quality and naturalness against full 2.1.

## 6. Optional Core-delegation probe
After the five comparison phrases, in a fresh session ask something that clearly requires Core, for example:

`Jarvis, use Jarvis Core to think carefully about the architecture tradeoff between GPT-Live and Realtime for our project.`

Expected: Realtime emits `delegate_to_jarvis_core`, the terminal prints `[Realtime delegated to Jarvis Core: ...]`, Core/Luna completes the backend call, and Realtime naturally communicates the returned result. It must not claim the backend result before Core returns it.

## 7. Lifecycle check
While a Realtime browser session is connected, stop the terminal with Ctrl+C. The browser should close the peer automatically when the localhost control channel disappears. Starting/stopping the terminal must not leave an orphaned direct Realtime session.
