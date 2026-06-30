#!/bin/bash
# ===============================================
# tests/test_health_check.sh - 健康检查脚本测试
# 用法: bash tests/test_health_check.sh
# ===============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_DIR="$(dirname "$SCRIPT_DIR")"
TARGET_SCRIPT="$TOOLKIT_DIR/bin/health_check.sh"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

passed=0
failed=0

# 测试函数
test_case() {
    local name=$1
    local cmd=$2
    
    echo -n "测试: $name ... "
    
    if eval "$cmd" >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((passed++))
    else
        echo -e "${RED}FAIL${NC}"
        ((failed++))
    fi
}

echo "==========================================="
echo "  SRE Toolkit 测试套件"
echo "==========================================="
echo ""

# 测试 1: 脚本存在
test_case "脚本存在" "[ -f '$TARGET_SCRIPT' ]"

# 测试 2: 脚本有执行权限（可选）
test_case "脚本可执行" "[ -x '$TARGET_SCRIPT' ] || chmod +x '$TARGET_SCRIPT'"

# 测试 3: 脚本能正常运行
test_case "脚本能运行" "bash '$TARGET_SCRIPT'"

# 测试 4: 输出包含 CPU 检查结果
test_case "输出包含 CPU" "bash '$TARGET_SCRIPT' | grep -q 'CPU'"

# 测试 5: 输出包含内存检查结果
test_case "输出包含内存" "bash '$TARGET_SCRIPT' | grep -q '内存'"

# 测试 6: 输出包含磁盘检查结果
test_case "输出包含磁盘" "bash '$TARGET_SCRIPT' | grep -q '磁盘'"

echo ""
echo "==========================================="
echo "  测试结果: 通过 $passed / 失败 $failed"
echo "==========================================="

[ $failed -eq 0 ] && exit 0 || exit 1