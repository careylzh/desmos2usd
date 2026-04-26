# Pass 5 Top Partials Evidence

Target: S2-06 Group E sqrt-domain explicit surface family.

## Result

- S2-06 Group E improved from 321 unsupported / 415 prims to 57 unsupported / 679 prims.
- The fixed family is Desmos restriction/domain semantics: undefined explicit-surface samples and undefined restriction samples are treated as outside the sampled domain instead of aborting the whole surface.
- S2-08 Group E and S2-09 Group F remain success in the regenerated summary.

## Visual Evidence

- `S2-06_Group_E_projection_pass5.png` and `.ppm`: deterministic XY/XZ/YZ projection from regenerated geometry.
- `S2-08_Group_E_projection_guard_pass5.png` and `.ppm`: deterministic guard projection.
- `S2-09_Group_F_projection_guard_pass5.png` and `.ppm`: deterministic guard projection.

Live browser screenshots were attempted but blocked in this sandbox:

- local `python3 -m http.server`: `PermissionError: [Errno 1] Operation not permitted`
- Playwright MCP: `user cancelled MCP tool call`
- Chrome DevTools MCP: `user cancelled MCP tool call`

The corresponding live viewer URLs are recorded in `capture-results.json` for reviewer recapture.

## Remaining S2-06E Unsupported

57 unsupported remain:

- 46 explicit surfaces, mostly the same ellipse/sqrt family where generated geometry still fails predicate validation at far out-of-domain samples rather than producing accepted faces.
- 11 inequality regions that still do not resolve to sampled cells.

Next exact target: make explicit-surface max-resolution no-face cases report as clipped empty domains or refine the solved-axis predicate boundary so the remaining `146_*` out-of-domain strips do not emit invalid validation points.
