#!/bin/bash
# ===============================================
# setup.sh - 一键安装脚本
# 用法: bash setup.sh
# 功能: 添加可执行权限、复制到 /usr/local/bin、创建日志目录
# ===============================================

set -e

TOOLKIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
LOG_DIR="${LOG_DIR:-/var/log/sre-toolkit}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo "==========================================="
echo "  SRE Toolkit 一键安装"
echo "==========================================="
echo ""

# 1. 添加可执行权限
echo -e "${YELLOW}[1/4]${NC} 添加可执行权限..."
find "$TOOLKIT_DIR/bin" -type f -name "*.sh" -exec chmod +x {} \;
find "$TOOLKIT_DIR/tests" -type f -name "*.sh" -exec chmod +x {} \;
echo -e "${GREEN}[OK]${NC} 完成"

# 2. 创建日志目录
echo -e "${YELLOW}[2/4]${NC} 创建日志目录 $LOG_DIR ..."
if [ -w "$(dirname "$LOG_DIR")" ]; then
    mkdir -p "$LOG_DIR"
    echo -e "${GREEN}[OK]${NC} 日志目录已创建"
else
    echo -e "${YELLOW}[SKIP]${NC} 无权限创建 $LOG_DIR，跳过"
fi

# 3. 软链接到 /usr/local/bin
echo -e "${YELLOW}[3/4]${NC} 软链接到 $INSTALL_DIR ..."
if [ -w "$INSTALL_DIR" ]; then
    for script in "$TOOLKIT_DIR/bin"/*.sh; do
        name=$(basename "$script" .sh)
        ln -sf "$script" "$INSTALL_DIR/$name"
        echo "  ✓ $name"
    done
    echo -e "${GREEN}[OK]${NC} 已创建软链接"
else
    echo -e "${YELLOW}[SKIP]${NC} 无权限写入 $INSTALL_DIR，跳过"
    echo "      提示: 用 sudo bash setup.sh 或直接调用 bin/*.sh"
fi

# 4. 运行测试
echo -e "${YELLOW}[4/4]${NC} 运行测试..."
if [ -f "$TOOLKIT_DIR/tests/test_health_check.sh" ]; then
    bash "$TOOLKIT_DIR/tests/test_health_check.sh" || true
fi

echo ""
echo -e "${GREEN}==========================================="
echo "  ✅ 安装完成！"
echo "===========================================${NC}"
echo ""
echo "快速开始："
echo "  bash bin/health_check.sh"
echo ""
echo "或安装后直接调用："
echo "  health_check"