# Project State
Updated: 2026-09-21 Asia/Shanghai
Status: verifying
## Goal
Display three distinct subscription/trading routes in one column, retain numeric OTC sorting and deploy.
## Current phase
verification
## Completed
- Replaced quota cell with three labeled rows: OTC subscription, exchange subscription, exchange trading.
- Numeric OTC sort keeps missing/paused values last, separates RMB/USD and ignores display text.
- Added conservative share-level channel classification and overlapping exchange/OTC filters for listed LOFs.
- Renamed quota column/filter/detail/CSV to OTC subscription limits; exchange ETF quota displays not applicable.
- Added channel badges and detail explanation; no historical PCF values added to live page.
- Read-only VPS probe obtained dated 2026-09-11 PCFs for 513100, 513390, 513110 and 159696.
- LOF 161128 official status lacks explicit exchange-channel scope; exchange limit remains unverified.
- Findings and API parameters saved in docs/primary-subscription-research.md; raw responses in work/primary-probe/.
- Pushed public GitHub repository naplesblue/QDII_Fund; VPS cloned it and activated a pinned Git release.
- Dedicated systemd service enabled, isolated Nginx site installed, HTTPS issued and renewal timer confirmed.
- Migrated 735-share snapshot with original timestamps; runtime data remains outside Git.
- Organized backend, tests, data seed, scripts and archived research.
- Existing shared cache uses NAV 6h, history/detail 24h, purchase 30m, quotes 5m; persistent cooldown and deduplication.
## Decisions
- Preserve public repository visibility chosen by user; exclude runtime snapshots, cache and credentials.
- Use dedicated service account, immutable release directories and separate /var/lib/fund-atlas state.
## Changed files
- docs/primary-subscription-research.md — official endpoint feasibility and exact sample limits; no application changes this turn.
- fund_atlas/, tests/, scripts/, data/, docs/, README.md, deploy/ — organized code and documentation.
## Verification
- Node trade-info checks passed for ascending/descending currency groups, missing/paused values and channel display.
- 22 Python tests and JS syntax passed; desktop screenshot inspected; mobile 390px no overflow, three rows present.
- VPS release c0aaf0e passed 22 tests and health check; live data includes channels (161128 both, 008971 OTC, 159696 exchange, 012868 OTC).
- 22 Python tests passed, including listed LOF versus nonlisted C share and paused subscription cases.
- JavaScript syntax passed; browser LOF-only filter returned 15 matching rows, no console errors.
- Desktop 1440px and mobile 390px layouts checked; mobile has no horizontal overflow.
- Restructured code: 21 tests passed; compileall and JavaScript syntax check passed.
- VPS: 21 tests passed; nginx -t passed; HTTPS status/data endpoints passed (735 shares).
- Production NAV retry 008971 returned cached=true, preserving 14:15:57 timestamp.
- Browser rendered 15 rows without horizontal overflow; searching 008971 returned one matching row with NAV 6.2248.
- Production uses /opt/fund-atlas/current pointing to a pinned Git release; favicon returns HTTPS 200.
- Desktop header uses main content edges, groups subtitle with brand, and keeps refresh aligned right.
- Header browser preview at 1920px: brand/main left edges both 206.39px; no horizontal overflow.
- Initial 2-second readiness check was too short for 9-second cache bootstrap; fixed to poll up to 30 attempts.
## Next action
Deploy verified three-route display and verify live static assets.
## Blockers and risks
- Four ETF samples are not full-market coverage; LOF channel scope and missing/zero semantics require further verification.
- Trading calendar covers 2026 only; extend before 2027.
- Public upstream availability is not guaranteed; failures use cooldown.
