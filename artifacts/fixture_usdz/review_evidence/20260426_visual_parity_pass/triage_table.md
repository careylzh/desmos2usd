# All-fixture triage — 2026-04-26 visual parity pass

Status legend:
- **OK**: matches Desmos closely; no obvious work needed
- **IMPROVED**: clearly better after this pass; minor differences remain but
  the scene reads as the intended Desmos figure
- **NEEDS-WORK**: still has visible issues; itemized blockers below
- **BLOCKED**: cannot reasonably be repaired with current exporter/viewer
  capabilities; root cause noted
- **NO-USDA**: fixture failed to export at the suite resolution; no artifact
  to review

Per-fixture priors are derived from each fixture's `report.json`
(prim_count, kind breakdown). Viewer screenshots used the local in-flight
viewer at `http://127.0.0.1:8842/...`. After this pass the live tailnet URL
reflects the same code only after a push.

## Acceptance set (held in branch baseline)

| Fixture | Prim breakdown | Status | Notes |
|---|---|---|---|
| zaqxhna15w | 268 explicit_surface | IMPROVED | Boundary refinement smooths constraint edges across the dense surface field. |
| ghnr7txz47 | 351 surf + 145 ineq + 49 curves + 72 mesh | IMPROVED | Curves now tubed; surface fins refined. |
| k0fbxxwkqf | 79 surf + 85 ineq + 10 mesh | IMPROVED | Surface boundaries smoother. |
| vyp9ogyimt | 553 inequality_region | OK | No curves, no explicit surfaces; identical to baseline. |
| yuqwjsfvsc | 341 inequality_region | OK | Same — regression-safe baseline. |

## Student fixtures (S2-01 → S2-10)

