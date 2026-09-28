#!/usr/bin/env bash
# Requires an isolated Linux Docker host. Creates ONLY a unique compose project.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"
project="sre-test-$(date +%s)-$$"
compose=(docker compose -p "$project" -f tests/integration/compose.yml)
tmp=$(mktemp -d)
cleanup() {
    "${compose[@]}" logs --no-color > "$tmp/containers.log" 2>&1 || true
    mkdir -p test_output/integration
    cp "$tmp/containers.log" test_output/integration/
    "${compose[@]}" down --volumes --remove-orphans
    rm -rf -- "$tmp"
}
trap cleanup EXIT
"${compose[@]}" up -d --build
"${compose[@]}" exec -T controller ssh-keygen -q -t ed25519 -N '' -f /tmp/sre-key
"${compose[@]}" cp controller:/tmp/sre-key.pub "$tmp/key.pub"
for target in target-a target-b; do
    ready=false
    for ((attempt=0; attempt<30; attempt++)); do
        if "${compose[@]}" exec -T "$target" systemctl is-active --quiet sshd; then ready=true; break; fi
        sleep 2
    done
    "$ready" || { echo "sshd failed to start: $target" >&2; exit 1; }
    "${compose[@]}" cp "$tmp/key.pub" "$target:/home/sreops/.ssh/authorized_keys"
    "${compose[@]}" exec -T "$target" chown sreops:sreops /home/sreops/.ssh/authorized_keys
    "${compose[@]}" exec -T "$target" chmod 600 /home/sreops/.ssh/authorized_keys
    # Get keys directly via Docker control plane, not unauthenticated ssh-keyscan.
    "${compose[@]}" exec -T "$target" cat /etc/ssh/ssh_host_ed25519_key.pub | \
        awk -v host="$target" '{print host, $1, $2}' >> "$tmp/known_hosts"
done
"${compose[@]}" cp "$tmp/known_hosts" controller:/tmp/known_hosts
"${compose[@]}" exec -T controller touch /tmp/ssh_config
# Build an isolated git snapshot inside the disposable controller only.
"${compose[@]}" exec -T controller bash -c 'git init -q; git config user.email test@example.invalid; git config user.name integration; git add .; git commit -qm fixture'
"${compose[@]}" exec -T controller python -m unittest discover -s tests -p 'test_*.py' -v
"${compose[@]}" exec -T controller python tests/integration/exercise.py
for target in target-a target-b; do
    "${compose[@]}" exec -T -e SRE_INTEGRATION=1 "$target" python3 /opt/sre-source/tests/integration/security.py
    "${compose[@]}" exec -T "$target" bash -c 'set -euo pipefail; files=(/srv/sre-fixtures/backups/*.tar.gz); mkdir -p /srv/sre-fixtures/restore; tar -xzf "${files[0]}" -C /srv/sre-fixtures/restore; cmp /srv/sre-fixtures/source/config /srv/sre-fixtures/restore/source/config; test ! -e /srv/sre-fixtures/archive/old.log'
done
"${compose[@]}" cp controller:/work/test_output/fleet "$tmp/fleet"
mkdir -p test_output/integration
cp -R "$tmp/fleet" test_output/integration/
echo 'PASS: two-host SSH, preview/apply, backup restore, cleanup, fail-stop'
