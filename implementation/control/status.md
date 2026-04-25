# Fixture USDZ Sweep Controller Status

- Active run session: none
- Last harvested run: `mild-basil`
- Last harvested at: `2026-04-25 17:47 +08`
- Policy: the previous full sweep finished and was harvested. Later wakes may start a new bounded tranche, but must not relaunch a long full sweep unless needed.

## Harvested baseline
- Total fixtures: `71`
- Success: `12`
- Partial USDZ outputs: `21`
- Errors before USDZ packaging: `38`
- Fixtures with USDZ artifacts present: `33`

## [4B] fixtures only
- Fixture count: `66`
- USDZ files present: `28`
- Missing USDZ files: `38`
- Success: `8`
- Partial: `20`
- Error: `38`

## Dominant blocker families
- Errors: implicit equality geometry (`18`), other unsupported expressions (`9`), segment expressions (`3`), tuple definition parse (`3`), other definition parse (`3`), list definition parse (`2`)
- Partials: inequality-region sampling (`11`), parametric `u`/`v` vars (`4`), evaluation failure (`2`)
