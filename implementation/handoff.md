# Handoff: 2026-04-26 15:46 SGT

## Active Task

Fix the remaining S2-03 Group B and S2-05 Group D visual mismatches after `e78806b`, without regenerating or regressing S2-09 Group F.

## Diagnosis

- S2-05 geometry was already tall and structurally complete: `150` prims, `0` unsupported, red legs to `z=138`, cap/spire to `z=150`.
- S2-03 geometry already had the long capped blue slab/body after the strict-slab fix.
- The fresh bad local screenshots were caused by viewer camera orientation. `viewer/app.js` interpreted `desmos:worldRotation3D` rows as right/up/depth basis vectors, which made S2-05 top-down/flat and S2-03 look like a compact front slice.
- Fixture evidence matches Desmos storing the matrix row-major while the camera basis is column-based: negative first column = depth, negative second column = screen right, third column = screen up.

## What Changed

- `viewer/app.js`
  - Changed `cameraBasisFromWorldRotation` to use the fixed column/sign mapping.
  - No exporter/tessellator semantic changes were made in this pass.

## Target Artifacts

- Regenerated S2-03 Group B `.report.json` and `.usdz`.
- Regenerated S2-05 Group D `.report.json` and `.usdz`.
- Rebuilt `artifacts/fixture_usdz/summary.json` from the existing `71` report files.
- S2-09 Group F was not regenerated and no S2-09 `.usda`, `.usdz`, or `.report.json` file changed.

## Evidence

- New evidence directory: `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_view_basis_columns/`
- Includes copied fresh Desmos screenshots, diagnostic local projections using the fixed viewer basis, `diagnostic_contact_sheet.png`, `assessment.md`, and `capture-results.json`.

Browser recapture is still blocked in this sandbox:

- Playwright MCP navigation returned `user cancelled MCP tool call`.
- Chrome DevTools MCP navigation returned `user cancelled MCP tool call`.
- Local `python3 -m http.server` bind failed with `PermissionError`.
- Chrome headless exited before producing a screenshot.
- Tailnet viewer DNS lookup failed with `curl: (6) Could not resolve host`.

## Visual Judgment

- S2-03 Group B: diagnostic projection now shows the long blue body/slab and rounded end. Browser parity remains unverified.
- S2-05 Group D: diagnostic projection now shows an upright Eiffel-tower-like structure with red legs, gray lattice, and dark cap/spire. Browser parity remains unverified.
- S2-09 Group F: no artifact regeneration; diagnostic basis check keeps the previously accepted top-cap orientation, but no browser regression screenshot was captured.

## Validation

- `node --check viewer/app.js` passed.
- `PYTHONPATH=src:tests python3 -m unittest tests.test_fixture_usdz_suite tests.test_usd_writer tests.test_student_fixture_regressions` passed: `26` tests in `35.422s`, OK.
- `git diff --check` passed.
- `usdcat -l` passed for regenerated S2-03/S2-05 `.usda` and `.usdz` files.

## Commit / Push

- Implementation commit created in writable temp clone `/tmp/desmos2usd-view-basis.VY6FQS/repo`: `76fb0c4` (`Fix Desmos view rotation basis in viewer`).
- Handoff status commit created in writable temp clone: `697563a` (`Record S2-03 S2-05 view basis handoff status`).
- Push-failure status commit created in writable temp clone: `3eb7122` (`Record S2-03 S2-05 view basis push failure`).
- Push attempted three times with `git push chektien HEAD:fix/student-fixture-usdz-export`.
- Push blocked by DNS each time: `ssh: Could not resolve hostname github.com: -65563`.
- Required remote: `git@github.com:chektien/desmos2usd.git`
- Required branch: `fix/student-fixture-usdz-export`
