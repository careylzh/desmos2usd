# Handoff: 2026-04-27 01:08 SGT — Ralph cron loop setup

## Active Task
Run a bounded non-overlapping Ralph loop every 10 minutes for `desmos2usd-carey`, fixing one remaining partial Desmos input at a time.

## Current Branch State
- Repo: `/Users/chek/repos/desmos2usd-carey`
- Branch: `fix/student-fixture-usdz-export`
- Push target: `chektien:fix/student-fixture-usdz-export`
- Current HEAD: `4cb884c Clip explicit surface samples outside domain`
- PR: `https://github.com/careylzh/desmos2usd/pull/1`

## Current Baseline
- Summary: 71 fixtures, 25 success, 46 partial, 0 error.
- S2-06 Group E pass 5: improved to 57 unsupported / 679 prims, still partial; ccwork approved.
- S2-08 Group E: success, 83 prims, 0 unsupported; use as regression guard.
- S2-09 Group F: success, 27 prims, 0 unsupported; use as regression guard.

## Next Recommended Fixture
Start with S2-03 Group D unless live Desmos/viewer evidence suggests a better one-input target:
- fixture: `[4B] 3D Diagram - S2-03 Group D.json`
- Desmos: `https://www.desmos.com/3d/zvasa1wcgo`
- current metrics: 122 unsupported, 204 prims, 271 classified

## Required Wake Behavior
- If an earlier Codex or ccwork run is still active, do not launch another run; post a concise progress update and exit.
- Otherwise, launch one bounded raw HOME Codex tranche.
- The tranche must load the Desmos URL, wait for the model, capture several reference screenshots, then compare against live viewer screenshots/projections while fixing.
- Do not rely on metrics alone.
- Update this handoff after meaningful work.

## Validation Expectations
- targeted regression tests for the fixed family
- relevant fixture regeneration and `summary.json` update
- S2-08E and S2-09F guard checks
- `git diff --check`
- commit/push if coherent and validation passes

## User-Facing Update
Ralph cron loop is being configured for 10-minute non-overlapping wakes, one Desmos input at a time.
