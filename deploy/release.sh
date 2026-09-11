#!/bin/sh
# Run as root on the VPS: sh /opt/fund-atlas/repo/deploy/release.sh <commit>
set -eu
commit=${1:?Pass the exact commit to deploy}
base=/opt/fund-atlas
resolved=$(git -C "$base/repo" rev-parse --verify "$commit^{commit}")
release="$base/releases/$resolved"
if [ -e "$release" ]; then
    echo "Release already exists: $release"
else
    mkdir -p "$release"
    git -C "$base/repo" archive "$resolved" | tar -x -C "$release"
fi
# Isolate test cache from production and avoid generated files in code releases.
test_data=$(mktemp -d)
trap 'rm -rf "$test_data"' EXIT
(cd "$release" && PYTHONDONTWRITEBYTECODE=1 FUND_DATA_DIR="$test_data" python3 -m unittest discover -s tests)
previous=$(readlink "$base/current" || true)
ln -s "$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
if systemctl restart fund-atlas && sleep 2 && curl --fail --silent http://127.0.0.1:8765/api/status >/dev/null; then
    printf '%s\n' "Active release: $resolved"
else
    echo 'Health check failed; restoring previous code release.' >&2
    if [ -n "$previous" ]; then
        ln -s "$previous" "$base/current.previous"
        mv -Tf "$base/current.previous" "$base/current"
        systemctl restart fund-atlas
    fi
    exit 1
fi
