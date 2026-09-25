# whisper.cpp provider

0.0.4's first STT candidate is local `whisper.cpp` with `large-v3-turbo-q5_0`.
The adapter talks only to a loopback `whisper-server` process so the model stays
loaded across turns. Core does not know the executable, model path, HTTP shape,
or model name.

The lab produces partials by bounded rolling re-inference while speech arrives,
then performs one final inference on the endpointed utterance. This is adequate
to measure quality/latency without making the transport permanent. A future
native binding can replace the adapter behind the same contract.
