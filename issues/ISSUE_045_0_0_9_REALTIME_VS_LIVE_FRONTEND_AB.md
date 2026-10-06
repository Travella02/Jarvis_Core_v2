# ISSUE 045 - 0.0.9 Realtime vs GPT-Live frontend A/B

## Problem
GPT-Live + Luna preserved Jarvis Core authority and sounded clean over browser WebRTC, but its strict delegation architecture can add artificial waiting acknowledgements for simple questions that a native speech-to-speech model could answer immediately. The user also preferred the conversational feel of OpenAI Realtime from V1.

## V1 lesson reused
V1 explicitly recommended OpenAI Realtime over WebRTC as the primary conversational brain, while local Jarvis Core retained identity, memory, permissions, tools, durable work, and provider routing. It also required stronger/background workers for research and deep work instead of giving Realtime unrestricted authority.

## 0.0.9 Repair4 decision
Add OpenAI Realtime as a second swappable full-duplex WebRTC frontend for direct A/B testing. Realtime may answer ordinary conversation itself. It receives exactly one narrow application function, `delegate_to_jarvis_core`, for durable/private memory, current state, actions, permissions, background work, or stronger/deeper reasoning.

The function executes in Jarvis Core. Realtime never receives unrestricted shell, desktop, memory database, or permission authority. When Core returns the result, it is sent back as `function_call_output`, then Realtime speaks the verified result naturally.

## Long-running work
For future durable jobs, Core can return a job handle immediately while a worker continues after the voice session closes. Realtime/GPT-Live are conversation surfaces, not the durable task runner.

## Transport lifecycle
Browser WebRTC remains the preferred client-device media path. Repair4 also closes the browser peer if its localhost Jarvis Core control channel disappears, preventing a direct cloud media session from outliving the trusted local authority.
