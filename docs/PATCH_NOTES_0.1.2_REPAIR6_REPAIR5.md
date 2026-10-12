# 0.1.2-repair6-repair5 — Gate-free conversation-only A/B

- **Optional direct-benchmark**: `python scripts/realtime_ab.py mini-fast` / `full-fast` bypasses the silent cloud routing inference. Realtime immediately generates the audible answer to informational conversation.
- **Existing safe path unchanged**: `mini` / `full` retain the silent router, Core/Luna calls, actions, sleep lifecycle, and permission boundary.
- **Crucial safety limitation**: fast mode explicitly disables all tools, including Core delegation and voice sleep; it is **NOT a drop-in replacement for tool-capable Jarvis**. On current WebRTC, audio can play before a later tool-call event. Previous repairs proved model instructions alone cannot prevent pre-tool audio leakage. A tool-capable single-pass design needs a response-specific audio publication boundary, further engineering, and live adversarial tests.
- **Cost/latency**: keeps user/reply transcript, token usage, estimated cost, response timestamps; direct mode `route=direct_no_gate` is clearly labeled in logs.
- **No configuration edits**: A/B launcher injects flags only in its child process; .env and secrets remain untouched. Development terminal transcripts are opt-in in production.
- **V1 lessons**: model can be the conversational brain, but Core/permissions remain trusted and speaker publication needs proof of ownership.
- **Testing**: patch tests and full regression required; Windows live acceptance pending. Do not commit before acceptance.
