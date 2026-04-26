# CSV URL to Fixture Comparison

This report maps each original CSV Desmos URL to its frozen fixture state and current local USDZ sweep evidence.
It does not claim live Desmos visual parity.

## Sources

- CSV: `/Users/chek/.openclaw/workspace/tmp/desmos2usd-ralph-control/desmos_urls_latest.csv`
- Frozen fixture states: `fixtures/states`
- Sweep summary: `artifacts/fixture_usdz/summary.json`
- USDZ artifacts: `artifacts/fixture_usdz`
- Live Desmos/browser check: unavailable; curl -I --max-time 10 https://www.desmos.com/3d/cvggvbbe73 failed with: curl: (6) Could not resolve host: www.desmos.com

## Aggregate Evidence

| Metric | Value |
| --- | ---: |
| CSV rows | 66 |
| Frozen fixture states present | 66/66 |
| Sweep reports mapped | 66/66 |
| Sweep status counts | success 16, partial 50 |
| USDZ artifacts present | 66/66 |
| Unsupported expressions | 1529 |
| Classified expressions | 6942 |
| Exported prims | 5823 |
| Unsupported kind counts | inequality_region 558, explicit_surface 549, classification 401, definition 9, triangle_mesh 8, parametric_surface 4 |

## Prioritized Remaining Rows

### Highest Unsupported Counts

| Fixture | URL hash | Status | Unsupported | Prims | Unsupported kinds | Notes |
| --- | --- | --- | ---: | ---: | --- | --- |
| [4B] 3D Diagram - S2-06 Group E.json | cg2sd6h1ws | partial | 329 | 407 | explicit_surface 318, inequality_region 11 | partial export; 329 unsupported; explicit_surface 318, inequality_region 11; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-03 Group D.json | zvasa1wcgo | partial | 122 | 204 | classification 55, explicit_surface 52, inequality_region 15 | partial export; 122 unsupported; classification 55, explicit_surface 52, inequality_region 15; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-01 Group A.json | cvggvbbe73 | partial | 119 | 89 | explicit_surface 115, inequality_region 4 | partial export; 119 unsupported; explicit_surface 115, inequality_region 4; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-03 Group E.json | sqkhp7wnx6 | partial | 97 | 99 | inequality_region 78, triangle_mesh 8, classification 6 | partial export; 97 unsupported; inequality_region 78, triangle_mesh 8, classification 6; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-10 Group F.json | tejhfrm34m | partial | 82 | 85 | inequality_region 82 | partial export; 82 unsupported; inequality_region 82; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-08 Group E.json | g59jqe6nxy | partial | 69 | 14 | classification 66, inequality_region 3 | partial export; 69 unsupported; classification 66, inequality_region 3; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-07 Group F.json | jkj1z8t8pf | partial | 69 | 36 | classification 67, definition 1, inequality_region 1 | partial export; 69 unsupported; classification 67, definition 1, inequality_region 1; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-02 Group C.json | sqn7vxcm4n | partial | 62 | 107 | inequality_region 42, classification 20 | partial export; 62 unsupported; inequality_region 42, classification 20; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-02 Group F.json | 1zpiejy9c9 | partial | 52 | 62 | explicit_surface 38, inequality_region 11, classification 3 | partial export; 52 unsupported; explicit_surface 38, inequality_region 11, classification 3; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-06 Group F.json | wd6jilpijy | partial | 44 | 50 | inequality_region 42, classification 2 | partial export; 44 unsupported; inequality_region 42, classification 2; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-06 Group A.json | lvj5ymlrba | partial | 43 | 474 | inequality_region 41, explicit_surface 2 | partial export; 43 unsupported; inequality_region 41, explicit_surface 2; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-08 Group G.json | 24vpv4pfwh | partial | 42 | 1217 | classification 21, inequality_region 21 | partial export; 42 unsupported; classification 21, inequality_region 21; needs live Desmos visual verification |

### Lowest Prim Counts Among Partial Rows

