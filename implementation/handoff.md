# Handoff: 2026-04-27 12:49 SGT - S2-02F one-axis quadratic guide bands

## Current Branch State
- Repo: `/Users/chek/repos/desmos2usd-carey`
- Branch: `fix/student-fixture-usdz-export`
- Push target: `chektien:fix/student-fixture-usdz-export`
- HEAD before this tranche: `0a683e5 Prioritize today's presentation fixtures`

## Completed This Tranche
- Targeted fixture: `[4B] 3D Diagram - S2-02 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/1zpiejy9c9`
- Implemented one general exporter fix:
  - inequality regions whose main predicate is a single-axis quadratic interval, e.g. `(z-c)^2 <= r^2`, are solved analytically into a bounded slab and routed through the existing band tessellator
  - this handles list-expanded guide/floor bands without relying on coarse sampled cells hitting a very thin interval
- No fixture-specific expression ids, fixture names, or one-off constants were added.
- Added regression coverage for the S2-02F-style one-axis quadratic band.
- Regenerated tracked S2-02F artifacts, S2-08E and S2-09F guard artifacts, and rebuilt `artifacts/fixture_usdz/summary.json` from reports.

## Evidence
- Evidence directory: `artifacts/fixture_usdz/review_evidence/20260427_s202_group_f_ralph_list_ranges/`
- Files:
  - `S2-02_Group_F_projection_before.png`
  - `S2-02_Group_F_projection_before.ppm`
  - `S2-02_Group_F_projection_before.usda`
  - `S2-02_Group_F_projection_after.png`
  - `S2-02_Group_F_projection_after.ppm`
  - `S2-02_Group_F_projection_after.usda`
  - `S2-02_Group_F_report_before.json`
  - `S2-02_Group_F_report_after.json`
  - `capture_results.json`
  - `assessment.md`
- Browser/live viewer blockers:
  - Playwright Desmos navigation returned `user cancelled MCP tool call`.
  - Chrome DevTools Desmos navigation returned `user cancelled MCP tool call`.
  - Playwright live-viewer navigation returned `user cancelled MCP tool call`.
  - Tailscale route checks for root, viewer, and summary failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Visual claim: no live Desmos/viewer parity claim. This tranche has deterministic local projection evidence only.

## Metrics
- Overall fixture summary: 71 fixtures, 30 success, 41 partial, 0 error, 71 USDZ, acceptance still not met.
- S2-02F official pre-tranche summary was stale at `73 prims / 41 unsupported / 111 classified`; a fresh local pre-edit export at resolution 8 showed `95 prims / 111 unsupported / 206 classified`.
- S2-02F after tracked resolution-12 regeneration: `159 prims / 47 unsupported / 206 classified / valid true / usdchecker returncode 0`.
- Fixed family: 64 repeated one-axis quadratic guide slabs from expressions `3_*` and `71_*` now export.
- Remaining S2-02F unsupported:
  - `72_*`: 9 malformed chained inequalities like `(y-c)^2 <= 0.00250 <= z <= 13.2-0.03 <= x <= 2.03`.
  - `90_*`: 21 constant-z circular explicit disk caps.
  - `98_*`: 17 constant-z circular explicit disk caps.
- S2-08 Group E guard remains success: `87 prims / 0 unsupported / valid true / usdchecker returncode 0`.
- S2-09 Group F guard remains success: `27 prims / 0 unsupported / valid true / usdchecker returncode 0`.

## Validation
- Focused regression passed: `PYTHONPATH=src:tests python3 -m unittest tests.test_student_fixture_regressions.StudentFixtureRegressionTests.test_single_axis_quadratic_inequality_band_tessellates_as_slab`.
- Targeted modules passed: `PYTHONPATH=src:tests python3 -m unittest tests.test_student_fixture_regressions tests.test_fixture_usdz_suite tests.test_visual_preview` ran 69 tests OK.
- Full unittest discovery passed: `PYTHONPATH=src:tests python3 -m unittest discover -s tests` ran 139 tests in 131.455s OK.
- Regenerated artifacts for S2-02F, S2-08E, and S2-09F with `usdchecker --arkit` return code `0`.
- Report-vs-USDA consistency checked:
  - S2-02F report prim_count `159`, USDA `Mesh` + `BasisCurves` defs `159`, unsupported `47`
  - S2-08E report prim_count `87`, USDA defs `87`, unsupported `0`
  - S2-09F report prim_count `27`, USDA defs `27`, unsupported `0`
- PNG projection dimensions checked with `sips`: before/after PNGs are `1552x512`.
- `git diff --check`: passed.

## Commit / Push
- Blocked in this HOME Codex environment.
- Final commit attempt blocker: `git add -A && git add -f artifacts/fixture_usdz/review_evidence/20260427_s202_group_f_ralph_list_ranges/ && git commit --author='chektien <www@ch3k.com>' -m 'Handle one-axis quadratic guide bands'` failed with `fatal: Unable to create '/Users/chek/repos/desmos2usd-carey/.git/index.lock': Operation not permitted`.
- Expected commit message: `Handle one-axis quadratic guide bands`.
- Include forced-add evidence if needed because `artifacts/*` may be ignored by default:
  - `git add -f artifacts/fixture_usdz/review_evidence/20260427_s202_group_f_ralph_list_ranges/`

## Review Links
- S2-02 Group F Desmos: `https://www.desmos.com/3d/1zpiejy9c9`
- S2-02 Group F viewer: `https://chq.singapura-broadnose.ts.net/viewer/?usda=..%2Fartifacts%2Ffixture_usdz%2F%5B4B%5D%203D%20Diagram%20-%20S2-02%20Group%20F.usda&label=S2-02%20Group%20F`
- S2-08 Group E Desmos: `https://www.desmos.com/3d/g59jqe6nxy`
- S2-08 Group E viewer: `https://chq.singapura-broadnose.ts.net/viewer/?usda=..%2Fartifacts%2Ffixture_usdz%2F%5B4B%5D%203D%20Diagram%20-%20S2-08%20Group%20E.usda&label=S2-08%20Group%20E`
- S2-09 Group F Desmos: `https://www.desmos.com/3d/umjxv6ahck`
- S2-09 Group F viewer: `https://chq.singapura-broadnose.ts.net/viewer/?usda=..%2Fartifacts%2Ffixture_usdz%2F%5B4B%5D%203D%20Diagram%20-%20S2-09%20Group%20F.usda&label=S2-09%20Group%20F`
- Route verification from this environment failed for root/viewer/summary with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.

## Remaining Mismatch / Next Wake Instructions
1. Continue S2-02 Group F unless Chek reprioritises; it remains the earliest highest-risk presenter and is still partial.
2. Highest-impact next target inside S2-02F is the constant-z circular explicit disk-cap family (`90_*` and `98_*`, 38 unsupported). This is likely a general explicit-surface analogue of existing flat/circular inequality disk handling.
3. After that, inspect the malformed chained `72_*` inequalities and decide whether they represent intended y-guide slabs or a genuinely empty/contradictory expression.
4. Keep S2-08E and S2-09F as regression guards.
5. Continue to include direct Tailscale viewer links and matching Desmos links in any review update, but do not claim live visual parity unless browser/viewer screenshots are actually captured.
