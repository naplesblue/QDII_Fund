# Project State
Updated: 2026-09-11 Asia/Shanghai
Status: verifying
## Goal
Organize and document the project, push to naplesblue/QDII_Fund, deploy a Git release on fund.naplesblue.cn.
## Current phase
verification
## Completed
- Inspected empty public GitHub repository and VPS tools/sites; SSH works.
- Organized backend, tests, data seed, scripts and archived research.
- Existing shared cache uses NAV 6h, history/detail 24h, purchase 30m, quotes 5m; persistent cooldown and deduplication.
## Decisions
- Preserve public repository visibility chosen by user; exclude runtime snapshots, cache and credentials.
- Use dedicated service account, immutable release directories and separate /var/lib/fund-atlas state.
## Changed files
- fund_atlas/, tests/, scripts/, data/, docs/, README.md, deploy/ — organized code and documentation.
## Verification
- Restructured code: 21 tests passed; compileall and JavaScript syntax check passed.
- VPS Python 3.10, Git, curl, Nginx and certbot available; port 8765 unused.
## Next action
Verify organized project, push repository, clone and activate on VPS with TLS.
## Blockers and risks
- Trading calendar covers 2026 only; extend before 2027.
- Public upstream availability is not guaranteed; failures use cooldown.