| Fixture | URL hash | Status | Unsupported | Prims | Unsupported kinds | Notes |
| --- | --- | --- | ---: | ---: | --- | --- |
| [4B] 3D Diagram - S2-05 Group A.json | ltogun0zlk | partial | 3 | 2 | inequality_region 3 | partial export; 3 unsupported; inequality_region 3; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-09 Group F.json | umjxv6ahck | partial | 24 | 3 | inequality_region 23, classification 1 | partial export; 24 unsupported; inequality_region 23, classification 1; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-10 Group C.json | 151jsdn8xs | partial | 5 | 3 | inequality_region 4, classification 1 | partial export; 5 unsupported; inequality_region 4, classification 1; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-05 Group F.json | kikxd6qykj | partial | 6 | 10 | inequality_region 6 | partial export; 6 unsupported; inequality_region 6; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-01 Group C.json | upbjmsjpzq | partial | 7 | 12 | inequality_region 6, classification 1 | partial export; 7 unsupported; inequality_region 6, classification 1; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-08 Group C.json | xrsgrdip5y | partial | 1 | 12 | inequality_region 1 | partial export; 1 unsupported; inequality_region 1; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-08 Group E.json | g59jqe6nxy | partial | 69 | 14 | classification 66, inequality_region 3 | partial export; 69 unsupported; classification 66, inequality_region 3; needs live Desmos visual verification |
| [4B] 3D Diagram - S2-07 Group E.json | gpskd1f59i | partial | 20 | 15 | inequality_region 19, classification 1 | partial export; 20 unsupported; inequality_region 19, classification 1; needs live Desmos visual verification |

## All CSV Rows

