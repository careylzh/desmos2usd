# S2-08 Group G Flat-Disk Tranche Assessment

Target: S2-08 Group G (`https://www.desmos.com/3d/24vpv4pfwh`).

Live Desmos and live viewer screenshots are blocked in this environment. Playwright and Chrome DevTools both returned `user cancelled MCP tool call`; Tailscale route checks also failed DNS resolution. This evidence therefore supports only structural/local projection progress, not live visual parity.

Local deterministic evidence:
- `S2-08_Group_G_tracked_report_before.json`: tracked stale baseline, 1236 prims / 23 unsupported.
- `S2-08_Group_G_projection_before.png`: fresh pre-disk local projection, 1833 prims / 2 unsupported (`800`, `801`).
- `S2-08_Group_G_projection_after.png`: after projection, 1835 prims / 0 unsupported.
- `S2-08_Group_E_projection_guard_after.png`: guard projection, 87 prims / 0 unsupported.
- `S2-09_Group_F_projection_guard_after.png`: guard projection, 27 prims / 0 unsupported.

Largest fixed mismatch: strict circular inequalities locked to a constant z plane, such as `x^2+y^2<2.5^2 {z=146.5}`, were treated as zero-height extrusions and fell through to sampled cells. The circular tessellator now emits a single flat disk mesh for caps-enabled circular inequalities whose extrusion axis has equal low/high bounds.
