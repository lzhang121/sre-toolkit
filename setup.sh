#!/usr/bin/env bash
# 仅建立链接；仓库需留在当前位置。不覆盖已有命令。
set -euo pipefail
TOOLKIT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
INSTALL_DIR=${INSTALL_DIR:-/usr/local/bin}
if [[ ${1:-} == --help ]]; then echo '用法: INSTALL_DIR=$HOME/.local/bin bash setup.sh'; exit 0; fi
[[ $# == 0 ]] || { echo '错误: 不接受位置参数' >&2; exit 2; }
for script in "$TOOLKIT_DIR"/bin/*.sh "$TOOLKIT_DIR"/lib/*.sh; do bash -n "$script"; done
mkdir -p -- "$INSTALL_DIR"
# 先检查全部冲突，再执行安装；重复运行允许指向同一脚本的链接。
for script in "$TOOLKIT_DIR"/bin/*.sh; do
    target="$INSTALL_DIR/$(basename -- "$script" .sh)"
    if [[ -e $target || -L $target ]]; then
        [[ -L $target && $(readlink -- "$target") == "$script" ]] || { printf '错误: 已存在其他命令 %s\n' "$target" >&2; exit 1; }
    fi
done
for script in "$TOOLKIT_DIR"/bin/*.sh; do
    chmod +x -- "$script"
    target="$INSTALL_DIR/$(basename -- "$script" .sh)"
    [[ -L $target ]] || ln -s -- "$script" "$target"
done
printf '安装完成: %s（请确保该目录在 PATH 中）\n' "$INSTALL_DIR"
