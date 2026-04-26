# Handoff: 2026-04-27 05:47 SGT - S2-07F point-list triangle tranche

## Current Branch State
- Repo: `/Users/chek/repos/desmos2usd-carey`
- Branch: `fix/student-fixture-usdz-export`
- Push target: `chektien:fix/student-fixture-usdz-export`
- Previous HEAD before this tranche: `f63f5f2 Improve S2-03E affine band export`

## Completed This Tranche
- Targeted fixture: `[4B] 3D Diagram - S2-07 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`
- Implemented one general classifier/export fix:
  - point-list definitions are retained in `EvalContext`
  - point-list indices such as `A[3]` resolve to vector literals
  - list-broadcast indices such as `A[B.x]` resolve after `B.x` expands per row
  - unbracketed comma-separated point lists such as `G_{1}=(...),(...),...` can be indexed
- No fixture-specific expression ids, fixture names, or one-off hacks were added.
- Added regression coverage for point-list triangle indexing in `tests/test_student_fixture_regressions.py`.
- Regenerated tracked artifacts for S2-07F plus S2-08E/S2-09F guards and rebuilt the 71-fixture `artifacts/fixture_usdz/summary.json` from reports.

## Evidence
- Evidence directory: `artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_triangles/`
- Files:
  - `S2-07_Group_F_projection_after.png`
  - `S2-07_Group_F_projection_after.ppm`
  - `S2-07_Group_F_projection_after.usda`
  - `S2-08_Group_E_projection_guard_after.png`
  - `S2-08_Group_E_projection_guard_after.ppm`
  - `S2-08_Group_E_projection_guard_after.usda`
  - `S2-09_Group_F_projection_guard_after.png`
  - `S2-09_Group_F_projection_guard_after.ppm`
  - `S2-09_Group_F_projection_guard_after.usda`
  - `projection_results.json`
  - `capture_results.json`
  - `assessment.md`
- Browser/live viewer blockers:
  - Playwright resize returned `user cancelled MCP tool call`.
  - Chrome DevTools resize and Desmos navigation returned `user cancelled MCP tool call`.
  - Local Chrome headless Desmos screenshot exited `-1`, emitted no stdout/stderr, and created no screenshot.
  - Local viewer server bind failed with `PermissionError: [Errno 1] Operation not permitted`.
- Visual claim: no live Desmos/viewer parity claim. This tranche has deterministic local projection evidence only.

## Metrics
- Overall fixture summary remains 71 fixtures, 26 success, 45 partial, 0 error, 71 USDZ, acceptance still not met.
- S2-07 Group F before: `36 prims / 69 unsupported / 37 classified`.
- S2-07 Group F after: `835 prims / 53 unsupported / 875 classified / valid true / usdchecker returncode 0`.
- S2-07 Group F triangle exports after: `799` triangle mesh prims.
- S2-08 Group E guard remains success: `87 prims / 0 unsupported / valid true / usdchecker returncode 0`.
- S2-09 Group F guard remains success: `27 prims / 0 unsupported / valid true / usdchecker returncode 0`.

## Validation
- Focused point-list regression tests passed.
- Full `tests.test_student_fixture_regressions`: `Ran 48 tests in 0.595s OK`.
- Visual/fixture suite unit tests: `tests.test_visual_preview tests.test_fixture_usdz_suite` ran `5` tests OK.
- Full unittest discovery with `python3 -m unittest discover -s tests`: `Ran 122 tests in 209.550s OK`.
- Report-vs-USDA consistency:
  - S2-07F report prim_count `835`, USDA `Mesh` + `BasisCurves` defs `835`, unsupported `53`
  - S2-08E report prim_count `87`, USDA defs `87`, unsupported `0`
  - S2-09F report prim_count `27`, USDA defs `27`, unsupported `0`
- `git diff --check`: passed.

## Commit / Push
- Commit/push blocked before staging.
- Exact blocker: `git add -u` failed with `fatal: Unable to create '/Users/chek/repos/desmos2usd-carey/.git/index.lock': Operation not permitted`.
- Worktree is ready for the main environment to stage tracked changes, force-add the ignored evidence directory, commit, and push to `chektien:fix/student-fixture-usdz-export`.
- Required staging commands:
  - `git add -u`
  - `git add -f artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_triangles/`

## Remaining Mismatch / Next Wake Instructions
1. Do not claim visual parity until live Desmos reference screenshots and live viewer screenshots can be captured.
2. Next highest-impact partial from current STATE is S2-06 Group E (`https://www.desmos.com/3d/cg2sd6h1ws`) with 57 unsupported.
3. If continuing S2-07 Group F, the next general target families are:
   - affine parser misses for implicit multiplication decimals such as `2z=.515x+1.91` and `.5x+3.76`
   - chained z-band inequalities currently failing as `Only direct function calls are supported`
   - small 3-axis implicit sphere-like details (`238`-`281`, `310`)
   - inequality region `325`
4. Preserve S2-08 Group E and S2-09 Group F as regression guards.
