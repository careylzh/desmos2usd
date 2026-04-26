# Implementation State

Last updated: 2026-04-27 03:08 SGT

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
  1. S2-03 Group D — https://www.desmos.com/3d/zvasa1wcgo — 12 unsupported, 573 prims, 585 classified after z-band union tranche; still partial and needs live visual evidence
  2. S2-03 Group E — https://www.desmos.com/3d/sqkhp7wnx6 — 85 unsupported, 111 prims, 190 classified
  3. S2-07 Group F — https://www.desmos.com/3d/jkj1z8t8pf — 69 unsupported, 36 prims, 37 classified
  4. S2-06 Group E — https://www.desmos.com/3d/cg2sd6h1ws — 57 unsupported after pass 5, 679 prims, 736 classified
  5. S2-10 Group F — https://www.desmos.com/3d/tejhfrm34m — 47 unsupported, 120 prims, 167 classified
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
- HEAD: 9a939b0 Improve S2-03D list broadcast classification
- summary: 71 fixtures; 25 success, 46 partial, 0 error
- S2-03 Group D current worktree tranche: 92 unsupported -> 12 unsupported, 269 prims -> 573 prims; live browser/viewer capture blocked, so structural progress only
- S2-06 Group E pass 5: 321 unsupported -> 57 unsupported, still partial; ccwork approved pass 5 as technically sound
- S2-08 Group E: success, 83 prims, 0 unsupported; pass-4 visual evidence exists
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
- timestamp: 2026-04-27 03:08 SGT
- result: completed raw HOME Codex S2-03D z-band union tranche; focused and full regression validation passed; commit/push blocked because Codex could not create `.git/index.lock` (`Operation not permitted`).
