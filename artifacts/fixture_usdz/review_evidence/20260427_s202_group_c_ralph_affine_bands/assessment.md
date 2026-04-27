# S2-02 Group C Ralph Tranche

- Target: `[4B] 3D Diagram - S2-02 Group C.json`
- Desmos URL: `https://www.desmos.com/3d/sqn7vxcm4n`
- General fix: nested Desmos restrictions such as `quadratic > 1 {2.7 > y > 2}` are flattened into separate predicates instead of parsing the inner brace as multiplication.
- Tracked baseline before this tranche: `133 prims / 36 unsupported / partial`.
- Fresh local pre-edit projection baseline: `149 prims / 20 unsupported / partial`.
- After this tranche: `169 prims / 0 unsupported / success`.
- Guard fixtures: S2-08 Group E remains `87 prims / 0 unsupported`; S2-09 Group F remains `27 prims / 0 unsupported`.
- Live visual gate: blocked. Browser and route failures are recorded in `capture_results.json`; do not claim live Desmos/viewer parity from this evidence.
- Local projection observation: the after projection adds the missing orange curved/banded side geometry around the lower central structure while preserving the tower, dome, top-down grid, and guard fixture success state.
