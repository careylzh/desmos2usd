# S2-02 Group F Chained 72 Assessment

- Target: `[4B] 3D Diagram - S2-02 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/1zpiejy9c9`
- Fix family: contradictory constant bounds inside a long chained inequality.

## Diagnosis

The remaining nine unsupported expressions were list expansions of:

`(y-c)^2 <= 0.00250 <= z <= 13.2-0.03 <= x <= 2.03`

Desmos chained-comparison semantics make this equivalent to adjacent comparisons. The tail `13.17 <= x <= 2.03` is contradictory, so the region has no points and should not fall through to sampled voxel export.

## Evidence

Live browser capture was blocked by the MCP host, and the local/Tailscale viewer routes were unavailable from this sandbox. See `capture_results.json` for exact command/tool failures.

Local deterministic projection evidence:

- `S2-02_Group_F_projection_before.png`
- `S2-02_Group_F_projection_after.png`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.png`

## Metrics

- Before: `197 prims / 9 unsupported / 206 classified / valid true / complete false`
- After: `206 prims / 0 unsupported / 206 classified / valid true / complete true`
- Guard S2-08 Group E: `87 prims / 0 unsupported / valid true`
- Guard S2-09 Group F: `27 prims / 0 unsupported / valid true`

The nine new S2-02F prims are valid empty mesh prims for the empty `72_*` regions.