| Fixture | Prim breakdown | Status | Notes |
|---|---|---|---|
| S2-01 Group A | 83 surf + 6 ineq | IMPROVED | Many parabolic-cap surfaces; boundary refinement smooths the rims. |
| S2-01 Group B | 1 surf + 114 mesh | OK | Mesh-only; no change. |
| S2-01 Group C | 4 surf + 1 imp + 8 ineq | IMPROVED | Surface fins refined. |
| S2-01 Group D | 5 ineq + 16 curves | IMPROVED | Curves tubed (tower-like). |
| S2-01 Group E | 9 surf + 14 ineq | IMPROVED | Surface fins refined. |
| S2-01 Group F | 9 surf + 1 ineq | IMPROVED | Surface fins refined. |
| S2-01 Group G | 17 surf + 2 imp + 53 ineq + 25 curves + 32 mesh | IMPROVED | Both fixes apply. |
| S2-02 Group A | 9 surf + 9 imp + 47 ineq | IMPROVED | Surfaces refined. |
| S2-02 Group B | 4 surf + 8 ineq + 8 mesh | IMPROVED | Surfaces refined. |
| S2-02 Group C | 124 ineq | OK | Inequality-only; identical. |
| S2-02 Group D | 3 surf + 60 ineq | IMPROVED (minor) | Few surfaces; mostly inequality. |
| S2-02 Group E | 4 imp + 49 ineq | OK | Implicit + inequality only. |
| S2-02 Group F | 58 surf + 15 ineq | IMPROVED | Many surfaces refined. |
| S2-02 Group G | 1 surf + 9 ineq | IMPROVED (minor) | One surface refined. |
| S2-03 Group A | 60 surf + 47 ineq | IMPROVED | Many surfaces refined. |
| S2-03 Group B | 9 surf + 3 ineq | **FIXED** | Primary target — fin artifacts repaired. |
| S2-03 Group C | 83 surf + 39 ineq | IMPROVED | Many surfaces refined. |
| S2-03 Group D | 28 surf + 148 imp + 28 ineq | IMPROVED | Surface portion refined. |
| S2-03 Group E | 103 ineq | OK | Inequality-only; identical. |
| S2-03 Group F | 41 curves + 11 surf | IMPROVED | Tower-like edge tubes now solid. |
| S2-04 Group A | 40 parametric_surface | OK | Parametric surfaces unaffected by either fix. |
| S2-04 Group B | 14 curves + 100 parametric_surface | IMPROVED | Curves tubed. |
| S2-04 Group C | 6 imp + 13 ineq | OK | No curves/explicit_surface. |
| S2-04 Group D | 6 surf + 14 ineq | IMPROVED | Surface fins refined. |
| S2-04 Group E | 8 imp + 1 ineq + 9 mesh | OK | No curves/explicit_surface. |
| S2-04 Group F | 62 surf + 4 curves + 41 parametric_surface | IMPROVED | Both fixes apply. |
| S2-04 Group G | 15 surf + 24 imp | IMPROVED | Surface fins refined. |
| S2-05 Group A | 2 ineq | OK | Trivial fixture. |
| S2-05 Group B | 37 ineq | OK | Inequality-only. |
| S2-05 Group C | 24 surf + 6 ineq | IMPROVED | Surface fins refined. |
| S2-05 Group D | 125 curves + 25 parametric_surface | **FIXED** | Primary target — Eiffel-tower wireframe fixed. |
| S2-05 Group E | 64 ineq | OK | Inequality-only. |
| S2-05 Group F | 1 surf + 5 ineq + 4 mesh | IMPROVED (minor) | Tiny surface refined. |
| S2-06 Group A | 6 surf + 468 ineq | IMPROVED (minor) | Few surfaces among many inequality regions. |
| S2-06 Group B | 196 ineq | OK | Inequality-only. |
| S2-06 Group C | 14 surf + 27 ineq | IMPROVED | Surface fins refined. |
| S2-06 Group D | 52 surf | IMPROVED | Surfaces refined. |
| S2-06 Group E | 79 surf + 2 imp + 326 ineq | IMPROVED | Surfaces refined. |
| S2-06 Group F | 8 surf + 42 ineq | IMPROVED | Surfaces refined. |
| S2-06 Group G | 49 ineq | OK | Inequality-only. |
| S2-07 Group A | 25 surf + 24 mesh | IMPROVED | Surfaces refined. |
| S2-07 Group B | 59 ineq | OK | Inequality-only. |
| S2-07 Group C | 10 surf + 9 ineq + 4 mesh | IMPROVED | Surfaces refined. |
| S2-07 Group D | 34 surf + 2 ineq | IMPROVED | Surfaces refined. |
| S2-07 Group E | 15 ineq | OK | Inequality-only. |
| S2-07 Group F | 36 ineq | OK | Inequality-only. |
| S2-08 Group A | 88 surf + 1 ineq + 40 curves | IMPROVED | Both fixes apply. |
| S2-08 Group B | 4 imp + 12 ineq | OK | No curves/explicit_surface. |
| S2-08 Group C | 12 ineq | OK | Inequality-only. |
| S2-08 Group D | 45 imp + 16 ineq | OK | No curves/explicit_surface. |
| S2-08 Group E | 9 surf + 29 imp | IMPROVED | Surfaces refined. |
| S2-08 Group G | 1208 curves + 2 imp + 7 ineq | NO-USDA | Existing failure: oversized curve count exceeds suite limits. Pre-existing condition; not addressed in this pass. |
| S2-09 Group A | 1 surf + 20 ineq | IMPROVED (minor) | One surface refined. |
| S2-09 Group B | 10 imp + 42 ineq | OK | No curves/explicit_surface. |
| S2-09 Group C | 25 surf + 47 imp + 2 mesh | IMPROVED | Surfaces refined. |
| S2-09 Group D | 77 surf + 1 ineq | IMPROVED | Many surfaces refined. |
| S2-09 Group E | 4 surf + 6 imp + 12 ineq | IMPROVED | Surfaces refined. |
| S2-09 Group F | 1 imp + 26 ineq | OK / **REGRESSION GUARD HELD** | No curves, no explicit_surface; pixel-identical. |
| S2-09 Group G | 80 ineq | OK | Inequality-only. |
| S2-10 Group A | 3 surf + 24 imp + 5 ineq | IMPROVED (minor) | Few surfaces. |
| S2-10 Group B | 66 surf + 49 ineq | IMPROVED | Surfaces refined. |
| S2-10 Group C | 3 ineq | OK | Inequality-only. |
| S2-10 Group D | 12 surf + 8 imp + 1 ineq | IMPROVED | Surfaces refined. |
| S2-10 Group E | 121 surf + 128 mesh | IMPROVED | Many surfaces refined. |
| S2-10 Group F | 85 ineq | OK | Inequality-only. |
| S2-10 Group G | 1 surf + 1 imp + 43 ineq | IMPROVED (minor) | One surface refined. |

## Remaining blockers

- **S2-08 Group G** is a pre-existing failure: 1208 parametric_curves
  exceed what the suite produces an artifact for. Not addressed in this
  pass; needs separate triage of the curve cap or split-fixture handling.
- **Parametric surfaces** (`parametric_surface`) get neither curve-tubing
  nor explicit_surface boundary refinement — they use their own
  `tessellate/parametric.py` path. Where the figure relies on a clipped
  parametric surface (e.g. some S2-04 fixtures), the same kind of fin
  artifact can persist. Out of scope for this pass; flagged for future
  work alongside `implicit_surface` quality improvements.
- **Implicit-surface-only fixtures** (S2-08 Group D, S2-09 Group B, etc.)
  are unchanged and were not regressed. They follow `tessellate/implicit.py`
  and were not in scope.
