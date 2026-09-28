#!/usr/bin/env bash
# 显式 init_log；无权限时失败，不降级到共享 /tmp。
LOG_DIR=${LOG_DIR:-/var/log/sre-toolkit}
LOG_FILE=${LOG_FILE:-$LOG_DIR/sre-toolkit.log}
LOG_LEVEL=${LOG_LEVEL:-INFO}
init_log() {
    (umask 077; mkdir -p -- "$LOG_DIR" && touch -- "$LOG_FILE")
}
write_log() {
    local level=$1 timestamp message
    shift
    timestamp=$(date -u +%FT%TZ) || return
    message=$*
    message=${message//$'\n'/\\n}
    message=${message//$'\r'/\\r}
    printf '%s [%s] %s\n' "$timestamp" "$level" "$message" >> "$LOG_FILE"
}
log_debug() { if [[ $LOG_LEVEL == DEBUG ]]; then write_log DEBUG "$@"; fi; }
log_info() { write_log INFO "$@"; }
log_warn() { write_log WARN "$@"; }
log_error() { write_log ERROR "$@"; }
# 只清理本工具的历史归档，永不删除当前文件；外部使用 logrotate 负责轮转。
rotate_log() {
    local keep_days=${1:-30}
    [[ $keep_days =~ ^[0-9]{1,4}$ && -d $LOG_DIR ]] || { echo '错误: 日志目录或保留天数无效' >&2; return 2; }
    find "$LOG_DIR" -maxdepth 1 -type f -name 'sre-toolkit.log.*.gz' ! -path "$LOG_FILE" -mtime "+$keep_days" -delete
}
