#!/bin/bash
# ===============================================
# 服务器健康检查脚本
# 作者：SRE学员
# 功能：检查服务器关键指标（CPU、内存、磁盘、负载）
# ===============================================

# ========== 1. 颜色定义 ==========
# \033[0;31m 是 ANSI 转义码，用于输出彩色文字
# RED = 红色，用于警告
# GREEN = 绿色，用于正常状态
# YELLOW = 黄色，用于提示
# NC = No Color，用于重置颜色（结束彩色输出）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# ========== 2. 定义检查函数 ==========

# --- CPU 检查函数 ---
# 思路：
# 1. 用 top 命令获取 CPU 使用率
# 2. 根据阈值判断是否需要警告
check_cpu() {
    # 方法：用 tr 把逗号转换成换行，再提取 us 字段
    # top 输出: %Cpu(s):  0.6 us,  0.6 sy,  0.0 ni, 98.8 id, ...
    cpu_usage=$(top -bn1 | grep "Cpu" | tr ',' '\n' | grep "us" | awk '{print $1}')

    # 检查是否为空或非数字
    if [ -z "$cpu_usage" ] || ! [[ "$cpu_usage" =~ ^[0-9.]+$ ]]; then
        echo -e "${YELLOW}[信息] 无法获取 CPU 数据${NC}"
        return
    fi

    # 判断阈值：使用率 > 80% 则警告
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}[警告] CPU 使用率: ${cpu_usage}%${NC}"
    else
        echo -e "${GREEN}[正常] CPU 使用率: ${cpu_usage}%${NC}"
    fi
}

# --- 内存检查函数 ---
# 思路：
# 1. 用 free -m 获取内存信息（单位 MB）
# 2. 计算使用率 = 已用 / 总计 * 100
# 3. 根据阈值判断
check_memory() {
    # free -m: 以 MB 为单位显示内存
    # 输出格式：
    #               total        used        free      shared  buff/cache   available
    # Mem:           1838         456         234          12         147         1234
    # Swap:          2047           0         2047

    # awk 'NR==2': 打印第 2 行（Mem 行）
    # $2 是 total，$3 是 used
    mem_total=$(free -m | awk 'NR==2 {print $2}')
    mem_used=$(free -m | awk 'NR==2 {print $3}')

    # scale=2: 保留 2 位小数
    # 计算百分比：已用 / 总计 * 100
    mem_percent=$(echo "scale=2; $mem_used * 100 / $mem_total" | bc)

    # 判断阈值：使用率 > 80% 则警告
    if (( $(echo "$mem_percent > 80" | bc -l) )); then
        echo -e "${RED}[警告] 内存使用率: ${mem_percent}% (${mem_used}/${mem_total}MB)${NC}"
    else
        echo -e "${GREEN}[正常] 内存使用率: ${mem_percent}% (${mem_used}/${mem_total}MB)${NC}"
    fi
}

# --- 磁盘检查函数 ---
# 思路：
# 1. 用 df -h / 获取根目录磁盘使用情况
# 2. 提取使用率百分比
# 3. 根据阈值判断
check_disk() {
    # df -h /: 查看根目录磁盘使用情况
    # 输出格式：
    # Filesystem      Size  Used Avail Use% Mounted on
    # /dev/sda1       50G   20G   30G  40% /

    # awk 'NR==2 {print $5}': 打印第 2 行第 5 列，即 "40%"
    # sed 's/%//': 去掉 % 符号，转成数字 40
    disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

    # 磁盘可以直接用整数比较（不需要 bc）
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${RED}[警告] 磁盘使用率: ${disk_usage}%${NC}"
    else
        echo -e "${GREEN}[正常] 磁盘使用率: ${disk_usage}%${NC}"
    fi
}

# --- 系统负载检查函数 ---
# 负载平均值：1分钟、5分钟、15分钟的平均负载
check_load() {
    # uptime: 显示系统运行时间、登录用户数、负载平均值
    # 输出格式： xx:xx:xx up xx days, xx:xx,  x users,  load average: 0.52, 0.58, 0.59

    # awk -F'load average:' '{print $2}'
    # -F: 指定分隔符为 "load average:"
    # $2: 打印分隔后的第 2 部分，即 " 0.52, 0.58, 0.59"
    load_avg=$(uptime | awk -F'load average:' '{print $2}')
    echo -e "${GREEN}[正常] 系统负载: ${load_avg}${NC}"
}

# ========== 3. 主程序 ==========

# 输出报告头部
echo "=========================================="
echo "       服务器健康检查报告"
# date '+%Y-%m-%d %H:%M:%S' 格式化输出时间
# %Y=年，%m=月，%d=日，%H=时，%M=分，%S=秒
echo "       $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# 调用各个检查函数
check_cpu      # 检查 CPU
check_memory    # 检查内存
check_disk      # 检查磁盘
check_load      # 检查负载

echo ""
echo "检查完成"
