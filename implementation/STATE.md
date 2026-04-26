# Implementation State

Last updated: 2026-04-26 15:46 SGT

## Loop Mode
- cadence: 10 one-shot cron wakes, 30 minutes apart
- mode: improve
- repo: /Users/chek/repos/desmos2usd-carey
- branch: fix/student-fixture-usdz-export
- pr: https://github.com/careylzh/desmos2usd/pull/1
- non-overlap: true; if an active Codex run is still going, later cron wakes must leave it alone and exit

## Executor Policy
- primary: home-codex-raw on chekstool
- optional-review: disabled unless Chek asks
- commit policy: commit after each wake completes a coherent task with passing validation; push to `chektien:fix/student-fixture-usdz-export`
- author: chektien <www@ch3k.com>

## Data Sources
- original URL CSV: /Users/chek/.openclaw/workspace/tmp/desmos2usd-ralph-control/desmos_urls_latest.csv, copied from /Users/chek/icloud/Downloads/desmos_urls_latest.csv; 66 rows parsed
- generated fixture artifacts: artifacts/fixture_usdz/
- viewer: http://chq.singapura-broadnose.ts.net:8765/viewer/

## Active Task
- index: 3
- id: fixture-viewer-camera-parity
- title: Apply saved Desmos 3D view metadata in the USDA viewer
- done-when:
  - viewer uses saved Desmos 3D view metadata from USDA when present
  - S2-03 Group B, S2-05 Group D, and S2-09 Group F artifacts carry view metadata
  - Playwright screenshot comparison is attempted and any environment failures are recorded
  - validation passes
  - the coherent fix is committed and pushed to `chektien:fix/student-fixture-usdz-export`

## Current Run Update
- task: continue after fresh evidence showed S2-03 Group B still partial and S2-05 Group D still unacceptable after `e78806b`.
- diagnosis:
  - S2-05 exported geometry is already tall in world coordinates: red legs reach `z=138`, cap/spire reaches `z=150`, and reports show `150` prims with `0` unsupported.
  - S2-03 exported geometry already contains the long capped slab/body after `e78806b`; the local screenshot collapsed it because the viewer looked along the wrong saved rotation basis.
  - root cause is viewer camera metadata interpretation, not another parametric-domain or slab tessellation failure: `viewer/app.js` treated Desmos `worldRotation3D` rows as camera basis vectors. Fixture evidence matches a row-major matrix whose columns are camera depth, screen-left, and screen-up.
- code changes:
  - `viewer/app.js` now derives camera depth from the negative first column, screen-right from the negative second column, and screen-up from the third column.
  - This keeps S2-05 upright instead of top-down/flattened and restores S2-03's long horizontal body with the rounded end visible.
- artifacts:
  - S2-03 Group B and S2-05 Group D `.report.json`/`.usdz` were regenerated with the existing exporter at resolution `8`.
  - `artifacts/fixture_usdz/summary.json` was rebuilt from the existing `71` report files.
  - S2-09 Group F was not regenerated and no S2-09 `.usda`, `.usdz`, or `.report.json` file was changed.
- evidence:
  - `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_view_basis_columns/assessment.md`
  - `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_view_basis_columns/capture-results.json`
  - `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_view_basis_columns/diagnostic_contact_sheet.png`
- screenshot capture status:
  - Fresh Desmos screenshots were copied from `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_after_domain_caps_recheck/`.
  - Browser recapture remains blocked in this sandbox: Playwright MCP and Chrome DevTools MCP navigation returned `user cancelled MCP tool call`, local `http.server` bind failed with `PermissionError`, Chrome headless exited without a screenshot, and `curl` to the tailnet viewer failed DNS.
  - Diagnostic local projections were generated from current geometry using the fixed viewer basis; they are not a substitute for WebGL/Playwright screenshots, so browser parity remains unverified.
- target results:
  - S2-03 Group B remains `success`, `12` prims, `0` unsupported; diagnostic projection now shows the long blue slab/body and rounded end.
  - S2-05 Group D remains `success`, `150` prims, `0` unsupported; diagnostic projection now shows an upright Eiffel-tower-like structure with red legs, gray lattice, and dark cap/spire.
  - S2-09 Group F was checked only through the same diagnostic camera-basis projection; no S2-09 artifact regeneration was performed.
- validation:
  - `node --check viewer/app.js` passed.
  - `PYTHONPATH=src:tests python3 -m unittest tests.test_fixture_usdz_suite tests.test_usd_writer tests.test_student_fixture_regressions` passed: `26` tests in `35.422s`, OK.
  - `git diff --check` passed.
  - `usdcat -l` passed for regenerated S2-03/S2-05 `.usda` and `.usdz` files.
