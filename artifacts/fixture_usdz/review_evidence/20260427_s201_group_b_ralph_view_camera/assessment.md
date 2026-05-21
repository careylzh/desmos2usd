# S2-01 Group B viewer-camera tranche

- Target: S2-01 Group B, https://www.desmos.com/3d/27v0xuv64m
- Live Desmos and live viewer capture are blocked in this environment by MCP cancellation, local server bind failure, headless Chrome failure, and Tailscale DNS failure; no live parity claim is made.
- Structural diagnosis: the viewer interpreted `desmos:worldRotation3D` by columns with sign flips. The exporter and diagnostics store Desmos row-major camera metadata where row 0 is screen-right, row 1 is screen-up, and row 2 is camera depth. This can make a complete S2-01B model open from the wrong saved view.
- Fix: the static viewer now loads a small camera math module and uses the rows directly as the saved Desmos camera basis.
- Geometry metrics are unchanged: S2-01B remains 143 prims / 0 unsupported; S2-08E and S2-09F guards remain success.
