#!/bin/bash
# ===============================================
# lib/log.sh - 日志记录工具
# 用法: source lib/log.sh
# ===============================================

# 默认日志目录
LOG_DIR="${LOG_DIR:-/var/log/sre-toolkit}"
LOG_FILE="${LOG_DIR}/sre-toolkit.log"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# 初始化日志目录
init_log() {
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR" 2>/dev/null || {
            # 权限不足时降级到 /tmp
            LOG_DIR="/tmp/sre-toolkit"
            LOG_FILE="${LOG_DIR}/sre-toolkit.log"
            mkdir -p "$LOG_DIR"
        }
    fi
}

# 写入日志
write_log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 写入日志文件
    echo "${timestamp} [${level}] ${message}" >> "$LOG_FILE" 2>/dev/null
}

# 各级别日志函数
log_debug() {
    [ "$LOG_LEVEL" = "DEBUG" ] && write_log "DEBUG" "$@"
}

log_info() {
    write_log "INFO" "$@"
}

log_warn() {
    write_log "WARN" "$@"
}

log_error() {
    write_log "ERROR" "$@"
}

# 清理旧日志（保留最近 N 天）
rotate_log() {
    local keep_days=${1:-30}
    find "$LOG_DIR" -name "*.log" -mtime +$keep_days -delete 2>/dev/null
}