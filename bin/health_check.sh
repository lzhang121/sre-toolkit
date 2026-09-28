#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
if [[ ${1:-} == --help ]]; then
    echo '用法: bash health_check.sh；Linux /proc，CPU 采样 1 秒'
    echo 'CPU_THRESHOLD/MEM_THRESHOLD/DISK_THRESHOLD/INODE_THRESHOLD=80；LOAD_THRESHOLD=1（每核负载）；DISK_PATH=/'
    exit 0
fi
[[ $# == 0 && $(uname -s) == Linux ]] || { echo '错误: 仅支持 Linux，且不接受位置参数' >&2; exit 2; }
status=0
report() {
    local label=$1 value=$2 threshold=$3 unit=$4
    if [[ ! $value =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        printf '[UNKNOWN] %s: 采集失败\n' "$label"; status=2
    elif awk -v v="$value" -v t="$threshold" 'BEGIN {exit !(v>t)}'; then
        printf '[WARN] %s: %s%s (阈值 %s)\n' "$label" "$value" "$unit" "$threshold"
        ((status != 0)) || status=1
    else printf '[OK] %s: %s%s\n' "$label" "$value" "$unit"; fi
}
for threshold in "${CPU_THRESHOLD:-80}" "${MEM_THRESHOLD:-80}" "${DISK_THRESHOLD:-80}" "${INODE_THRESHOLD:-80}"; do
    [[ $threshold =~ ^[0-9]+([.][0-9]+)?$ ]] && awk -v t="$threshold" 'BEGIN {exit !(t>=0 && t<=100)}' || { echo '错误: 百分比阈值必须在 0-100' >&2; exit 2; }
done
[[ ${LOAD_THRESHOLD:-1} =~ ^[0-9]+([.][0-9]+)?$ ]] || { echo '错误: LOAD_THRESHOLD 必须为非负数字' >&2; exit 2; }
cpu_snapshot() { awk '/^cpu / {s=0; for(i=2;i<=9;i++) s+=$i; print s, $5+$6; found=1; exit} END {if(!found) exit 1}' /proc/stat; }
printf '服务器健康检查 %s\n' "$(date -u +%FT%TZ)"
first=$(cpu_snapshot) || first=''
sleep 1
second=$(cpu_snapshot) || second=''
cpu=''
if [[ -n $first && -n $second ]]; then
    cpu=$(awk -v a="$first" -v b="$second" 'BEGIN {split(a,x);split(b,y);d=y[1]-x[1]; if(d>0 && y[2]>=x[2]) printf "%.2f",100*(1-(y[2]-x[2])/d)}')
fi
report CPU "$cpu" "${CPU_THRESHOLD:-80}" '%'
memory=$(awk '/^MemTotal:/ {t=$2} /^MemAvailable:/ {a=$2;found=1} END {if(t>0 && found && a<=t) printf "%.2f",100*(t-a)/t}' /proc/meminfo) || memory=''
report 内存 "$memory" "${MEM_THRESHOLD:-80}" '%'
for metric in disk inode; do
    flags=-Pk; threshold=${DISK_THRESHOLD:-80}; label=磁盘
    if [[ $metric == inode ]]; then flags=-Pi; threshold=${INODE_THRESHOLD:-80}; label=Inode; fi
    value=$(df "$flags" -- "${DISK_PATH:-/}" | awk 'NR==2 {gsub(/%/,"",$5); print $5}') || value=''
    report "$label" "$value" "$threshold" '%'
done
cores=$(getconf _NPROCESSORS_ONLN) || cores=''
load=''
if [[ $cores =~ ^[1-9][0-9]*$ ]]; then
    load=$(awk -v n="$cores" 'NR==1 && $1 ~ /^[0-9]+[.][0-9]+$/ {printf "%.2f",$1/n}' /proc/loadavg) || load=''
fi
report '1分钟每核负载' "$load" "${LOAD_THRESHOLD:-1}" ''
exit "$status"
