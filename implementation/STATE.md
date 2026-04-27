# Implementation State

Last updated: 2026-04-27 07:58 SGT

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
  1. Continue S2-03 Group E remaining spherical caps / non-affine arc cutouts — https://www.desmos.com/3d/sqkhp7wnx6 — now 17 unsupported, 447 prims, 464 classified
  2. Continue S2-07 Group F remaining parser/classifier slabs and sampled inequality — https://www.desmos.com/3d/jkj1z8t8pf — now 14 unsupported, 874 prims, 875 classified
  3. Continue S2-06 Group E remaining elliptical annular slabs / y-squared bridge surfaces / random Gaussian regions — https://www.desmos.com/3d/cg2sd6h1ws — now 13 unsupported, 723 prims, 736 classified
  4. Revisit S2-10 Group F only for live visual parity evidence when browser capture is available — https://www.desmos.com/3d/tejhfrm34m — structurally success, 167 prims, 0 unsupported
  5. Revisit S2-03 Group D only for live visual parity evidence when browser capture is available — https://www.desmos.com/3d/zvasa1wcgo — structurally success, 585 prims, 0 unsupported
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
- HEAD before current tranche: 9b4b25e Improve S2-10F modulo inequality regions
- summary: 71 fixtures; 27 success, 44 partial, 0 error
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
- timestamp: 2026-04-27 07:58 SGT
- result: HOME Codex completed one S2-10F ball-cap tranche. Implemented a general axis-aligned ellipsoid inequality-region cap path; S2-10F improved to success at 167 prims, 0 unsupported. S2-08E and S2-09F remain success guards. Browser/live viewer capture remains blocked by MCP cancellation and local server bind denial, so no live visual parity claim. Commit/push blocked before staging by `.git/index.lock` permission denial.
