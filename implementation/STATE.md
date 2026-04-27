# Implementation State

Last updated: 2026-04-27 15:24 SGT

## Loop Mode
- cadence: every 10 minutes via OpenClaw cron
- mode: improve
- repo: /Users/chek/repos/desmos2usd-carey
- branch: fix/student-fixture-usdz-export
- push-target: chektien:fix/student-fixture-usdz-export
- pr: https://github.com/careylzh/desmos2usd/pull/1
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
  1. TODAY 1610 Class 2-08: S2-08 Group G — https://www.desmos.com/3d/24vpv4pfwh — 23 unsupported, 1236 prims
  2. TODAY 1630 Class 2-10: S2-10 Group E — https://www.desmos.com/3d/xzhfl6m1td — 10 unsupported, 249 prims
  3. TODAY 1630 Class 2-10: S2-10 Group A — https://www.desmos.com/3d/g53xte50e7 — 8 unsupported, 32 prims
  4. Fixed today: S2-02 Group C — https://www.desmos.com/3d/sqn7vxcm4n — success after nested restriction pass, 169 prims, 0 unsupported
  5. Fixed today: S2-04 Group G — https://www.desmos.com/3d/ratctlkc9i — success after hsv/okhsv color-function pass, 103 prims, 0 unsupported
  6. Fixed today: S2-02 Group F — https://www.desmos.com/3d/1zpiejy9c9 — success after chained-empty pass, 206 prims, 0 unsupported
  7. Only after today's presenters are improved: resume global queue, starting with S2-01 Group A and S2-06 Group F
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
- HEAD before current tranche: 6e1b1ef Record hsv color harvest
- summary: 71 fixtures; 33 success, 38 partial, 0 error
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
- timestamp: 2026-04-27 15:24 SGT
- result: HOME Codex tranche fixed S2-02 Group C nested restrictions, regenerated S2-02C plus S2-08E/S2-09F guards, rebuilt the 71-fixture summary, and validated targeted tests (92 OK), full unittest discovery (150 OK), report-vs-USDA consistency, PNG dimensions, and `git diff --check`. Browser/live viewer capture remained blocked. Commit/push blocked by `.git/index.lock` permission failure during `git add`; worktree is ready for main-environment commit. Next wake should move to S2-08 Group G only after this dirty worktree is committed/pushed or intentionally carried forward.
