# Handoff: 2026-04-27 11:54 SGT - S2-03E top sphere-cap tranche

## Current Branch State
- Repo: `/Users/chek/repos/desmos2usd-carey`
- Branch: `fix/student-fixture-usdz-export`
- Push target: `chektien:fix/student-fixture-usdz-export`
- HEAD before this tranche: `8137dd2 Handle random Gaussian fixture regions`

## Completed This Tranche
- Targeted fixture: `[4B] 3D Diagram - S2-03 Group E.json`
- Desmos URL: `https://www.desmos.com/3d/sqkhp7wnx6`
- Implemented one general exporter fix:
  - axis-aligned implicit ellipsoid surfaces now clip generated mesh faces against expression predicates instead of rejecting the entire ellipsoid when any generated vertex is outside the restriction
  - this handles equality sphere caps such as `sphere residual = radius^2 {z >= center_z}` without falling through to the 3-axis marching fallback that requires a constant-bounded axis
- No fixture-specific expression ids, fixture names, or one-off constants were added.
- Added student-fixture regression coverage for an axis-restricted implicit sphere surface cap.
- Regenerated tracked artifacts for S2-03E and rebuilt the 71-fixture `artifacts/fixture_usdz/summary.json` from reports.
- S2-08E and S2-09F were regenerated for guard validation during the tranche; their tracked artifact churn was restored because the guard outputs remained semantically unchanged.

## Evidence
- Evidence directory: `artifacts/fixture_usdz/review_evidence/20260427_s203_group_e_ralph_top_sphere_caps/`
- Files:
  - `S2-03_Group_E_projection_before.png`
  - `S2-03_Group_E_projection_before.ppm`
  - `S2-03_Group_E_projection_before.usda`
  - `S2-03_Group_E_projection_after.png`
  - `S2-03_Group_E_projection_after.ppm`
  - `S2-03_Group_E_projection_after.usda`
  - `S2-03_Group_E_report_before.json`
  - `S2-03_Group_E_report_after.json`
  - `S2-08_Group_E_projection_guard_after.png`
  - `S2-08_Group_E_projection_guard_after.ppm`
  - `S2-08_Group_E_projection_guard_after.usda`
  - `S2-09_Group_F_projection_guard_after.png`
  - `S2-09_Group_F_projection_guard_after.ppm`
  - `S2-09_Group_F_projection_guard_after.usda`
  - `before_metrics.json`
  - `after_metrics.json`
  - `capture_results.json`
  - `projection_results.json`
  - `assessment.md`
- Browser/live viewer blockers:
  - Playwright Desmos setup/navigation returned `user cancelled MCP tool call`.
  - Chrome DevTools Desmos navigation returned `user cancelled MCP tool call`.
  - Playwright viewer navigation returned `user cancelled MCP tool call`.
  - Chrome DevTools viewer navigation returned `user cancelled MCP tool call`.
  - Tailnet route checks for root, viewer, and summary failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Visual claim: no live Desmos/viewer parity claim. This tranche has deterministic local projection evidence only.

## Metrics
- Overall fixture summary: 71 fixtures, 29 success, 42 partial, 0 error, 71 USDZ, acceptance still not met.
- S2-03 Group E before: `460 prims / 4 unsupported / 464 classified / 464 renderable / valid true / usdchecker returncode 0`.
- S2-03 Group E after: `464 prims / 0 unsupported / 464 classified / 464 renderable / valid true / usdchecker returncode 0`.
- Added/removed unsupported expression ids: `363_0`, `363_1`, `363_2`, `363_3`; each now validates as `64 faces / 65 points`.
- S2-08 Group E guard remains success: `87 prims / 0 unsupported / valid true / usdchecker returncode 0`.
- S2-09 Group F guard remains success: `27 prims / 0 unsupported / valid true / usdchecker returncode 0`.

## Validation
- Focused regression passed: `PYTHONPATH=src:tests python3 -m unittest tests.test_student_fixture_regressions.StudentFixtureRegressionTests.test_axis_restricted_implicit_sphere_exports_surface_cap`.
- Targeted modules passed: `PYTHONPATH=src:tests python3 -m unittest tests.test_student_fixture_regressions tests.test_fixture_usdz_suite tests.test_visual_preview` ran 67 tests OK.
- Full unittest discovery passed: `PYTHONPATH=src:tests python3 -m unittest discover -s tests` ran 137 tests in 130.755s OK.
- Report-vs-USDA consistency checked:
  - S2-03E report prim_count `464`, USDA `Mesh` + `BasisCurves` defs `464`, unsupported `0`
  - S2-08E report prim_count `87`, USDA defs `87`, unsupported `0`
  - S2-09F report prim_count `27`, USDA defs `27`, unsupported `0`
- PNG projection dimensions checked with `sips`: all four PNGs are `1552x512`.
- `git diff --check`: passed.

## Commit / Push
- Blocked in this HOME Codex environment.
- Exact blocker: `git add -A && git add -f artifacts/fixture_usdz/review_evidence/20260427_s203_group_e_ralph_top_sphere_caps/ && git commit --author='chektien <www@ch3k.com>' -m 'Handle predicate-clipped sphere caps'` failed with `fatal: Unable to create '/Users/chek/repos/desmos2usd-carey/.git/index.lock': Operation not permitted`.
- Worktree is ready for the orchestrator/next wake to stage, commit, and push.
- Expected commit message: `Handle predicate-clipped sphere caps`.
- Include forced-add evidence if needed because `artifacts/*` may be ignored by default:
  - `git add -f artifacts/fixture_usdz/review_evidence/20260427_s203_group_e_ralph_top_sphere_caps/`

## Remaining Mismatch / Next Wake Instructions
1. Do not claim visual parity until live Desmos reference screenshots and live viewer screenshots can be captured.
2. Next exact implementation target: S2-07 Group F remaining sampled inequality. Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`; current metrics: `887 prims / 888 classified / 1 unsupported`.
3. S2-03 Group E is now structurally success and should only be revisited for live visual parity evidence when browser capture is available.
4. Preserve S2-08 Group E and S2-09 Group F as regression guards.
