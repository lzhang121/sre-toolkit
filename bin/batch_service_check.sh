#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
if [[ ${1:-} == --help ]]; then
    echo '用法: bash batch_service_check.sh [hosts.txt]；无参数检查本机默认 systemd 服务'
    echo 'hosts.txt: 主机 端口 服务标签；CONCURRENCY=8，TIMEOUT=3（秒）'
    exit 0
fi
result=0
if [[ $# == 0 ]]; then
    command -v systemctl >/dev/null || { echo '错误: 需要 systemctl' >&2; exit 2; }
    for service in nginx postgresql redis docker sshd; do
        if systemctl is-active --quiet -- "$service"; then printf '[OK] %s\n' "$service"
        else printf '[FAIL] %s\n' "$service"; result=1; fi
    done
    exit "$result"
fi
[[ $# == 1 && -f $1 && -r $1 ]] || { echo '错误: 需要可读主机清单' >&2; exit 2; }
concurrency=${CONCURRENCY:-8}
timeout_seconds=${TIMEOUT:-3}
[[ $concurrency =~ ^[1-9][0-9]{0,2}$ && $timeout_seconds =~ ^[1-9][0-9]{0,2}$ ]] || { echo '错误: CONCURRENCY/TIMEOUT 必须是 1-999' >&2; exit 2; }
command -v timeout >/dev/null || { echo '错误: 需要 GNU timeout' >&2; exit 2; }
hosts=(); ports=(); labels=()
while IFS= read -r line || [[ -n $line ]]; do
    line=${line%$'\r'}
    line=${line%%#*}
    read -r host port label extra <<< "$line"
    [[ -n ${host:-} ]] || continue
    [[ $host =~ ^[a-zA-Z0-9_:][a-zA-Z0-9_.:%-]*$ && ${port:-} =~ ^[0-9]{1,5}$ && -n ${label:-} && -z ${extra:-} ]] || { echo '错误: 清单格式必须是 主机 端口 标签' >&2; exit 2; }
    port=$((10#$port))
    ((port >= 1 && port <= 65535)) || { echo '错误: 端口超出范围' >&2; exit 2; }
    hosts+=("$host"); ports+=("$port"); labels+=("$label")
done < "$1"
((${#hosts[@]} > 0)) || { echo '错误: 主机清单为空' >&2; exit 2; }
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || :; done; wait || :; }
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
probe() {
    if timeout "$timeout_seconds" bash -c 'exec 3<>"/dev/tcp/$1/$2"' bash "$1" "$2" 2>/dev/null; then
        printf '[OK] %s %s:%s\n' "$3" "$1" "$2"
    else printf '[FAIL] %s %s:%s\n' "$3" "$1" "$2"; return 1; fi
}
# 固定大小批次兼容 Bash 4，不依赖 wait -n。
for ((i=0; i<${#hosts[@]}; i++)); do
    probe "${hosts[i]}" "${ports[i]}" "${labels[i]}" &
    pids+=("$!")
    if ((${#pids[@]} >= concurrency)); then
        for pid in "${pids[@]}"; do wait "$pid" || result=1; done
        pids=()
    fi
done
for pid in "${pids[@]}"; do wait "$pid" || result=1; done
exit "$result"