- commit/push status:
  - implementation commit in writable temp clone `/tmp/desmos2usd-view-basis.VY6FQS/repo`: `76fb0c4` (`Fix Desmos view rotation basis in viewer`).
  - handoff status commit in writable temp clone: `697563a` (`Record S2-03 S2-05 view basis handoff status`).
  - push-failure status commit in writable temp clone: `3eb7122` (`Record S2-03 S2-05 view basis push failure`).
  - push attempted three times with `git push chektien HEAD:fix/student-fixture-usdz-export`.
  - push blocked by DNS each time: `ssh: Could not resolve hostname github.com: -65563`.

## Ordered Task Cycle
1. [x] Recover interrupted readable-CSV/list-expansion changes, regenerate all fixture artifacts, validate, commit/push if sound.
2. [x] Build a CSV-to-fixture comparison report covering all 66 original Desmos URLs, with direct Desmos state/render evidence where available and clear unknowns where not.
3. [ ] Prioritize remaining partial fixtures by unsupported-count and visual-risk; fix one bounded mismatch category per wake.
4. [ ] Regenerate affected/full fixture artifacts, validate, commit/push, and comment on PR with concise evidence.
5. [ ] Repeat improvement pass until all 10 cron wakes are exhausted or no safe fixes remain.

## Known Current State
- Current viewer-camera fix is implemented locally:
  - `viewer/app.js` now parses quoted USD `customLayerData` keys and uses `desmos:worldRotation3D` as a full camera basis when present.
  - `src/desmos2usd/usd/writer.py` emits `desmos:worldRotation3D`, `desmos:axis3D`, and Desmos view flags into USDA layer metadata.
  - `src/desmos2usd/validate/fixture_usdz_suite.py` records `view_metadata` in fixture reports.
  - Target artifacts regenerated:
    - `S2-03 Group B`: success, `12` prims, `0` unsupported, `world_rotation_3d` length `9`.
    - `S2-05 Group D`: success, `150` prims, `0` unsupported, `world_rotation_3d` length `9`.
    - `S2-09 Group F`: success, `27` prims, `0` unsupported, `world_rotation_3d` length `9`, `degree_mode=true`.
- New evidence/assessment path:
  - `artifacts/fixture_usdz/review_evidence/20260426_view_metadata_parity/assessment.md`
  - `artifacts/fixture_usdz/review_evidence/20260426_view_metadata_parity/capture-results.json`
- After-change screenshot capture is blocked in this sandbox:
  - `python3 -m http.server 8776 --bind 127.0.0.1` failed with `PermissionError: [Errno 1] Operation not permitted`.
  - `curl` to `chq.singapura-broadnose.ts.net` failed with `curl: (6) Could not resolve host`.
  - Playwright Chromium launch failed with `bootstrap_check_in org.chromium.Chromium.MachPortRendezvousServer: Permission denied (1100)` and SIGTRAP/SIGABRT.
  - MCP browser calls were immediately cancelled before navigation.
- Visual parity judgment for S2-03/S2-05/S2-09: previous Playwright evidence showed camera/framing mismatch; after-change screenshot parity remains unverified and must not be claimed until a browser-capable environment recaptures local viewer screenshots.
- PR #1 already has commits `baa8963` and `20b23c1` pushed.
- The readable-CSV/list-expansion recovery pass was validated with a full 71-fixture sweep:
  - `fixture_count=71`
  - `fixtures_with_usdz_count=71`
  - `error_count=0`
  - `success_count=19`
  - `partial_count=52`
- Recovered support covers Desmos ellipsis lists, scalar formulas over lists, `mod`, `\pi` implicit multiplication, and narrow single-letter implicit multiplication during list expansion.
- Recovery commit `13c4bff` (`Support Desmos list range fixture expansion`) has been pushed to `chektien:fix/student-fixture-usdz-export`.
- Main checkout is clean at `41147b6`.
- CSV comparison report `artifacts/fixture_usdz/url_fixture_comparison.md` now maps all 66 original URLs to frozen fixture states and the current fixture sweep reports:
  - CSV rows mapped: `66/66`
  - frozen fixture states present: `66/66`
  - sweep reports present: `66/66`
  - USDZ artifacts present: `66/66`
  - sweep status over CSV rows: `16` success, `50` partial, `0` error
  - current CSV-row totals: `1529` unsupported expressions, `6942` classified expressions, `5823` exported prims
  - unsupported kind counts: `inequality_region=558`, `explicit_surface=549`, `classification=401`, `definition=9`, `triangle_mesh=8`, `parametric_surface=4`
  - highest unsupported rows: `S2-06 Group E` (`329`), `S2-03 Group D` (`122`), `S2-01 Group A` (`119`), `S2-03 Group E` (`97`), `S2-10 Group F` (`82`)
  - lowest-prim partial risk starts with `S2-05 Group A` (`2` prims), then `S2-09 Group F` (`3` prims, `24` unsupported), `S2-10 Group C` (`3` prims)