| # | Source URL | Fixture | Frozen state | Sweep | USDZ | Unsupported | Classified | Prims | Notes |
| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| 1 | https://www.desmos.com/3d/cvggvbbe73 | [4B] 3D Diagram - S2-01 Group A.json | yes | partial | yes | 119 | 208 | 89 | partial export; 119 unsupported; explicit_surface 115, inequality_region 4; needs live Desmos visual verification |
| 2 | https://www.desmos.com/3d/27v0xuv64m | [4B] 3D Diagram - S2-01 Group B.json | yes | partial | yes | 27 | 116 | 115 | partial export; 27 unsupported; classification 26, inequality_region 1; needs live Desmos visual verification |
| 3 | https://www.desmos.com/3d/upbjmsjpzq | [4B] 3D Diagram - S2-01 Group C.json | yes | partial | yes | 7 | 18 | 12 | partial export; 7 unsupported; inequality_region 6, classification 1; needs live Desmos visual verification |
| 4 | https://www.desmos.com/3d/z68jgsnw24 | [4B] 3D Diagram - S2-01 Group D.json | yes | success | yes | 0 | 21 | 21 | structural success; live visual parity unverified |
| 5 | https://www.desmos.com/3d/nzokib2plm | [4B] 3D Diagram - S2-01 Group E.json | yes | partial | yes | 20 | 43 | 23 | partial export; 20 unsupported; inequality_region 20; needs live Desmos visual verification |
| 6 | https://www.desmos.com/3d/sbrpw8amwn | [4B] 3D Diagram - S2-01 Group F.json | yes | success | yes | 0 | 10 | 10 | structural success; live visual parity unverified |
| 7 | https://www.desmos.com/3d/jbmqctn5ic | [4B] 3D Diagram - S2-01 Group G.json | yes | success | yes | 0 | 129 | 129 | structural success; live visual parity unverified |
| 8 | https://www.desmos.com/3d/yyhld5wuie | [4B] 3D Diagram - S2-02 Group A.json | yes | partial | yes | 3 | 65 | 65 | partial export; 3 unsupported; classification 3; needs live Desmos visual verification |
| 9 | https://www.desmos.com/3d/fpj0hokhfc | [4B] 3D Diagram - S2-02 Group B.json | yes | partial | yes | 2 | 21 | 20 | partial export; 2 unsupported; classification 1, inequality_region 1; needs live Desmos visual verification |
| 10 | https://www.desmos.com/3d/sqn7vxcm4n | [4B] 3D Diagram - S2-02 Group C.json | yes | partial | yes | 62 | 149 | 107 | partial export; 62 unsupported; inequality_region 42, classification 20; needs live Desmos visual verification |
| 11 | https://www.desmos.com/3d/fpwtzvfima | [4B] 3D Diagram - S2-02 Group D.json | yes | success | yes | 0 | 63 | 63 | structural success; live visual parity unverified |
| 12 | https://www.desmos.com/3d/6ltj6kjhh9 | [4B] 3D Diagram - S2-02 Group E.json | yes | partial | yes | 6 | 54 | 53 | partial export; 6 unsupported; classification 5, inequality_region 1; needs live Desmos visual verification |
| 13 | https://www.desmos.com/3d/1zpiejy9c9 | [4B] 3D Diagram - S2-02 Group F.json | yes | partial | yes | 52 | 111 | 62 | partial export; 52 unsupported; explicit_surface 38, inequality_region 11, classification 3; needs live Desmos visual verification |
| 14 | https://www.desmos.com/3d/vf0bjbwmve | [4B] 3D Diagram - S2-02 Group G.json | yes | success | yes | 0 | 10 | 10 | structural success; live visual parity unverified |
| 15 | https://www.desmos.com/3d/8wt3h8gs1u | [4B] 3D Diagram - S2-03 Group A.json | yes | partial | yes | 5 | 112 | 107 | partial export; 5 unsupported; explicit_surface 5; needs live Desmos visual verification |
| 16 | https://www.desmos.com/3d/dstsug13q6 | [4B] 3D Diagram - S2-03 Group B.json | yes | success | yes | 0 | 12 | 12 | structural success; live visual parity unverified |
| 17 | https://www.desmos.com/3d/xyvxakzxdj | [4B] 3D Diagram - S2-03 Group C.json | yes | partial | yes | 9 | 131 | 122 | partial export; 9 unsupported; inequality_region 9; needs live Desmos visual verification |
| 18 | https://www.desmos.com/3d/zvasa1wcgo | [4B] 3D Diagram - S2-03 Group D.json | yes | partial | yes | 122 | 271 | 204 | partial export; 122 unsupported; classification 55, explicit_surface 52, inequality_region 15; needs live Desmos visual verification |
| 19 | https://www.desmos.com/3d/sqkhp7wnx6 | [4B] 3D Diagram - S2-03 Group E.json | yes | partial | yes | 97 | 185 | 99 | partial export; 97 unsupported; inequality_region 78, triangle_mesh 8, classification 6; needs live Desmos visual verification |
| 20 | https://www.desmos.com/3d/v9rkpmtkte | [4B] 3D Diagram - S2-03 Group F.json | yes | success | yes | 0 | 52 | 52 | structural success; live visual parity unverified |
| 21 | https://www.desmos.com/3d/ztbpwpfqyb | [4B] 3D Diagram - S2-04 Group A.json | yes | success | yes | 0 | 40 | 40 | structural success; live visual parity unverified |
| 22 | https://www.desmos.com/3d/rdh4sapm8y | [4B] 3D Diagram - S2-04 Group B.json | yes | success | yes | 0 | 114 | 114 | structural success; live visual parity unverified |
| 23 | https://www.desmos.com/3d/xh4pra7x5t | [4B] 3D Diagram - S2-04 Group C.json | yes | partial | yes | 7 | 20 | 15 | partial export; 7 unsupported; inequality_region 5, classification 2; needs live Desmos visual verification |
| 24 | https://www.desmos.com/3d/tp1uoi8wr3 | [4B] 3D Diagram - S2-04 Group D.json | yes | partial | yes | 1 | 20 | 20 | partial export; 1 unsupported; classification 1; needs live Desmos visual verification |
| 25 | https://www.desmos.com/3d/bkvhsygeva | [4B] 3D Diagram - S2-04 Group E.json | yes | success | yes | 0 | 18 | 18 | structural success; live visual parity unverified |
| 26 | https://www.desmos.com/3d/sq7mwuppve | [4B] 3D Diagram - S2-04 Group F.json | yes | partial | yes | 4 | 111 | 107 | partial export; 4 unsupported; parametric_surface 4; needs live Desmos visual verification |
| 27 | https://www.desmos.com/3d/ratctlkc9i | [4B] 3D Diagram - S2-04 Group G.json | yes | partial | yes | 41 | 52 | 39 | partial export; 41 unsupported; classification 25, explicit_surface 8, inequality_region 5; needs live Desmos visual verification |
| 28 | https://www.desmos.com/3d/ltogun0zlk | [4B] 3D Diagram - S2-05 Group A.json | yes | partial | yes | 3 | 5 | 2 | partial export; 3 unsupported; inequality_region 3; needs live Desmos visual verification |
| 29 | https://www.desmos.com/3d/0pqcfy5mm4 | [4B] 3D Diagram - S2-05 Group B.json | yes | partial | yes | 6 | 43 | 37 | partial export; 6 unsupported; inequality_region 6; needs live Desmos visual verification |
| 30 | https://www.desmos.com/3d/gwm96pxshz | [4B] 3D Diagram - S2-05 Group C.json | yes | success | yes | 0 | 30 | 30 | structural success; live visual parity unverified |
| 31 | https://www.desmos.com/3d/5jh9zwy75e | [4B] 3D Diagram - S2-05 Group D.json | yes | success | yes | 0 | 150 | 150 | structural success; live visual parity unverified |
| 32 | https://www.desmos.com/3d/ogadswpcsz | [4B] 3D Diagram - S2-05 Group E.json | yes | partial | yes | 2 | 66 | 64 | partial export; 2 unsupported; inequality_region 2; needs live Desmos visual verification |
| 33 | https://www.desmos.com/3d/kikxd6qykj | [4B] 3D Diagram - S2-05 Group F.json | yes | partial | yes | 6 | 16 | 10 | partial export; 6 unsupported; inequality_region 6; needs live Desmos visual verification |
| 34 | https://www.desmos.com/3d/lvj5ymlrba | [4B] 3D Diagram - S2-06 Group A.json | yes | partial | yes | 43 | 517 | 474 | partial export; 43 unsupported; inequality_region 41, explicit_surface 2; needs live Desmos visual verification |
| 35 | https://www.desmos.com/3d/7qad26nam5 | [4B] 3D Diagram - S2-06 Group B.json | yes | partial | yes | 31 | 196 | 192 | partial export; 31 unsupported; classification 27, inequality_region 4; needs live Desmos visual verification |
| 36 | https://www.desmos.com/3d/qzmi6yftoo | [4B] 3D Diagram - S2-06 Group C.json | yes | partial | yes | 3 | 44 | 41 | partial export; 3 unsupported; inequality_region 3; needs live Desmos visual verification |
| 37 | https://www.desmos.com/3d/qedmqiodp9 | [4B] 3D Diagram - S2-06 Group D.json | yes | success | yes | 0 | 52 | 52 | structural success; live visual parity unverified |
| 38 | https://www.desmos.com/3d/cg2sd6h1ws | [4B] 3D Diagram - S2-06 Group E.json | yes | partial | yes | 329 | 736 | 407 | partial export; 329 unsupported; explicit_surface 318, inequality_region 11; needs live Desmos visual verification |
| 39 | https://www.desmos.com/3d/wd6jilpijy | [4B] 3D Diagram - S2-06 Group F.json | yes | partial | yes | 44 | 92 | 50 | partial export; 44 unsupported; inequality_region 42, classification 2; needs live Desmos visual verification |
| 40 | https://www.desmos.com/3d/ooieibjrtn | [4B] 3D Diagram - S2-06 Group G.json | yes | success | yes | 0 | 49 | 49 | structural success; live visual parity unverified |
| 41 | https://www.desmos.com/3d/etaopz7dqp | [4B] 3D Diagram - S2-07 Group A.json | yes | success | yes | 0 | 49 | 49 | structural success; live visual parity unverified |
| 42 | https://www.desmos.com/3d/cslobql2iu | [4B] 3D Diagram - S2-07 Group C.json | yes | partial | yes | 3 | 23 | 23 | partial export; 3 unsupported; classification 3; needs live Desmos visual verification |
| 43 | https://www.desmos.com/3d/x76gox8jfv | [4B] 3D Diagram - S2-07 Group D.json | yes | partial | yes | 3 | 37 | 36 | partial export; 3 unsupported; classification 2, inequality_region 1; needs live Desmos visual verification |
| 44 | https://www.desmos.com/3d/gpskd1f59i | [4B] 3D Diagram - S2-07 Group E.json | yes | partial | yes | 20 | 34 | 15 | partial export; 20 unsupported; inequality_region 19, classification 1; needs live Desmos visual verification |
| 45 | https://www.desmos.com/3d/jkj1z8t8pf | [4B] 3D Diagram - S2-07 Group F.json | yes | partial | yes | 69 | 37 | 36 | partial export; 69 unsupported; classification 67, definition 1, inequality_region 1; needs live Desmos visual verification |
| 46 | https://www.desmos.com/3d/iotojm1ll4 | [4B] 3D Diagram - S2-08 Group A.json | yes | success | yes | 0 | 129 | 129 | structural success; live visual parity unverified |
| 47 | https://www.desmos.com/3d/9ie18aufkm | [4B] 3D Diagram - S2-08 Group B.json | yes | partial | yes | 2 | 18 | 16 | partial export; 2 unsupported; inequality_region 2; needs live Desmos visual verification |
| 48 | https://www.desmos.com/3d/xrsgrdip5y | [4B] 3D Diagram - S2-08 Group C.json | yes | partial | yes | 1 | 13 | 12 | partial export; 1 unsupported; inequality_region 1; needs live Desmos visual verification |
| 49 | https://www.desmos.com/3d/1fbxkhzguy | [4B] 3D Diagram - S2-08 Group D.json | yes | partial | yes | 2 | 63 | 61 | partial export; 2 unsupported; inequality_region 2; needs live Desmos visual verification |
| 50 | https://www.desmos.com/3d/g59jqe6nxy | [4B] 3D Diagram - S2-08 Group E.json | yes | partial | yes | 69 | 17 | 14 | partial export; 69 unsupported; classification 66, inequality_region 3; needs live Desmos visual verification |
| 51 | https://www.desmos.com/3d/24vpv4pfwh | [4B] 3D Diagram - S2-08 Group G.json | yes | partial | yes | 42 | 1238 | 1217 | partial export; 42 unsupported; classification 21, inequality_region 21; needs live Desmos visual verification |
| 52 | https://www.desmos.com/3d/s6vcgvu9e8 | [4B] 3D Diagram - S2-09 Group B.json | yes | partial | yes | 19 | 60 | 46 | partial export; 19 unsupported; inequality_region 14, classification 5; needs live Desmos visual verification |
| 53 | https://www.desmos.com/3d/zxjnvkynzf | [4B] 3D Diagram - S2-09 Group D.json | yes | partial | yes | 37 | 89 | 78 | partial export; 37 unsupported; classification 26, inequality_region 11; needs live Desmos visual verification |
| 54 | https://www.desmos.com/3d/ml3mebe7y5 | [4B] 3D Diagram - S2-09 Group E.json | yes | partial | yes | 13 | 25 | 22 | partial export; 13 unsupported; classification 10, explicit_surface 2, inequality_region 1; needs live Desmos visual verification |
| 55 | https://www.desmos.com/3d/umjxv6ahck | [4B] 3D Diagram - S2-09 Group F.json | yes | partial | yes | 24 | 26 | 3 | partial export; 24 unsupported; inequality_region 23, classification 1; needs live Desmos visual verification |
| 56 | https://www.desmos.com/3d/oqffspzojt | [4B] 3D Diagram - S2-09 Group G.json | yes | partial | yes | 7 | 84 | 80 | partial export; 7 unsupported; inequality_region 4, classification 3; needs live Desmos visual verification |
| 57 | https://www.desmos.com/3d/g53xte50e7 | [4B] 3D Diagram - S2-10 Group A.json | yes | partial | yes | 8 | 40 | 32 | partial export; 8 unsupported; explicit_surface 4, inequality_region 4; needs live Desmos visual verification |
| 58 | https://www.desmos.com/3d/flaqwkpbgj | [4B] 3D Diagram - S2-10 Group B.json | yes | partial | yes | 1 | 115 | 115 | partial export; 1 unsupported; classification 1; needs live Desmos visual verification |
| 59 | https://www.desmos.com/3d/151jsdn8xs | [4B] 3D Diagram - S2-10 Group C.json | yes | partial | yes | 5 | 7 | 3 | partial export; 5 unsupported; inequality_region 4, classification 1; needs live Desmos visual verification |
| 60 | https://www.desmos.com/3d/egutwuose9 | [4B] 3D Diagram - S2-10 Group D.json | yes | partial | yes | 4 | 25 | 21 | partial export; 4 unsupported; explicit_surface 4; needs live Desmos visual verification |
| 61 | https://www.desmos.com/3d/xzhfl6m1td | [4B] 3D Diagram - S2-10 Group E.json | yes | partial | yes | 10 | 249 | 249 | partial export; 10 unsupported; classification 10; needs live Desmos visual verification |
| 62 | https://www.desmos.com/3d/tejhfrm34m | [4B] 3D Diagram - S2-10 Group F.json | yes | partial | yes | 82 | 167 | 85 | partial export; 82 unsupported; inequality_region 82; needs live Desmos visual verification |
| 63 | https://www.desmos.com/3d/ezmhu7lfyu | [4B] 3D Diagram - S2-10 Group G.json | yes | partial | yes | 10 | 46 | 41 | partial export; 10 unsupported; classification 5, inequality_region 4, explicit_surface 1; needs live Desmos visual verification |
| 64 | https://www.desmos.com/3d/t4sd1jyl5z | [4B] 3D Diagram - S2-07 Group B.json | yes | partial | yes | 4 | 63 | 59 | partial export; 4 unsupported; inequality_region 4; needs live Desmos visual verification |
| 65 | https://www.desmos.com/3d/bfj4fa4oiq | [4B] 3D Diagram - S2-09 Group C.json | yes | partial | yes | 2 | 74 | 74 | partial export; 2 unsupported; classification 2; needs live Desmos visual verification |
| 66 | https://www.desmos.com/3d/gk9kr8h9ki | [4B] 3D Diagram - S2-09 Group A.json | yes | partial | yes | 41 | 62 | 21 | partial export; 41 unsupported; inequality_region 41; needs live Desmos visual verification |
