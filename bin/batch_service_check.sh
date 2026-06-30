#!/bin/bash

SERVICE=(
    "nginx"
    "postgresql"
    "redis"
    "docker"
    "sshd"
)

# ========== 2. 定义颜色 ==========
GREEN='\033[0;32m'   # 绿色 = 运行中
RED='\033[0;31m'     # 红色 = 已停止
NC='\033[0m'         # 重置颜色

# ========== 3. 输出标题 ==========
echo "=========================================="
echo "       批量服务状态检查"
echo "=========================================="

# ========== 4. 遍历服务列表 ==========
for service in "${SERVICE[@]}"; do
    if systemctl is-active --quiet $service; then
        echo -e "${GREEN}$service is running${NC}"
    else
        echo -e "${RED}$service is not running${NC}"
    fi
done

echo "=========================================="
echo "       批量服务状态检查完成"
echo "=========================================="