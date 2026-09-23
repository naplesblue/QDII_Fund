# Project State
Updated: 2026-09-24 Asia/Shanghai
Status: complete
## Goal
Keep the NAV history popover open when switching ranges, add a 30-day range, and show a dated/value crosshair on hover.
## Current phase
handoff
## Completed
- Confirmed current three-year 80-point percentage sketch is embedded in fund snapshots; daily raw history is not exposed to the UI.
- Confirmed history source cache is shared and raw vendor responses are saved as evidence on successful fetches.
- Added daily unit NAV to shared history records and an on-demand 1/3/5-year API with validated legacy evidence fallback.
- Replaced the old three-year sampled sketch with a detailed chart; table NAV opens the same chart on hover/click.
- Diagnosed popover closure: switching range replaces the clicked button before the document-level outside-click handler runs.
- Added 30-day cache-only NAV query and four UI ranges; clicking within the popover remains inside despite DOM replacement.
- Added visible horizontal/vertical SVG guides with selected date and unit-NAV axis labels.
## Decisions
- Show daily unit NAV as a line, never synthetic OHLC candles; mark dividend/split events and distinguish reported daily change.
- Keep daily series out of the main 735-fund snapshot; serve one fund on demand from the existing history cache, with checked legacy evidence fallback.
- Chart reads must not contact upstream; a missing series prompts use of the existing refresh action.
- Define 30 days as 30 calendar days ending at the historical series' latest valuation date.
## Changed files
- fund_atlas/server.py — cache-backed daily series and single-fund API.
- web/app.js, web/nav-history.js, web/index.html, web/style.css — table and detail charts.
- tests/test_screener.py — daily series, cache-only reads, failed-cache and legacy evidence checks.
- README.md — chart behavior and data limits.
- state.md — current verification checkpoint.
- fund_atlas/server.py, tests/test_screener.py — 30-day date window and test.
- web/nav-history.js, web/style.css, README.md — stable range controls, crosshair and documentation.
## Verification
- 30 Python tests passed; JS syntax, trade sorting test and git diff whitespace check passed.
- Browser: table popup rendered 783 daily points, detail chart and 1-year switch rendered 262 points; dragged across chart and date/price readout changed.
- Local API returned 783 synthetic QA points for one 3-year fund; VPS had 730 raw NAV evidence files before release.
- GitHub commit f8c87aa pushed; VPS release f8c87aa deployed with 30 passing tests, active systemd service and premium collector enabled.
- Public API and browser chart for 161128 returned/rendered 728 real valuation dates from 2023-09-21 to 2026-09-21.
- 31 Python tests, JS syntax, trade sorting and diff whitespace checks passed locally.
- Browser popup stayed open after switching 3y → 30d (22 observations) → 5y (1305 observations). Detail dialog switched to 30d. Crosshair screenshot showed both guides plus 2025-09-03 / 3.9712 badges.
- GitHub commit 369cd10 pushed and VPS release 369cd10 deployed; VPS service active and 31 Python tests passed during release.
- Public browser: 161128 popup stayed open at 30d with 21 valuation dates (2026-08-24 through 2026-09-21); crosshair interaction showed 2026-09-11 / 6.7984 in the readout and both SVG axis labels.
## Next action
None; deployed and verified.
## Blockers and risks
- Existing cached records without daily series or raw evidence need the next history source refresh. Unit NAV is unadjusted around dividends and is not total return.
