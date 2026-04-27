# Implementation State

Last updated: 2026-04-28 00:10 SGT

## Loop Mode
- cadence: every 10 minutes via OpenClaw cron
- mode: improve
- repo: /Users/chek/repos/desmos2usd-carey
- branch: fix/student-fixture-usdz-export
- push-target: chektien:fix/student-fixture-usdz-export
- pr: https://github.com/careylzh/desmos2usd/pull/2
- non-overlap: true; if a previous Codex or ccwork run is still active, a cron wake must leave it running and not start another implementation pass

## Executor Policy
- primary: raw HOME Codex on chekstool
- reviewer: ccwork/Claude on chekbook only when explicitly launched by the orchestrator
- commit policy: commit and push coherent fixes with passing validation; if Codex cannot write `.git`, the orchestrator/next wake must commit from the main environment before launching more work
- author: chektien <www@ch3k.com>

## Visual-Fidelity Gate
- For each chosen Desmos input, load the Desmos URL in a browser-capable path, wait until the model appears, and capture several reference screenshots before fixing.
- Regenerate the USD/USDZ and load it in the live viewer.
- Iterate until the viewer rendering visually matches the Desmos screenshots enough to be defensible, or record the exact blocker.
- Metrics, prim counts, unsupported counts, valid USD, and report consistency are necessary but not sufficient; live visual evidence is authoritative.
- Do not claim full parity without browser/viewer screenshots.
- Do not claim a fixture/model is done until the rendered model from the Desmos URL has been checked against the generated viewer/USDZ and the match is defensible; metrics-only success is structural progress only.

## Active Task
- index: 1
- id: one-desmos-input-at-a-time
- title: Fix one remaining partial Desmos input per bounded tranche using live Desmos screenshots and viewer screenshots
- current-priority:
  1. TOMORROW visual blocker / first class: S2-01 Group B — https://www.desmos.com/3d/27v0xuv64m — metrics say 143 prims / 0 unsupported, but Chek reported the viewer still looked wrong; the viewer saved-camera basis fix is already in, but live browser/viewer evidence remains blocked here, so keep it review-pinned until Chek accepts the direct viewer link or gives fresh visual feedback
  2. TOMORROW high gap: S2-09 Group A — https://www.desmos.com/3d/gk9kr8h9ki — partial, 22 prims, 40 unsupported
  3. TOMORROW high gap: S2-06 Group A — https://www.desmos.com/3d/lvj5ymlrba — partial, 499 prims, 18 unsupported
  4. TOMORROW high gap: S2-09 Group D — https://www.desmos.com/3d/zxjnvkynzf — partial, 102 prims, 12 unsupported
  5. TOMORROW high gap: S2-03 Group C — https://www.desmos.com/3d/xyvxakzxdj — partial, 122 prims, 9 unsupported
  6. TOMORROW remaining partials: S2-09B (4), S2-05F (3), S2-03A (2), S2-07C (2), S2-09C (2), S2-09E (2), S2-09G (2), S2-07D (1), S2-07E (1)
  7. TOMORROW already metrics-success: S2-01A/C/D/E/F/G, S2-03B/D/E/F, S2-05A/B/C/D/E, S2-06B/C/D/E/F/G, S2-07A/B/F, S2-09F
  8. Defer unless Chek reopens it: S2-10 Group E — https://www.desmos.com/3d/xzhfl6m1td — metrics say success after label filtering, but Chek reported the viewer still looks broken; do not call it visually fixed from metrics alone
- done-when:
  - one chosen fixture has fresh Desmos reference screenshots
  - live viewer screenshots/projections exist for the generated USD artifact
  - a general exporter/viewer fix is implemented, not a fixture-specific hack
  - S2-08 Group E and S2-09 Group F remain safe regression guards
  - validation passes
  - changes are committed and pushed, or the exact commit/push blocker is recorded

