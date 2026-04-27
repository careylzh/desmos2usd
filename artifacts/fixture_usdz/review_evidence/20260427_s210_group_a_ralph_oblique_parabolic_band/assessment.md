# S2-10 Group A Oblique Parabolic Band Assessment

- Target: `[4B] 3D Diagram - S2-10 Group A.json`
- Desmos URL: `https://www.desmos.com/3d/g53xte50e7`
- Focus: expression `41`, `-0.7y^{2}+2.3<z<-0.7y^{2}+2.8 {-1<2.8x+1.25z-8.4<0}{z>0}`

## Result

The exporter now handles function-band inequality regions whose remaining axis is bounded by affine predicates. S2-10A improved from `39 prims / 1 unsupported / partial` to `40 prims / 0 unsupported / success`.

No fixture names, expression ids, or one-off S2-10 constants are encoded in the fix.

## Evidence

Browser capture is still blocked in this environment: both Playwright and Chrome DevTools returned `user cancelled MCP tool call` for Desmos and viewer navigation. The Tailscale review host also failed DNS resolution with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.

The evidence here is therefore deterministic local projection only, not live Desmos/viewer parity. The after projection adds the missing right-side gray oblique parabolic band corresponding to expression `41`; the existing opposite/adjacent bands are regenerated through the same general path.
