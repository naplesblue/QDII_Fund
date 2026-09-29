# Project State
Updated: 2026-09-29 Asia/Shanghai
Status: verifying
## Goal
VPS automatically updates shared fund data; browser refresh reads snapshots without waiting for upstream.
## Current phase
verification
## Completed
- Verified production has only premium collector enabled; browser POST starts full upstream refresh.
## Decisions
- Background full refresh at startup and 30 minutes after completion; existing per-source TTLs and lock prevent duplicate upstream requests.
- Browser refresh and legacy POST refresh become snapshot-only; single-field retries retained.
- Production enables scheduler; local opt-in documented.
## Changed files
- server.py, app.js, index.html — background scheduler and snapshot-only refresh.
- deploy/fund-atlas.service, README.md — production enablement and operating documentation.
- tests/test_updater.py — scheduling and legacy endpoint regression tests.
## Verification
- Production systemd environment and API status inspected successfully.
- Python unittest: 35 passed; node --check web/app.js passed; trade-info JS tests passed.
## Next action
Deploy and verify production updater status and snapshot response.
## Blockers and risks
- Full refresh shares lock with premium collector and may delay premium samples.
