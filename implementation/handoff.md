## Handoff: 2026-04-26 09:54 SGT

### Active Task
- Continue the bounded partial/high-risk fixture improvement cycle from `artifacts/fixture_usdz/url_fixture_comparison.md`.

### What Changed
- Fixed built-in function calls adjacent to preceding variables/symbols before concatenated-symbol splitting, e.g. `z\tan(...)`, `x\cos(a)`, and `y\sin(a)`.
- Added focused regressions for parser normalization and inequality-region tessellation.
- Regenerated the full 71-fixture USDZ sweep and refreshed `artifacts/fixture_usdz/url_fixture_comparison.md`.
- `S2-09 Group F` (`umjxv6ahck`) improved from `0` prims, `27` unsupported to `3` prims, `24` unsupported; the prior `name 't' is not defined` failures are gone.
- `S2-03 Group B` (`dstsug13q6`) also improved in the same parser category: status `partial -> success`, unsupported `1 -> 0`, prims `11 -> 12`.
- CSV comparison evidence is now 66/66 rows mapped, 66/66 USDZ present, 16 success, 50 partial.
- Live Desmos check still failed: `curl -I --max-time 10 https://www.desmos.com/3d/cvggvbbe73` returned `curl: (6) Could not resolve host: www.desmos.com`; no live visual parity is claimed.
- Commit `41147b6` (`Support adjacent trig calls in fixture exports`) was pushed to `chektien:fix/student-fixture-usdz-export` after retrying from the temporary clone.

### Validation
- `PYTHONPATH=src python3 -m desmos2usd.validate.fixture_usdz_suite --out artifacts/fixture_usdz --resolution 8 --no-validate-usdz` passed: 71 fixtures, 20 success, 51 partial, 0 error, 71 USDZ present.
- `PYTHONPATH=src python3 -m desmos2usd.validate.csv_fixture_report --expect-rows 66 --live-note 'unavailable; curl -I --max-time 10 https://www.desmos.com/3d/cvggvbbe73 failed with: curl: (6) Could not resolve host: www.desmos.com'` passed: `csv_rows=66`, `status_counts=success 16, partial 50`, `usdz_present=66`.
- `PYTHONPATH=src:tests python3 -m unittest tests.test_parser.ParserTests.test_variable_adjacent_to_builtin_function_multiplies tests.test_student_fixture_regressions.StudentFixtureRegressionTests.test_variable_adjacent_trig_inequality_region_tessellates tests.test_csv_fixture_report.CsvFixtureReportTests.test_build_report_maps_csv_rows_to_summary_and_missing_state` passed: `Ran 3 tests`, OK.
- `PYTHONPATH=src:tests python3 -m unittest discover -s tests` passed: `Ran 87 tests in 202.108s`, OK.
- `git diff --check` passed.

### Executor Notes
- Codex: use raw HOME Codex via Ralph non-overlap controller.
- Claude Code: not used unless explicitly requested.
- Prefer SSH remote `git@github.com:chektien/desmos2usd.git` for pushes from this host.
- Main checkout cannot write `.git/index.lock` under the current sandbox (`Operation not permitted`), so commit/push should be done from a writable temporary clone as in the previous report wake.
- Nonsemantic `.usdz` repack churn from the full sweep was reverted; only the semantically changed `S2-03 Group B` USD/USDZ artifact remains in the diff.
- Push succeeded after retry from `/tmp/desmos2usd-trig-commit.XWnPpl/repo`.

### Risks or Open Questions
- [ ] Direct live Desmos visual comparison may remain DNS-blocked; record exact failure modes and do not claim live visual parity without a real check.
- [ ] `S2-09 Group F` still has 23 `inequality_region` sampled-cell misses and one unsupported slanted equality cylinder; the parser/evaluator gap is fixed but small/narrow region tessellation remains.
- [ ] Highest unsupported rows are still dominated by `explicit_surface`, `inequality_region`, and `classification`; choose one bounded, testable category only.

### Recommended Next Wake
- Start from `artifacts/fixture_usdz/url_fixture_comparison.md`.
- Pick one bounded fix target. Good candidates:
  - Continue `S2-09 Group F` (`umjxv6ahck`) with a narrow sampled-cell/slanted-cylinder inequality-region fix; current state is 3 prims, 24 unsupported.
  - `S2-06 Group E` (`cg2sd6h1ws`): high-impact but large, 329 unsupported, mostly `explicit_surface`.
  - `S2-01 Group A` (`cvggvbbe73`): 119 unsupported, mostly `explicit_surface`.
- Add focused regression coverage, regenerate affected fixture artifacts and summary/report as needed, run targeted tests, commit/push if coherent.

### User-Facing Update
- Variable-adjacent trig parsing is fixed, validated, and pushed to `chektien:fix/student-fixture-usdz-export` as `41147b6`.