## Ordered Task Cycle
1. [ ] Pick the next highest-impact partial fixture and capture Desmos reference screenshots.
2. [ ] Diagnose the largest general unsupported/visual mismatch family for that single fixture.
3. [ ] Implement one bounded exporter/viewer fix and add regression tests.
4. [ ] Regenerate affected artifacts and summary.
5. [ ] Capture viewer screenshots/projections and compare against Desmos references.
6. [ ] Validate, commit, push, and update handoff.
7. [ ] Advance to the next input only after the current one is either defensibly fixed or explicitly blocked.

## Current Baseline
- HEAD before current tranche: ace64b0 Record S2-01B visual retry blocker
- summary: 71 fixtures; 50 success, 21 partial, 0 error
- S2-01 Group B visual retry 3 blocker tranche: HOME Codex retried the pinned S2-01B visual gate again. Playwright and Chrome DevTools still return `user cancelled MCP tool call` for Desmos and `file://` viewer navigation; Tailscale route checks still fail DNS; local `python3 -m http.server 8765 --bind 127.0.0.1` still fails with `PermissionError: [Errno 1] Operation not permitted`; headless Chrome `file://` screenshots exit `-1` with no screenshot; live Desmos URL refresh fails DNS. Offline precheck/projections remain success for S2-01B (`143 prims / 0 unsupported`) and guards S2-08E/S2-09F. No exporter/viewer code change was safe without live screenshots or fresh Chek visual feedback.
- S2-01 Group B visual retry 2 blocker tranche: HOME Codex retried the pinned S2-01B visual gate again. Playwright and Chrome DevTools still return `user cancelled MCP tool call` for Desmos and `file://` viewer navigation; Tailscale route checks still fail DNS; local `python3 -m http.server 8765 --bind 127.0.0.1` still fails with `PermissionError: [Errno 1] Operation not permitted`; headless Chrome `file://` screenshot exits `134` with no screenshot; live Desmos URL refresh fails DNS. Offline precheck/projections remain success for S2-01B (`143 prims / 0 unsupported`) and guards S2-08E/S2-09F. No exporter/viewer code change was safe without live screenshots or fresh Chek visual feedback.
- S2-01 Group B visual gate retry blocker tranche: HOME Codex retried the pinned S2-01B visual gate. Chrome DevTools and Playwright still return `user cancelled MCP tool call` for both Desmos and `file://` viewer navigation; Tailscale route checks still fail DNS; local `python3 -m http.server 8765 --bind 127.0.0.1` still fails with `PermissionError: [Errno 1] Operation not permitted`; headless Chrome `file://` screenshot exits `-1` with no screenshot; URL conversion against Desmos also fails DNS. Offline precheck/projections remain success for S2-01B (`143 prims / 0 unsupported`) and guards S2-08E/S2-09F. No new code fix was safe without live screenshots or fresh Chek visual feedback.
- S2-01 Group B live-review blocker tranche: HOME Codex retried the pinned S2-01B visual gate after the camera-basis fix. Chrome DevTools and Playwright still return `user cancelled MCP tool call` for both Desmos and `file://` viewer navigation; Tailscale route checks still fail DNS; local `python3 -m http.server 8765 --bind 127.0.0.1` still fails with `PermissionError: [Errno 1] Operation not permitted`; headless Chrome `file://` screenshot exits `-1` with no screenshot. Offline precheck remains success for S2-01B (`143 prims / 0 unsupported`) and guards S2-08E/S2-09F. No new code fix was safe without live screenshots or fresh Chek visual feedback.
- S2-01 Group B current viewer-camera tranche: static viewer `worldRotation3D` handling now uses Desmos row-major camera basis rows directly (`row0` screen-right, `row1` screen-up, `row2` depth) instead of transposed columns with sign flips. This is a general viewer fix for saved-source-view mismatch and does not change geometry metrics: S2-01B remains 143 prims / 0 unsupported / success; S2-08 Group E and S2-09 Group F guards remain success. Browser/live viewer capture remains blocked by MCP cancellation, local server permission failure, headless Chrome failure, and Tailscale DNS failure, so visual claim is structural/local projection plus camera-basis diagnostics only.
- S2-01 Group B current visual tranche: constant explicit panels with finite constant bounds on both domain axes are no longer dropped solely because the solved axis is outside the saved source viewport. Tracked S2-01B remains 143 prims / 0 unsupported / success, but expression `8` (`z=130 {-10<=x<=10}{-10<=y<=10}`) improved from a valid empty mesh (`0 points / 0 faces`) to `196 points / 169 faces`. Nonconstant out-of-viewport suppression remains guarded by `ghnr7txz47` expr `835`. Browser/live viewer capture remains blocked by MCP cancellation, local server permission failure, headless Chrome sandbox failure, and Tailscale DNS failure, so visual claim is structural/local projection only.
- S2-01 Group B current tranche: malformed flat-axis chained comparisons such as `x^{2}+y^{2}<=5000z=0` now normalize to an ordinary 2D inequality plus a constant-axis predicate, equivalent to `x^{2}+y^{2}<=5000 {z=0}`. Tracked resolution-12 export improved 142 prims / 1 unsupported / 143 classified / 143 renderable -> 143 prims / 0 unsupported / 143 classified / 143 renderable, success. S2-08 Group E and S2-09 Group F guards remain success. Browser/live viewer capture remains blocked by MCP cancellation, local server permission failure, and Tailscale DNS failure, so visual claim is deterministic local projection only.
- S2-01 Group C current tranche: scalar-list expressions with implicit numeric multiplication such as `3n` now expand from hidden list definitions, axis-aligned `abs(axis)` interval regions export as disjoint rectangular shell extrusions, and one-axis implicit equalities with bounded cross axes export as sheet meshes. Tracked resolution-12 export improved 15 prims / 4 unsupported / 18 classified / 19 renderable -> 27 prims / 0 unsupported / 27 classified / 27 renderable, success. S2-08 Group E and S2-09 Group F guards remain success. Browser/live viewer capture remains blocked by MCP cancellation, local server permission failure, and Tailscale DNS failure, so visual claim is deterministic local projection only.
- S2-01 Group E current tranche: scaled band-axis comparisons such as `2z < f(x)` now produce normalized function bounds, and curved thin bands can extrude through affine cross-axis bounds. Tracked resolution-12 export improved 23 prims / 20 unsupported -> fresh pre-edit local 39 prims / 4 unsupported -> regenerated 43 prims / 0 unsupported, success. S2-08 Group E and S2-09 Group F guards remain success. Browser/live viewer capture remains blocked by MCP cancellation, local server permission failure, and Tailscale DNS failure, so visual claim is deterministic local projection only.
- S2-01 Group B previous tranche: static 3D vector-list rows such as `[A,B]` now classify/export as linear `BasisCurves` when entries resolve to point/vector definitions; tracked resolution-12 export improved 133 prims / 10 unsupported -> 142 prims / 1 unsupported, still partial. Remaining unsupported was malformed flat-disk inequality `74` (`x^{2}+y^{2}<=5000z=0`). Browser/live viewer capture remained blocked by MCP cancellation and Tailscale DNS failure, so visual claim was structural/local projection only.
- S2-01 Group B previous tranche: point-defined vector expressions such as `A+t(B-A)` now classify/export as parametric `BasisCurves`; tracked resolution-12 export improved 116 prims / 27 unsupported -> 133 prims / 10 unsupported, still partial. Remaining unsupported were nine point-list rows like `[A,B]` and malformed flat-disk inequality `74` (`x^{2}+y^{2}<=5000z=0`). Browser/live viewer capture remained blocked by MCP cancellation and Tailscale DNS failure, so visual claim was structural/local projection only.
- S2-01 Group A current tranche: affine-clipped explicit-surface domain inference now substitutes the solved axis into linear predicates and clips the two domain axes before grid sampling; tracked export improved from HEAD-projection 90 prims / 118 unsupported to regenerated 208 prims / 0 unsupported, success. Browser/live viewer capture remains blocked by MCP cancellation and Tailscale DNS failure, so visual claim is structural/local projection only.
- S2-10 Group A current tranche: affine-clipped function-band variable extrusion fixed expression `41`, the obliquely clipped parabolic inequality region; tracked export improved 39 prims / 1 unsupported to 40 prims / 0 unsupported, success. Browser/live viewer capture remains blocked by MCP cancellation and Tailscale DNS failure, so visual claim is structural/local projection only.
- S2-10 Group A previous tranche: unbraced Desmos trig commands such as `\sin7x` now parse as function calls with implicit argument multiplication; tracked export improved 35 prims / 5 unsupported to 39 prims / 1 unsupported, with all four sinusoidal border surfaces `59`, `60`, `61`, and `62` exported. Browser/live viewer capture blocked by MCP cancellation and Tailscale DNS failure, so visual claim is structural/local projection only.
- S2-10 Group E current tranche: tracked artifact improved 249 prims / 10 unsupported / 259 renderable -> 249 prims / 0 unsupported / 249 renderable, success. The unsupported rows were non-graphable section labels/separators such as `pyramid 4 sketch`, not Desmos geometry; visible expression rows with only label text are now filtered out before classification. Browser/live viewer capture blocked, so visual claim is structural/local projection only and geometry projection is unchanged.
- S2-08 Group G current tranche: tracked artifact improved 1236 prims / 23 unsupported -> fresh pre-disk 1833 prims / 2 unsupported -> regenerated 1835 prims / 0 unsupported, success. Existing list tuple expansion covered the stale tracked unsupported family; this tranche added a general zero-height circular inequality flat-disk mesh for strict constant-z disks `800` and `801`. Browser/live viewer capture blocked, so visual claim is structural/local projection only.
- S2-02 Group C current tranche: nested restriction flattening fixed Desmos predicates like `quadratic > 1 {2.7 > y > 2}`; tracked resolution-12 export improved 133 prims / 36 unsupported -> 169 prims / 0 unsupported, success. Fresh local pre-edit from current code was 149 prims / 20 unsupported. Browser/live viewer capture blocked, so visual claim is structural/local projection only.
- S2-04 Group G current tranche: static Desmos `hsv(...)`/`okhsv(...)` color definitions now resolve through `colorLatex`; tracked resolution-12 export improved 103 prims / 3 unsupported -> 103 prims / 0 unsupported, success. Browser/live viewer capture blocked, so visual claim is structural/local projection only.
- S2-02 Group F current tranche: chained predicate constant-bound contradictions now export as valid empty meshes; tracked resolution-12 export improved 197 prims / 9 unsupported -> 206 prims / 0 unsupported, success. Browser/live viewer capture blocked, so visual claim is structural/local projection only.
- S2-02 Group F previous tranche: constant-z explicit circular disk caps improved tracked resolution-12 export 47 unsupported -> 9 unsupported and 159 prims -> 197 prims; all `90_*` and `98_*` cap surfaces now export; remaining unsupported were nine malformed chained `72_*` inequalities; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-02 Group F previous tranche: list-expanded one-axis quadratic guide bands improved fresh local export 111 unsupported -> 47 unsupported and 95 prims -> 159 prims; tracked resolution-12 artifact was 159 prims / 47 unsupported / 206 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-07 Group F current tranche: chained quadratic disk inequality support improved 1 unsupported -> 0 unsupported, 887 prims -> 888 prims, 888 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-03 Group E current tranche: predicate-clipped implicit ellipsoid surfaces improved 4 unsupported -> 0 unsupported, 460 prims -> 464 prims, classified remains 464; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-06 Group E current tranche: seeded bounded `random(n)` expansion plus Gaussian local flat-region sampling improved 7 unsupported -> 0 unsupported, 729 prims -> 1625 prims, 736 classified -> 1625 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-06 Group E current tranche: steep explicit-surface reorientation improved 9 unsupported -> 7 unsupported, 727 prims -> 729 prims, classified remains 736; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-06 Group E current tranche: annular quadratic slab extrusion improved 13 unsupported -> 9 unsupported, 723 prims -> 727 prims, classified remains 736; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-07 Group F current tranche: leading-dot decimal implicit multiplication pass improved 14 unsupported -> 1 unsupported, 874 prims -> 887 prims, 875 classified -> 888 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-03 Group E current tranche: fresh pre-edit export was 12 unsupported / 452 prims; adaptive sampled inequality retry improved it to 4 unsupported / 460 prims, classified remains 464; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-10 Group F current tranche: ball-cap pass improved 20 unsupported -> 0 unsupported, 147 prims -> 167 prims, classified remains 167; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-10 Group F current tranche: modulo cylinder/slat/box pass improved 47 unsupported -> 20 unsupported, 120 prims -> 147 prims, classified remains 167; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-07 Group F current tranche: unbounded implicit sphere pass improved 53 unsupported -> 14 unsupported, 835 prims -> 874 prims, classified remains 875; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-07 Group F current tranche: point-list triangle indexing pass improved 69 unsupported -> 53 unsupported, 36 prims -> 835 prims, 37 classified -> 875 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-03 Group E affine-band tranche: 71 unsupported -> 17 unsupported, 393 prims -> 447 prims, 464 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-03 Group E previous tranche: 85 unsupported -> 71 unsupported, 111 prims -> 393 prims, 190 classified -> 464 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-03 Group D current tranche: 12 unsupported -> 0 unsupported, 573 prims -> 585 prims; live browser/viewer capture blocked, so structural/local projection progress only
- S2-06 Group E current tranche: 57 unsupported -> 13 unsupported, 679 prims -> 723 prims, 736 classified; live browser/viewer capture blocked, so visual claim is structural/local projection only
- S2-06 Group E pass 5: 321 unsupported -> 57 unsupported, still partial; ccwork approved pass 5 as technically sound
- S2-08 Group E: success, 87 prims, 0 unsupported; current guard projection exists
- S2-09 Group F: success, 27 prims, 0 unsupported

