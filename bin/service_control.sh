#!/usr/bin/env bash
set -euo pipefail
dry_run=false
if [[ ${1:-} == --dry-run ]]; then dry_run=true; shift; fi
if [[ ${1:-} == --help ]]; then
    echo '用法: bash service_control.sh [--dry-run] <service_name> <start|stop|restart|status>'
    exit 0
fi
[[ $# == 2 && $1 =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.@:-]*$ ]] || { echo '错误: 需要合法服务名称和操作，参见 --help' >&2; exit 2; }
service=$1
action=$2
case $action in start|stop|restart|status) ;; *) echo '错误: 不支持的操作' >&2; exit 2;; esac
if $dry_run; then printf 'systemctl --no-pager %s -- %s\n' "$action" "$service"; exit 0; fi
command -v systemctl >/dev/null || { echo '错误: 需要 systemd/systemctl' >&2; exit 2; }
# 保留 systemctl 原始退出码；不自动 sudo，也不隐藏执行失败。
exec systemctl --no-pager "$action" -- "$service"
