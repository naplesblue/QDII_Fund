# Project State
Updated: 2026-09-24 Asia/Shanghai
Status: complete
## Goal
Keep NAV and premium history popovers open while switching time ranges; provide a 30-day NAV range and dated/value crosshair.
## Current phase
handoff
## Completed
- Added cache-backed daily unit-NAV history and 30-day, 1-year, 3-year, 5-year chart ranges.
- Added NAV chart crosshair with date and unit-NAV labels; switching ranges keeps its popover open.
- Fixed the same detached-button outside-click bug in the premium history popover using the click event's composed path.
- Versioned the premium script URL so browsers load the deployed fix instead of a cached copy.
## Decisions
- Chart reads use shared history caches only, without upstream requests.
- The 30-day NAV range ends at each fund's latest historical valuation date.
- Unit NAV is unadjusted; dividend/split jumps do not represent holding return.
## Changed files
- fund_atlas/server.py — cache-backed NAV history API.
- web/nav-history.js, web/style.css — NAV ranges and crosshair.
- web/premium-history.js — stable premium range switching.
- web/index.html — versioned premium script URL.
- tests/test_screener.py, README.md — NAV window test and behavior documentation.
## Verification
- Local browser: premium popup remained open switching 30 → 7 → 90 days; close button still worked.
- VPS release 6107a78c2a5af536b712eca9f233c0f4d0b70ed7 passed 31 Python tests; systemd service active.
- Public browser: script URL contains v=20260924a; 513310 premium popup stayed open switching 30 → 7 → 90 days.
- Earlier public browser check: 161128 NAV popup stayed open at 30 days and crosshair showed date and value labels.
## Next action
None — complete.
## Blockers and risks
- Existing cached NAV records without daily series need the next source refresh; unit NAV is not total return.
