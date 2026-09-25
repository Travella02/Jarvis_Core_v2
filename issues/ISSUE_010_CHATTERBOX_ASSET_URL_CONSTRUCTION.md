# ISSUE_010 - Chatterbox Asset URL Construction

## Status
Addressed by 0.0.4-repair5; pending live acceptance.

## Problem
During repair4 live setup, the Chatterbox model files were confirmed to exist upstream, but the PowerShell downloader repeatedly ended in HTTP 404. The URL expression used `"$ModelBaseUrl/$Name?download=true"`. In an expandable PowerShell string, punctuation directly following a variable can produce ambiguous variable-token parsing and an incorrect request target.

## Resolution
- Pin Chatterbox Turbo asset delivery to upstream revision `1e4698ca7cbb41ff030c4185f0927a3b42d76924`.
- Escape each filename explicitly.
- Build the resolve URL with PowerShell's `-f` format operator instead of adjacent interpolated variables/query text.
- Remove the unnecessary `?download=true` query entirely.
- Retain curl retry/resume, BITS fallback, SHA-256 checks, and atomic installation from repair4.

## Long-term rule
Provider asset URLs must be built by an explicit URL-construction helper/pattern and covered by a regression test. Do not rely on ambiguous adjacent PowerShell interpolation for remote asset paths.
