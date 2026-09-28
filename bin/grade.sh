#!/usr/bin/env bash
set -euo pipefail
if [[ ${1:-} == --help ]]; then echo '用法: bash grade.sh <0-100>（人工评分分级，不采集健康指标）'; exit 0; fi
[[ $# == 1 && $1 =~ ^[0-9]{1,3}$ ]] || { echo '错误: 请输入 0-100 的整数' >&2; exit 2; }
score=$((10#$1))
((score <= 100)) || { echo '错误: 评分不能超过 100' >&2; exit 2; }
if ((score >= 90)); then grade=A
elif ((score >= 80)); then grade=B
elif ((score >= 70)); then grade=C
else grade=D
fi
printf '成绩: %s, 等级: %s\n' "$score" "$grade"
