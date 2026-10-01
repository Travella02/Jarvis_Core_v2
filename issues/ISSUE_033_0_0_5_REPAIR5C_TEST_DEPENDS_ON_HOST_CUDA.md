# ISSUE 033 — Repair5c loader test depended on host CUDA installation

The Repair5c runtime loader intentionally discovers installed CUDA Toolkit
directories. Its unit test accidentally used the developer machine's real
environment and asserted that only one DLL directory was added.

On machines with CUDA installed, that assertion is wrong even though runtime
behavior is correct.

Repair5d isolates the fallback-loader unit test from host CUDA discovery.
