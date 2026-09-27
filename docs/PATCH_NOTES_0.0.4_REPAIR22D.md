# 0.0.4 Repair22d — candidate attention fallback

Repair22d fixes the Windows line-ending guard problem in Repair22c and restores the isolated streaming candidate worker from the canonical Repair22 payload. The only model-loader change is replacing `attn_implementation="flash_attention_2"` with `attn_implementation="sdpa"`.

The installer recognizes both LF and CRLF forms of the Repair22 original worker and the malformed Repair22a worker, backs up the current candidate worker, compiles the replacement before and after installation, and verifies the installed SHA-256. The accepted Repair20 provider/runtime remains untouched.
