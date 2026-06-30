#!/bin/bash
# ===============================================
# lib/color.sh - 终端颜色输出
# 用法: source lib/color.sh
# ===============================================

# 颜色定义
readonly COLOR_RED='\033[0;31m'
readonly COLOR_GREEN='\033[0;32m'
readonly COLOR_YELLOW='\033[0;33m'
readonly COLOR_BLUE='\033[0;34m'
readonly COLOR_PURPLE='\033[0;35m'
readonly COLOR_CYAN='\033[0;36m'
readonly COLOR_NC='\033[0m'  # No Color

# === 打印函数 ===

# 打印红色（错误）
print_error() {
    echo -e "${COLOR_RED}[ERROR] $*${COLOR_NC}"
}

# 打印黄色（警告）
print_warn() {
    echo -e "${COLOR_YELLOW}[WARN]  $*${COLOR_NC}"
}

# 打印绿色（成功/正常）
print_ok() {
    echo -e "${COLOR_GREEN}[OK]    $*${COLOR_NC}"
}

# 打印蓝色（信息）
print_info() {
    echo -e "${COLOR_BLUE}[INFO]  $*${COLOR_NC}"
}

# 打印青色（标题）
print_title() {
    echo -e "${COLOR_CYAN}=========================================${COLOR_NC}"
    echo -e "${COLOR_CYAN}$*${COLOR_NC}"
    echo -e "${COLOR_CYAN}=========================================${COLOR_NC}"
}