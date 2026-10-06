# ISSUE 051 — Desktop orb state transitions hard-cut / over-bounce

## Status
Resolved by 0.1.0 Repair3.

## Symptom
The Repair2 dust orb improved Jarvis's visual identity, but changing between listening, thinking, speaking, and idle could look like a visual cut. Speaking also used enough scale modulation to read as a visible bounce instead of subtle energy.

## Root cause
State-specific values were selected directly from the current state on each animation frame, while CSS state filters also switched immediately. The particle field itself persisted, but motion speed, scale, brightness, and tint targets were not interpolated.

## Resolution
Repair3 keeps one particle field and continuously eases its state parameters toward the next state's targets. Color, motion speed, scale, turbulence, radial movement, core energy, and opacity now blend over time. CSS no longer performs abrupt state-specific color/filter swaps. Speaking scale modulation was reduced to less than 0.4%.

## Regression protection
`tests.unit.test_0_1_0_repair3_orb_state_transitions` verifies persistent-field interpolation, unique state targets, reduced speaking bounce, and the absence of CSS hard-swap filters.
