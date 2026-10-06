# ISSUE 046 — Realtime WebRTC SDP sent as file part instead of form field

## Symptom
`POST /v1/realtime/calls` returned HTTP 400 with:

`Invalid multipart form, field "sdp" is required but not found`

## Root cause
Repair4 used an httpx multipart tuple with filename `offer.sdp`. That serialized the SDP as a file-upload part. OpenAI's Realtime unified WebRTC endpoint expects the `sdp` value as an ordinary multipart text field.

## Resolution
Repair5 removes filenames from both `sdp` and `session` multipart parts and adds regression tests that assert neither part contains `filename=`.
