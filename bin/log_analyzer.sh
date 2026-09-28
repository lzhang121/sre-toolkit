#!/usr/bin/env bash
# 支持标准 combined/common access log；不支持 JSON 或自定义字段布局。
set -euo pipefail
export LC_ALL=C
if [[ ${1:-} == --help ]]; then echo '用法: bash log_analyzer.sh [access.log]（common/combined 格式）'; exit 0; fi
log_file=${1:-/var/log/nginx/access.log}
[[ $# -le 1 && -f $log_file && -r $log_file ]] || { echo '错误: 需要可读的普通日志文件' >&2; exit 2; }
# 单次扫描；Top 表在临时文件中排序，避免 head 引发 SIGPIPE。
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
awk -v dir="$tmp" '
{
    total++
    split($0,q,"\"")
    request_count=split(q[2],r," ")
    split(q[3],s," ")
    if ($0 !~ /^[^ ]+ [^ ]+ [^ ]+ \[[^]]+\] "/ || request_count!=3 || r[3] !~ /^HTTP\/[0-9.]+$/ || s[1] !~ /^[1-5][0-9][0-9]$/) {invalid++; next}
    valid++; codes[s[1]]++; ips[$1]++; paths[r[2]]++
    if(s[1]==404) e404++
    if(s[1]>=500) e5xx++
}
END {
    printf "总行数: %d\n总请求数: %d\n无效行数: %d\n404 错误数: %d\n5xx 错误数: %d\n",total,valid,invalid,e404,e5xx
    for(k in codes) print codes[k],k > (dir "/codes")
    for(k in ips) print ips[k],k > (dir "/ips")
    for(k in paths) print paths[k],k > (dir "/paths")
    print invalid+0 > (dir "/invalid")
}' < "$log_file"
for table in codes ips paths; do
    case $table in codes) echo '状态码统计:';; ips) echo 'Top 10 请求 IP:';; paths) echo 'Top 10 请求路径:';; esac
    if [[ -f $tmp/$table ]]; then sort -k1,1nr -k2 "$tmp/$table" | sed -n '1,10p'; fi
done
[[ $(cat "$tmp/invalid") == 0 ]] || exit 1
