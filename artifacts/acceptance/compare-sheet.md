# desmos2usd acceptance manual compare sheet

Manual compare scaffold generated from the five frozen required Desmos 3D samples.
This sheet links each real Desmos sample to local acceptance artifacts for human side-by-side review.
Frozen view metadata is read from the in-repo required sample states and is provided only to set up the manual comparison.
It is not proof of visual parity, and it does not claim the USDA/PPM render matches Desmos.

| sample | Desmos 3D sample | viewer USDA | local USDA | local PPM | report | artifact presence | frozen Desmos view | geometry diagnostics | report renderables | frozen fixture renderables | report count check | valid | complete | prims | unsupported | unsupported triage | unsupported evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |
| zaqxhna15w | [https://www.desmos.com/3d/zaqxhna15w](https://www.desmos.com/3d/zaqxhna15w) | [open USDA](../../viewer/?usda=..%2Fartifacts%2Facceptance%2Fzaqxhna15w.usda) | [zaqxhna15w.usda](zaqxhna15w.usda) | [zaqxhna15w.ppm](zaqxhna15w.ppm) | [zaqxhna15w.report.json](zaqxhna15w.report.json) | USDA present<br>PPM present<br>report present | viewport x[-152.132, 152.132] y[-152.132, 152.132] z[-152.132, 152.132]<br>worldRotation3D [0.82576, -0.529959, 0.19304, 0.516046, 0.848023, 0.120638, -0.227636, 0, 0.973746]<br>axis3D [-0.529959, 0.848023, 0]<br>threeDMode=true; showPlane3D=false | 0 viewport outliers | 268 | 268 | matches frozen fixture | true | true | 268 | 0 | 0 contradictory source, 0 residual limitation, 0 untriaged | none |
| ghnr7txz47 | [https://www.desmos.com/3d/ghnr7txz47](https://www.desmos.com/3d/ghnr7txz47) | [open USDA](../../viewer/?usda=..%2Fartifacts%2Facceptance%2Fghnr7txz47.usda) | [ghnr7txz47.usda](ghnr7txz47.usda) | [ghnr7txz47.ppm](ghnr7txz47.ppm) | [ghnr7txz47.report.json](ghnr7txz47.report.json) | USDA present<br>PPM present<br>report present | viewport x[-63.5658, 62.0295] y[-63.1685, 62.4268] z[-42.9128, 82.6826]<br>worldRotation3D [-0.684085, 0.685556, -0.249078, -0.644184, -0.72802, -0.23455, -0.342131, 0, 0.939652]<br>axis3D [0, 0, -1]<br>threeDMode=true | 0 viewport outliers | 617 | 617 | matches frozen fixture | true | true | 617 | 0 | 0 contradictory source, 0 residual limitation, 0 untriaged | none |
| yuqwjsfvsc | [https://www.desmos.com/3d/yuqwjsfvsc](https://www.desmos.com/3d/yuqwjsfvsc) | [open USDA](../../viewer/?usda=..%2Fartifacts%2Facceptance%2Fyuqwjsfvsc.usda) | [yuqwjsfvsc.usda](yuqwjsfvsc.usda) | [yuqwjsfvsc.ppm](yuqwjsfvsc.ppm) | [yuqwjsfvsc.report.json](yuqwjsfvsc.report.json) | USDA present<br>PPM present<br>report present | viewport x[-113.523, 113.523] y[-113.523, 113.523] z[-113.523, 113.523]<br>worldRotation3D [-0.51328, -0.83147, -0.212608, 0.768178, -0.55557, 0.31819, -0.382683, 0, 0.92388]<br>axis3D [0, 0, -1]<br>threeDMode=true | 0 viewport outliers | 341 | 341 | matches frozen fixture | true | true | 341 | 0 | 0 contradictory source, 0 residual limitation, 0 untriaged | none |
| vyp9ogyimt | [https://www.desmos.com/3d/vyp9ogyimt](https://www.desmos.com/3d/vyp9ogyimt) | [open USDA](../../viewer/?usda=..%2Fartifacts%2Facceptance%2Fvyp9ogyimt.usda) | [vyp9ogyimt.usda](vyp9ogyimt.usda) | [vyp9ogyimt.ppm](vyp9ogyimt.ppm) | [vyp9ogyimt.report.json](vyp9ogyimt.report.json) | USDA present<br>PPM present<br>report present | viewport x[-510, 510] y[-510, 510] z[-510, 510]<br>worldRotation3D [-0.624357, 0.777806, -0.072079, -0.772675, -0.628504, -0.0892015, -0.114683, 0, 0.993402]<br>axis3D [0, 0, 1]<br>threeDMode=true | 0 viewport outliers | 558 | 558 | matches frozen fixture | true | false | 553 | 5 | 5 contradictory source, 0 residual limitation, 0 untriaged | 5 contradiction details: [details](#unsupported-evidence-vyp9ogyimt) |
| k0fbxxwkqf | [https://www.desmos.com/3d/k0fbxxwkqf](https://www.desmos.com/3d/k0fbxxwkqf) | [open USDA](../../viewer/?usda=..%2Fartifacts%2Facceptance%2Fk0fbxxwkqf.usda) | [k0fbxxwkqf.usda](k0fbxxwkqf.usda) | [k0fbxxwkqf.ppm](k0fbxxwkqf.ppm) | [k0fbxxwkqf.report.json](k0fbxxwkqf.report.json) | USDA present<br>PPM present<br>report present | viewport x[-139.387, 139.387] y[-139.387, 139.387] z[-139.387, 139.387]<br>worldRotation3D [0, 1, 0, -0.927897, 0, -0.372837, -0.372837, 0, 0.927897]<br>axis3D [-1, 0, 0]<br>threeDMode=true | 11 viewport outliers; strongest expr `3`: x low 85.613, high 85.613 (margin 27.8774): [details](#geometry-diagnostics-k0fbxxwkqf) | 174 | 174 | matches frozen fixture | true | true | 174 | 0 | 0 contradictory source, 0 residual limitation, 0 untriaged | none |

## Geometry Diagnostics Details

<a id="geometry-diagnostics-k0fbxxwkqf"></a>
### k0fbxxwkqf

- outlier rule: prim bbox outside frozen source viewport by more than 10% of that axis span
- frozen source viewport bbox: min [-139.387, -139.387, -139.387], max [139.387, 139.387, 139.387], span [278.774, 278.774, 278.774]
- report global bbox: min [-225, -23, -139.387], max [225, 23, 139.387], span [450, 46, 278.774]
- outlier axis/direction summary: x low 7 (max 85.613), high 7 (max 85.613)
- expr `3` (`expr_0001__3`, explicit_surface): max overshoot 85.613; x low 85.613, high 85.613 (margin 27.8774)
- expr `10` (`expr_0002__10`, explicit_surface): max overshoot 85.613; x low 85.613, high 85.613 (margin 27.8774)
- expr `13` (`expr_0003__13`, inequality_region): max overshoot 85.613; x low 85.613, high 85.613 (margin 27.8774)
- expr `46` (`expr_0013__46`, explicit_surface): max overshoot 85.613; x low 85.613 (margin 27.8774)
- expr `79` (`expr_0017__79`, explicit_surface): max overshoot 85.613; x low 85.613 (margin 27.8774)
- expr `80` (`expr_0021__80`, explicit_surface): max overshoot 85.613; x high 85.613 (margin 27.8774)
- expr `81` (`expr_0025__81`, explicit_surface): max overshoot 85.613; x high 85.613 (margin 27.8774)
- expr `294` (`expr_0142__294`, explicit_surface): max overshoot 37.613; x high 37.613 (margin 27.8774)
- expr `298` (`expr_0146__298`, explicit_surface): max overshoot 37.613; x high 37.613 (margin 27.8774)
- expr `312` (`expr_0260__312`, explicit_surface): max overshoot 37.613; x low 37.613 (margin 27.8774)
- expr `323` (`expr_0264__323`, explicit_surface): max overshoot 37.613; x low 37.613 (margin 27.8774)

## Unsupported Evidence Details

<a id="unsupported-evidence-vyp9ogyimt"></a>
### vyp9ogyimt

- expr `223`: axis y contradiction: lower bound 17 from `17\le y\le20` is above upper bound -17 from `-20\le y\le-17`
- expr `360`: axis y contradiction: lower bound 17 from `17\le y\le20` is above upper bound -17 from `-20\le y\le-17`
- expr `293`: axis x contradiction: lower bound 391 from `391\le x\le388` is above upper bound 388 from `391\le x\le388`
- expr `181`: axis x contradiction: lower bound 490 from `490\le x\le-487` is above upper bound -487 from `490\le x\le-487`
- expr `273`: axis x contradiction: lower bound 501 from `501\le x\le498` is above upper bound 498 from `501\le x\le498`

Review notes:

- Use this artifact to open the Desmos source and the local USDA/PPM artifacts for manual comparison.
- Serve the repository root for viewer links: run `python3 -m http.server 8765` from the repo root and open `http://localhost:8765/artifacts/acceptance/compare-sheet.md`. The relative `usda` links rely on `viewer/` and the generated artifacts both being served from that repo-root layout.
- Re-check artifact freshness without regenerating this sheet: run `PYTHONPATH=src python3 -m desmos2usd.validate.sample_suite --out artifacts/acceptance --verify-artifacts`; fix any `missing` item before manual comparison.
- The frozen view cell records Desmos viewport and world rotation values from `fixtures/states/*.json`; it is setup context, not a rendering verdict.
- Geometry diagnostics are copied from existing report `geometry_diagnostics` fields and flag stored prim bounding boxes outside the frozen viewport margin; they are manual-diagnosis aids, not visual parity verdicts.
- The frozen fixture renderable count is recomputed from `fixtures/states/*.json` with the current classifier. A mismatch is a stale-report consistency signal, not proof of visual mismatch.
- Unsupported evidence is copied from report `source_triage` entries and is limited to the unsupported rows already present in the required sample reports.
- `valid` and `complete` are export/validation signals from the generated reports, not visual parity verdicts.
- The row set is intentionally limited to the frozen required samples; extra report files are ignored.
