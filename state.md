# Project State
Updated: 2026-09-29 Asia/Shanghai
Status: complete
## Goal
VPS automatically updates shared fund data; browser refresh reads snapshots without waiting for upstream.
## Current phase
handoff
## Completed
- Deployed scheduler and snapshot-only browser refresh to production; first automatic round completed.
- Added negotiated gzip compression for large JSON responses.
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
- Python unittest: 36 passed; node --check web/app.js passed; trade-info JS tests passed.
- Production release 7300400a9086c0f6686db924fce61075425affc5: 36 tests passed; service healthy.
- Browser refresh returned snapshot status and enabled button.
- Public compressed snapshot HTTP 200: 389974 bytes / 0.351 seconds in one measurement (previous uncompressed 3.5 MB / 7.7 seconds).
## Next action
None — complete.
## Blockers and risks
- Full refresh shares lock with premium collector and may delay premium samples.
