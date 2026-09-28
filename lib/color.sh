#!/bin/bash
# shellcheck disable=SC2034
# Public color constants are also available to callers that source this library.
# ===============================================
# lib/color.sh - 终端颜色输出
# 用法: source lib/color.sh
# ===============================================

# 颜色定义
COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_BLUE='\033[0;34m'
COLOR_PURPLE='\033[0;35m'
COLOR_CYAN='\033[0;36m'
COLOR_NC='\033[0m'  # No Color

if [[ ! -t 1 || -n ${NO_COLOR:-} ]]; then
    COLOR_RED='' COLOR_GREEN='' COLOR_YELLOW='' COLOR_BLUE=''
    COLOR_PURPLE='' COLOR_CYAN='' COLOR_NC=''
fi

# === 打印函数 ===

# 打印红色（错误）
print_error() {
    printf '%b%s%b\n' "${COLOR_RED}" "[ERROR] $*" "$COLOR_NC" >&2
}

# 打印黄色（警告）
print_warn() {
    printf '%b%s%b\n' "${COLOR_YELLOW}" "[WARN]  $*" "$COLOR_NC"
}

# 打印绿色（成功/正常）
print_ok() {
    printf '%b%s%b\n' "${COLOR_GREEN}" "[OK]    $*" "$COLOR_NC"
}

# 打印蓝色（信息）
print_info() {
    printf '%b%s%b\n' "${COLOR_BLUE}" "[INFO]  $*" "$COLOR_NC"
}

# 打印青色（标题）
print_title() {
    printf '%b%s%b\n' "${COLOR_CYAN}" "=========================================" "$COLOR_NC"
    printf '%b%s%b\n' "${COLOR_CYAN}" "$*" "$COLOR_NC"
    printf '%b%s%b\n' "${COLOR_CYAN}" "=========================================" "$COLOR_NC"
}
