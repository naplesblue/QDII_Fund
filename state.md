# Project State
Updated: 2026-09-23 Asia/Shanghai
Status: complete
## Goal
Collect observed IOPV premiums every five minutes during trading sessions using the shared cache, preserve history and show hover/click charts.
## Current phase
handoff
## Completed
- Added separate SQLite history with code/quote timestamp deduplication and 7/30/90-day read API.
- Collector runs in production server, checks every 30s, fetches only when shared 5-minute quote cache expires and no manual job holds lock.
- Rejects invalid IOPV/prices, mismatched dates, stale/future and out-of-session observations. Failed current fetches do not erase history.
- Added desktop hover, click-to-pin and mobile click panel; zero line, extrema, sample count, dates and disconnected gaps over 20 minutes.
- Existing three-route subscription display, OTC numeric sorting, manual retry/cooldown and favorites retained.
## Decisions
- Enable scheduler via FUND_COLLECT_PREMIUM=1 in systemd; local default remains off.
- No synthetic history, prior NAV backfill or historic research samples injected. First recorded sample may have no line.
- Sources expose quote timestamps but not separately verified IOPV timestamps; data may be delayed.
- Runtime stays /var/lib/fund-atlas outside Git; pinned releases via /opt/fund-atlas/current.
## Changed files
- fund_atlas/premium_history.py, server.py — archive, shared collector, history API.
- web/premium-history.js, app.js, index.html, style.css — popover and history triggers.
- tests/test_premium_history.py, deploy/fund-atlas.service — verification and scheduler opt-in.
## Verification
- 26 Python tests passed; JS syntax and trade display/sort checks passed.
- Browser empty state and five isolated chart samples passed: 5 dots / 3 segments across a 30-minute gap.
- Mobile 390px panel within viewport, no overflow, no browser errors.
- VPS release c77d7eb deployed; 26 tests passed; systemd enabled and collector.enabled=true.
- Public HTTPS and local history APIs returned valid empty histories during lunch, as expected; no upstream request attempted off-session.
- Initial remote DNS failure cleared on retry; both endpoint checks passed.
## Next action
None — deployed. History begins with valid quotes in the next trading session; no real production samples existed during lunch verification.
## Blockers and risks
- Exchange calendar covers 2026 only; unknown years stop automated collection.
- Upstream availability, service downtime or long manual refresh can leave gaps; no complete tick-history claim.