- Comparison report commit `e9623ba` (`Add CSV fixture comparison report`) has been pushed to `chektien:fix/student-fixture-usdz-export`.
- Current parser fix supports built-in function calls adjacent to preceding variables/symbols before concatenated-symbol splitting, e.g. `z\tan(...)`, `x\cos(a)`, and `y\sin(a)`.
- Full fixture sweep after the degree-mode/circular-extrusion fix reports:
  - `fixture_count=71`
  - `fixtures_with_usdz_count=71`
  - `error_count=0`
  - `success_count=21`
  - `partial_count=50`
- Target fixture result:
  - `S2-03 Group B` (`dstsug13q6`) remains structural success: `12` classified, `12` prims, `0` unsupported. Current local evidence shows the ground/slab regions and fin surfaces are exported; live visual parity is unverified.
  - `S2-05 Group D` (`5jh9zwy75e`) remains structural success: `150` classified, `150` prims, `0` unsupported, including `25` mesh surface prims and `125` curve prims; live visual parity is unverified.
  - `S2-09 Group F` (`umjxv6ahck`) improved from partial to success: `27` classified, `27` prims, `0` unsupported. The fix combines graph `degreeMode` trig evaluation with circular extrusion for bounded slanted cylinder solids/surfaces.
- CSV comparison report now maps all 66 URLs and reports `17` success, `49` partial, `0` error.
- Live Desmos/browser visual comparison was not available in this wake:
  - Playwright/Chrome DevTools calls were cancelled before navigation.
  - `curl -I --max-time 10` for `dstsug13q6`, `5jh9zwy75e`, and `umjxv6ahck` failed with `curl: (6) Could not resolve host: www.desmos.com`.
  - The report records structural/frozen-state/local projection evidence only and does not claim live visual parity.
- Local visual/evidence artifacts:
  - `artifacts/fixture_usdz/review_evidence/20260426_user_review/S2-03_Group_B_local_projection.png`
  - `artifacts/fixture_usdz/review_evidence/20260426_user_review/S2-05_Group_D_local_projection.png`
  - `artifacts/fixture_usdz/review_evidence/20260426_user_review/S2-09_Group_F_local_projection.png`
- Changed URL evidence from the CSV was recorded for eight affected student fixtures:
  - `https://www.desmos.com/3d/27v0xuv64m` (`S2-01 Group B`): classified `18 -> 116`, prims `15 -> 115`
  - `https://www.desmos.com/3d/1zpiejy9c9` (`S2-02 Group F`): classified `15 -> 111`, prims `4 -> 62`
  - `https://www.desmos.com/3d/sqkhp7wnx6` (`S2-03 Group E`): classified `178 -> 185`
  - `https://www.desmos.com/3d/5jh9zwy75e` (`S2-05 Group D`): status `partial -> success`, unsupported `8 -> 0`
  - `https://www.desmos.com/3d/cg2sd6h1ws` (`S2-06 Group E`): classified `24 -> 736`, prims `4 -> 407`
  - `https://www.desmos.com/3d/xrsgrdip5y` (`S2-08 Group C`): prims `9 -> 12`, unsupported `4 -> 1`
  - `https://www.desmos.com/3d/151jsdn8xs` (`S2-10 Group C`): prims `2 -> 3`, unsupported `6 -> 5`
  - `https://www.desmos.com/3d/tejhfrm34m` (`S2-10 Group F`): prims `83 -> 85`, unsupported `84 -> 82`

## Blockers
- Direct browser/Desmos rendering may be flaky; if live Desmos cannot be loaded, use frozen state plus local viewer/artifact structural evidence and say so.
- Live Desmos DNS failed during this wake; continue recording exact live-check failures and do not claim visual parity without an actual live/browser comparison.
- Main checkout Git index writes may be blocked in Codex sandbox runs; use a writable temporary clone for commit/push if needed.
- GitHub SSH push from the temporary clone initially failed during this wake because `github.com` could not be resolved, but a later retry succeeded.

## Last Wake
- timestamp: 2026-04-26 12:40 SGT
- result: implemented saved Desmos 3D view metadata in USDA layer metadata and the local viewer camera path; regenerated S2-03 Group B, S2-05 Group D, and S2-09 Group F artifacts; after-change screenshots remain blocked by local browser/DNS permissions.
- validation:
  - `node --check viewer/app.js` passed.
  - `PYTHONPATH=src:tests python3 -m unittest tests.test_usd_writer tests.test_fixture_usdz_suite tests.test_parser.ParserTests.test_required_fixture_view_metadata_is_parsed` passed: 7 tests, OK.
  - `PYTHONPATH=src:tests python3 -m unittest discover -s tests` passed: 92 tests in 196.151s, OK.
  - `git diff --check` passed.
- commit/push:
  - Temporary clone: `/tmp/desmos2usd-view-camera.bJufZM/repo`
  - Implementation commit: `6e77fe1` (`Use saved Desmos view metadata in viewer`)
  - Push command attempted three times: `git push chektien HEAD:fix/student-fixture-usdz-export`
  - Push result: blocked, `ssh: Could not resolve hostname github.com: -65563`
