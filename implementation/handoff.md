# Handoff: 2026-04-27 12:22 SGT - S2-07F final chained disk inequality

## Current Branch State
- Repo: `/Users/chek/repos/desmos2usd-carey`
- Branch: `fix/student-fixture-usdz-export`
- Push target: `chektien:fix/student-fixture-usdz-export`
- HEAD before this tranche: `a035b71 Handle predicate-clipped sphere caps`

## Completed This Tranche
- Targeted fixture: `[4B] 3D Diagram - S2-07 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`
- Implemented one general exporter fix:
  - inequality regions can now tessellate chained quadratic disk extrusions such as `(x-u)^2+(y-v)^2 <= r^2 <= z <= h`, intersected with ordinary constant axis restrictions
  - this handles tiny disk/cylinder regions that coarse sampled cells miss
- No fixture-specific expression ids, fixture names, or one-off constants were added.
- Added student-fixture regression coverage for the chained quadratic disk inequality.
- Regenerated tracked S2-07F artifacts and rebuilt the 71-fixture `artifacts/fixture_usdz/summary.json` from reports.
- S2-08E and S2-09F were regenerated as guards during validation and remain success.

## Evidence
- Evidence directory: `artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_final_inequality/`
- Files:
  - `S2-07_Group_F_projection_before.png`
  - `S2-07_Group_F_projection_before.ppm`
  - `S2-07_Group_F_projection_before.usda`
  - `S2-07_Group_F_projection_after.png`
  - `S2-07_Group_F_projection_after.ppm`
  - `S2-07_Group_F_projection_after.usda`
  - `S2-07_Group_F_report_before.json`
  - `S2-07_Group_F_report_after.json`
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
  - Playwright Desmos navigation returned `user cancelled MCP tool call`.
  - Chrome DevTools Desmos navigation returned `user cancelled MCP tool call`.
  - Tailnet route checks for root, viewer, and summary failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Visual claim: no live Desmos/viewer parity claim. This tranche has deterministic local projection evidence only.

## Metrics
- Overall fixture summary: 71 fixtures, 30 success, 41 partial, 0 error, 71 USDZ, acceptance still not met.
- S2-07 Group F before: `887 prims / 1 unsupported / 888 classified / valid true / usdchecker returncode 0`.
- S2-07 Group F after: `888 prims / 0 unsupported / 888 classified / valid true / usdchecker returncode 0`.
- Added prim: `325`, validated as `96 faces / 66 points`.
- S2-08 Group E guard remains success: `87 prims / 0 unsupported / valid true / usdchecker returncode 0`.
- S2-09 Group F guard remains success: `27 prims / 0 unsupported / valid true / usdchecker returncode 0`.

## Validation
- Focused regression passed: `PYTHONPATH=src:tests python3 -m unittest tests.test_student_fixture_regressions.StudentFixtureRegressionTests.test_chained_quadratic_disk_inequality_extrudes_as_cylinder`.
- Targeted modules passed: `PYTHONPATH=src:tests python3 -m unittest tests.test_student_fixture_regressions tests.test_fixture_usdz_suite tests.test_visual_preview` ran 68 tests OK.
- Full unittest discovery passed: `PYTHONPATH=src:tests python3 -m unittest discover -s tests` ran 138 tests in 130.321s OK.
- Temporary S2-07F export check passed: `888 prims / 0 unsupported / valid true`.
- Regenerated artifacts for S2-07F, S2-08E, and S2-09F with `usdchecker --arkit` return code `0`.
- Report-vs-USDA consistency checked:
  - S2-07F report prim_count `888`, USDA `Mesh` + `BasisCurves` defs `888`, unsupported `0`, expr `325` present
  - S2-08E report prim_count `87`, USDA defs `87`, unsupported `0`
  - S2-09F report prim_count `27`, USDA defs `27`, unsupported `0`
- PNG projection dimensions checked with `sips`: all four PNGs are `1552x512`.
- `git diff --check`: passed.

## Commit / Push
- Blocked in this HOME Codex environment.
- Final commit attempt blocker: `git add -A && git add -f artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_final_inequality/ && git commit --author='chektien <www@ch3k.com>' -m 'Handle chained quadratic disk inequalities' && git push chektien fix/student-fixture-usdz-export` failed with `fatal: Unable to create '/Users/chek/repos/desmos2usd-carey/.git/index.lock': Operation not permitted`.
- Earlier guard-artifact restore also hit the same `.git/index.lock` blocker, so S2-08E/S2-09F regenerated guard report/USDZ churn remains in the worktree even though both guards are still success.
- Expected commit message: `Handle chained quadratic disk inequalities`.
- Include forced-add evidence if needed because `artifacts/*` may be ignored by default:
  - `git add -f artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_final_inequality/`

## Review Links
- S2-07 Group F Desmos: `https://www.desmos.com/3d/jkj1z8t8pf`
- S2-07 Group F viewer: `https://chq.singapura-broadnose.ts.net/viewer/?usda=..%2Fartifacts%2Ffixture_usdz%2F%5B4B%5D%203D%20Diagram%20-%20S2-07%20Group%20F.usda&label=S2-07%20Group%20F`
- S2-08 Group E Desmos: `https://www.desmos.com/3d/g59jqe6nxy`
- S2-08 Group E viewer: `https://chq.singapura-broadnose.ts.net/viewer/?usda=..%2Fartifacts%2Ffixture_usdz%2F%5B4B%5D%203D%20Diagram%20-%20S2-08%20Group%20E.usda&label=S2-08%20Group%20E`
- S2-09 Group F Desmos: `https://www.desmos.com/3d/umjxv6ahck`
- S2-09 Group F viewer: `https://chq.singapura-broadnose.ts.net/viewer/?usda=..%2Fartifacts%2Ffixture_usdz%2F%5B4B%5D%203D%20Diagram%20-%20S2-09%20Group%20F.usda&label=S2-09%20Group%20F`
- Route verification from this environment failed for root/viewer/summary with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.

## Remaining Mismatch / Next Wake Instructions
1. Do not start a new implementation tranche until this S2-07F work is staged, committed, and pushed from an environment that can write `.git`.
2. Do not claim visual parity until live Desmos reference screenshots and live viewer screenshots can be captured.
3. After committing, next highest-impact partial by current summary is S2-01 Group A. Desmos URL: `https://www.desmos.com/3d/cvggvbbe73`; current metrics: `162 prims / 46 unsupported`.
4. If Chek wants the visual-only path first and browser capture works, revisit S2-03 Group D live visual parity evidence. Desmos URL: `https://www.desmos.com/3d/zvasa1wcgo`; current metrics: `585 prims / 0 unsupported`.
5. Preserve S2-08 Group E and S2-09 Group F as regression guards.
