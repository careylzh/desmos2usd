# S2-01 Group A Ralph Tranche Assessment

- Fixture: `[4B] 3D Diagram - S2-01 Group A.json`
- Desmos URL: `https://www.desmos.com/3d/cvggvbbe73`
- Fix family: affine-clipped explicit surface domain inference

## Evidence Status

Live Desmos and live viewer screenshots are blocked in this environment. Playwright and Chrome DevTools both returned `user cancelled MCP tool call`; Tailscale route checks failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.

Do not treat this as a live visual parity claim. The evidence here is deterministic local projection only.

## Structural Result

- Before projection from HEAD code: `90 prims / 118 unsupported / valid true / partial`.
- After projection from current code: `208 prims / 0 unsupported / valid true / success`.
- Tracked artifact after regeneration: `208 prims / 0 unsupported / valid true / success / usdchecker returncode 0`.
- S2-08 Group E guard remains `87 prims / 0 unsupported / success`.
- S2-09 Group F guard remains `27 prims / 0 unsupported / success`.

The after projection removes the old broad-domain sampling misses and fills in the tower/roof diagonal explicit-surface family that was absent or poorly sampled before.
