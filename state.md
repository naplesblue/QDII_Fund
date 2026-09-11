# Project State
Updated: 2026-09-11 Asia/Shanghai
Status: complete
## Goal
Organize and document the project, push to naplesblue/QDII_Fund, deploy a Git release on fund.naplesblue.cn.
## Current phase
handoff
## Completed
- Pushed public GitHub repository naplesblue/QDII_Fund; VPS cloned it and activated a pinned Git release.
- Dedicated systemd service enabled, isolated Nginx site installed, HTTPS issued and renewal timer confirmed.
- Migrated 735-share snapshot with original timestamps; runtime data remains outside Git.
- Organized backend, tests, data seed, scripts and archived research.
- Existing shared cache uses NAV 6h, history/detail 24h, purchase 30m, quotes 5m; persistent cooldown and deduplication.
## Decisions
- Preserve public repository visibility chosen by user; exclude runtime snapshots, cache and credentials.
- Use dedicated service account, immutable release directories and separate /var/lib/fund-atlas state.
## Changed files
- fund_atlas/, tests/, scripts/, data/, docs/, README.md, deploy/ — organized code and documentation.
## Verification
- Restructured code: 21 tests passed; compileall and JavaScript syntax check passed.
- VPS: 21 tests passed; nginx -t passed; HTTPS status/data endpoints passed (735 shares).
- Production NAV retry 008971 returned cached=true, preserving 14:15:57 timestamp.
- Browser rendered 15 rows without horizontal overflow; searching 008971 returned one matching row with NAV 6.2248.
- Production uses /opt/fund-atlas/current pointing to a pinned Git release; favicon returns HTTPS 200.
- Desktop header uses main content edges, groups subtitle with brand, and keeps refresh aligned right.
- Header browser preview at 1920px: brand/main left edges both 206.39px; no horizontal overflow.
- Initial 2-second readiness check was too short for 9-second cache bootstrap; fixed to poll up to 30 attempts.
## Next action
None — complete. Future updates: push tested commit, fetch on VPS, run deploy/release.sh with that commit.
## Blockers and risks
- Trading calendar covers 2026 only; extend before 2027.
- Public upstream availability is not guaranteed; failures use cooldown.