## Control
- cron control directory: /Users/chek/.openclaw/workspace/tmp/desmos2usd-ralph-control
- worker prompt: /Users/chek/.openclaw/workspace/tmp/desmos2usd-ralph-control/worker-prompt.md
- progress updates: every cron wake should deliver a concise message to the Discord thread, including whether it launched, skipped due active run, harvested, committed, or blocked

## Blockers / Cautions
- Existing public branch still contains agentic implementation files; Chek separately asked for a later clean-public-branch/history rewrite pass. Do not do that destructive cleanup inside the cron loop unless explicitly asked.
- Browser capture can be flaky. If live Desmos or viewer capture fails, record the exact failure and do not claim parity.
- Do not overlap Codex/ccwork runs.

## Last Wake
- timestamp: 2026-04-28 00:10 SGT
- result: HOME Codex ran one bounded S2-01 Group B visual-gate retry tranche. No exporter/viewer code change was made because S2-01B remains metrics-success and all live Desmos/viewer capture paths are still blocked in this environment. Recorded blocker evidence, regenerated offline precheck/projection artifacts for S2-01B plus S2-08E/S2-09F guards, and validated viewer JS syntax, focused tests, full tests, report-vs-USDA consistency, JSON validity, projection dimensions, and `git diff --check`. Commit/push is blocked here by `.git/index.lock` permission failure; main environment should stage, commit, and push the ready worktree. Next action is Chek review or fresh visual mismatch detail for S2-01B; if accepted/not reopened, advance to S2-09 Group A.
