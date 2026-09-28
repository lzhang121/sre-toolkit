#!/usr/bin/env bash
# Internal fixed-argument inspection commands. Use sre.sh for validation/timeouts.
set -Eeuo pipefail
trap 'exit 2' ERR
export LC_ALL=C
task=${1:-}
shift || true
status=0
warn() { if ((status == 0)); then status=1; fi; }
case "$task" in
    system) required=(cat uname uptime bash free timedatectl);;
    storage) required=(df awk findmnt);;
    processes) required=(ps sed systemctl);;
    network) required=(ip ss);;
    logs|journal) required=(journalctl id);;
    directory) required=(du);;
    service_status) required=(systemctl);;
    dns) required=(getent);;
    tcp) required=(timeout bash);;
    http) required=(curl);;
    *) exit 2;;
esac
for tool in "${required[@]}"; do command -v "$tool" >/dev/null || { echo "Missing command: $tool" >&2; exit 2; }; done
if [[ $task == logs || $task == journal ]]; then
    groups=$(id -nG)
    if [[ $EUID != 0 && " $groups " != *' systemd-journal '* ]]; then
        echo 'System journal visibility requires root or systemd-journal membership' >&2
        exit 2
    fi
fi
case "$task" in
    system)
        cat /etc/os-release
        uname -r
        uptime
        root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
        bash "$root/bin/health_check.sh" || status=$?
        free -m
        synced=$(timedatectl show -p NTPSynchronized --value)
        printf 'NTPSynchronized=%s\n' "$synced"
        [[ $synced == yes ]] || warn
        ;;
    storage)
        # GNU df -l excludes remote filesystems; no implicit directory traversal.
        df -lPk
        df -lPi
        if df -lPk | awk 'NR>1 {gsub(/%/,"",$5); if($5>80) bad=1} END {exit !bad}'; then warn; fi
        if df -lPi | awk 'NR>1 {gsub(/%/,"",$5); if($5>80) bad=1} END {exit !bad}'; then warn; fi
        mounts=$(findmnt -rn -o TARGET,FSTYPE,OPTIONS)
        printf '%s\n' "$mounts"
        if printf '%s\n' "$mounts" | awk '$2 ~ /^(ext[234]|xfs|btrfs|vfat)$/ && $3 ~ /(^|,)ro(,|$)/ {bad=1} END {exit !bad}'; then warn; fi
        ;;
    processes)
        ps -eo pid,user,comm,pcpu,pmem --sort=-pcpu | sed -n '1,11p'
        ps -eo pid,user,comm,pcpu,pmem --sort=-pmem | sed -n '1,11p'
        failed=$(systemctl --no-pager --plain --failed --no-legend)
        printf '%s\n' "$failed"
        [[ -z $failed ]] || warn
        ;;
    network)
        ip -brief address
        ip route
        ss -lntu
        ;;
    logs)
        # Metadata only: journal content needs the explicit journal task.
        journalctl --disk-usage
        ;;
    directory)
        [[ $# == 1 && -d $1 ]] || exit 2
        du -sx -- "$1"
        ;;
    service_status)
        [[ $# == 1 ]] || exit 2
        systemctl --no-pager show --property=LoadState,ActiveState,SubState -- "$1"
        systemctl is-active --quiet -- "$1" || warn
        ;;
    dns)
        [[ $# == 1 ]] || exit 2
        getent ahosts "$1" || warn
        ;;
    tcp)
        [[ $# == 2 ]] || exit 2
        timeout 10 bash -c 'exec 3<>"/dev/tcp/$1/$2"' bash "$1" "$2" || warn
        ;;
    http)
        [[ $# == 1 ]] || exit 2
        # Do not follow redirects to unselected destinations; never print bodies.
        code=$(curl --silent --show-error --connect-timeout 5 --max-time 15 --proto '=http,https' --output /dev/null --write-out '%{http_code}' -- "$1") || warn
        printf 'http_status=%s\n' "$code"
        [[ $code =~ ^2[0-9][0-9]$ ]] || warn
        ;;
    journal)
        [[ $# == 2 ]] || exit 2
        entries=$(journalctl --quiet --no-pager -u "$1" --since "$2 minutes ago" -p err -n 200 -o short-iso)
        printf '%s\n' "$entries"
        [[ -z $entries ]] || warn
        ;;
    *) echo 'Unsupported inspection task' >&2; exit 2 ;;
esac
exit "$status"
