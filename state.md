# Project State
Updated: 2026-09-24 Asia/Shanghai
Status: complete
## Goal
Add an on-demand 1/3/5-year unit-NAV history chart with valuation-date hover details, using the shared historical source cache and no upstream request on chart open.
## Current phase
handoff
## Completed
- Confirmed current three-year 80-point percentage sketch is embedded in fund snapshots; daily raw history is not exposed to the UI.
- Confirmed history source cache is shared and raw vendor responses are saved as evidence on successful fetches.
- Added daily unit NAV to shared history records and an on-demand 1/3/5-year API with validated legacy evidence fallback.
- Replaced the old three-year sampled sketch with a detailed chart; table NAV opens the same chart on hover/click.
## Decisions
- Show daily unit NAV as a line, never synthetic OHLC candles; mark dividend/split events and distinguish reported daily change.
- Keep daily series out of the main 735-fund snapshot; serve one fund on demand from the existing history cache, with checked legacy evidence fallback.
- Chart reads must not contact upstream; a missing series prompts use of the existing refresh action.
## Changed files
- fund_atlas/server.py — cache-backed daily series and single-fund API.
- web/app.js, web/nav-history.js, web/index.html, web/style.css — table and detail charts.
- tests/test_screener.py — daily series, cache-only reads, failed-cache and legacy evidence checks.
- README.md — chart behavior and data limits.
- state.md — current verification checkpoint.
## Verification
- 30 Python tests passed; JS syntax, trade sorting test and git diff whitespace check passed.
- Browser: table popup rendered 783 daily points, detail chart and 1-year switch rendered 262 points; dragged across chart and date/price readout changed.
- Local API returned 783 synthetic QA points for one 3-year fund; VPS had 730 raw NAV evidence files before release.
- GitHub commit f8c87aa pushed; VPS release f8c87aa deployed with 30 passing tests, active systemd service and premium collector enabled.
- Public API and browser chart for 161128 returned/rendered 728 real valuation dates from 2023-09-21 to 2026-09-21.
## Next action
None — deployed and verified.
## Blockers and risks
- Existing cached records without daily series or raw evidence need the next history source refresh. Unit NAV is unadjusted around dividends and is not total return.
