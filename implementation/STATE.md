# Implementation State

Last updated: 2026-04-27 20:00 SGT

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

## Active Task
- index: 1
- id: one-desmos-input-at-a-time
- title: Fix one remaining partial Desmos input per bounded tranche using live Desmos screenshots and viewer screenshots
- current-priority:
  1. TOMORROW focus: S2-01 Group E — https://www.desmos.com/3d/nzokib2plm — partial, 23 prims, 20 unsupported; highest remaining S2-01 gap
  2. TOMORROW focus: S2-01 Group C — https://www.desmos.com/3d/upbjmsjpzq — partial, 15 prims, 4 unsupported
  3. TOMORROW focus: S2-01 Group B — https://www.desmos.com/3d/27v0xuv64m — partial, 142 prims, 1 unsupported; remaining malformed disk expression `74`
  4. TOMORROW already success: S2-01 Group A — https://www.desmos.com/3d/cvggvbbe73 — 208 prims, 0 unsupported
  5. TOMORROW already success: S2-01 Group D — https://www.desmos.com/3d/z68jgsnw24 — 21 prims, 0 unsupported
  6. TOMORROW already success: S2-01 Group F — https://www.desmos.com/3d/sbrpw8amwn — 10 prims, 0 unsupported
  7. TOMORROW already success: S2-01 Group G — https://www.desmos.com/3d/jbmqctn5ic — 129 prims, 0 unsupported
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
- HEAD before current tranche: d9a8424 Render point-defined vector edges
- summary: 71 fixtures; 47 success, 24 partial, 0 error
- S2-01 Group B current tranche: static 3D vector-list rows such as `[A,B]` now classify/export as linear `BasisCurves` when entries resolve to point/vector definitions; tracked resolution-12 export improved 133 prims / 10 unsupported -> 142 prims / 1 unsupported, still partial. Remaining unsupported is malformed flat-disk inequality `74` (`x^{2}+y^{2}<=5000z=0`). Browser/live viewer capture remains blocked by MCP cancellation and Tailscale DNS failure, so visual claim is structural/local projection only.
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
- timestamp: 2026-04-27 20:00 SGT
- result: harvested dirty run `20260427-193331-22493`, revalidated targeted modules (104 tests OK), full unittest discovery (163 tests OK), and `git diff --check`, then committed and pushed `ee7335c` (`Render point-list curves`). No new implementation pass launched; next wake should continue S2-01 Group B expression `74` (`x^{2}+y^{2}<=5000z=0`).
