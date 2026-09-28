#!/usr/bin/env bash
# 原子发布归档；不自动删除历史备份。
set -euo pipefail
if [[ $# != 1 || $1 == --help ]]; then
    echo '用法: BACKUP_DIR=/var/backups/sre-toolkit bash backup.sh <文件或目录>'
    [[ ${1:-} == --help ]] && exit 0
    exit 2
fi
source_path=$(realpath -e -- "$1")
[[ -f $source_path || -d $source_path ]] || { echo '错误: 仅支持普通文件或目录' >&2; exit 2; }
backup_dir=${BACKUP_DIR:-/var/backups/sre-toolkit}
umask 077
mkdir -p -- "$backup_dir"
backup_dir=$(realpath -e -- "$backup_dir")
if [[ -d $source_path && ( $source_path == / || $backup_dir == "$source_path" || $backup_dir == "$source_path/"* ) ]]; then
    echo '错误: 备份目录不能位于源目录内部' >&2
    exit 2
fi
# 私有临时目录避免并发冲突；信号和失败均清理未完成归档。
staging=$(mktemp -d "$backup_dir/.backup.XXXXXXXX")
trap 'rm -rf -- "$staging"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
name=$(basename -- "$source_path")
archive="$backup_dir/${name}_$(date -u +%Y%m%dT%H%M%SZ)_${staging##*.}.tar.gz"
tar -czf "$staging/archive.tar.gz" -C "$(dirname -- "$source_path")" -- "$name"
tar -tzf "$staging/archive.tar.gz" >/dev/null
# 硬链接发布不会覆盖任何已有目标，且只公开完整文件。
ln -- "$staging/archive.tar.gz" "$archive"
printf '备份完成: %s\n' "$archive"
