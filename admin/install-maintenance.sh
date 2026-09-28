#!/usr/bin/env bash
# Administrator-only deployment. Never called by operational Jenkins jobs.
set -euo pipefail
[[ $EUID == 0 && $# == 1 && $1 =~ ^[a-z_][a-z0-9_-]*$ ]] || {
    echo 'Usage (root): bash admin/install-maintenance.sh <existing-ops-user>' >&2
    exit 2
}
id -- "$1" >/dev/null
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
command -v visudo >/dev/null
install -d -o root -g root -m 0755 /opt/sre-toolkit-privileged /opt/sre-toolkit-privileged/sretoolkit /opt/sre-toolkit-privileged/bin /etc/sre-toolkit
install -d -o root -g root -m 0700 /var/lib/sre-toolkit /var/lib/sre-toolkit/plans
exec 9>/var/lib/sre-toolkit/maintenance.lock
flock -n 9 || { echo 'Maintenance is active; deploy after it completes' >&2; exit 1; }
# Exclude local __pycache__, virtualenvs and untracked executable content.
for file in __init__.py common.py tasks.py privileged.py; do
    install -o root -g root -m 0644 "$root/sretoolkit/$file" "/opt/sre-toolkit-privileged/sretoolkit/$file"
done
install -o root -g root -m 0644 "$root/bin/backup.sh" /opt/sre-toolkit-privileged/bin/backup.sh
install -o root -g root -m 0755 "$root/admin/sre-maint" /usr/local/sbin/sre-maint
if [[ ! -e /etc/sre-toolkit/policy.json ]]; then
    install -o root -g root -m 0600 "$root/configs/policy.example.json" /etc/sre-toolkit/policy.json
fi
tmp=$(mktemp)
trap 'rm -f -- "$tmp"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/sre-maint ""\n' "$1" > "$tmp"
visudo -cf "$tmp"
install -o root -g root -m 0440 "$tmp" /etc/sudoers.d/sre-toolkit
echo 'Installed. Policy defaults deny all. Review /etc/sre-toolkit/policy.json as root.'
