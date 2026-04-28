# S2-01 Group C Assessment

- Target: `[4B] 3D Diagram - S2-01 Group C.json`
- Desmos: `https://www.desmos.com/3d/upbjmsjpzq`
- Evidence: local before/after contact-sheet projections only; live Desmos/viewer capture failed in this environment.
- Before: `15 prims / 4 unsupported / 18 classified / 19 renderable / valid true / partial`.
- After: `27 prims / 0 unsupported / 27 classified / 27 renderable / valid true / success`.
- Added geometry in the after projection:
  - expression `28`: disjoint `abs(x)` side shell around the small gray structure
  - expressions `40_0..40_4` and `42_0..42_4`: repeated green tube posts from `n=[2,3,4,5,6]`
  - expression `47`: four bounded sheets from `abs(abs(x)-2.5)=0.3`
- Guards: S2-08 Group E remains `87 prims / 0 unsupported`; S2-09 Group F remains `27 prims / 0 unsupported`.
