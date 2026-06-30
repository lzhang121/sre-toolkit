#!/bin/bash
# ===============================================
# lib/notify.sh - 告警通知（钉钉/Webhook/邮件）
# 用法: source lib/notify.sh
# ===============================================

# 钉钉机器人 Webhook URL（请替换为实际的）
DINGTALK_WEBHOOK="${DINGTALK_WEBHOOK:-https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN}"
DINGTALK_SECRET="${DINGTALK_SECRET:-YOUR_SECRET}"

# 邮件配置
SMTP_HOST="${SMTP_HOST:-smtp.example.com}"
SMTP_PORT="${SMTP_PORT:-25}"
ALERT_EMAIL="${ALERT_EMAIL:-ops@example.com}"

# === 钉钉通知 ===
notify_dingtalk() {
    local title=$1
    local content=$2
    
    # 构造 JSON
    local payload=$(cat <<EOF
{
    "msgtype": "markdown",
    "markdown": {
        "title": "${title}",
        "text": "## ${title}\n\n${content}\n\n> 时间: $(date '+%Y-%m-%d %H:%M:%S')"
    }
}
EOF
)
    
    # 发送请求（需要 curl）
    if command -v curl &>/dev/null; then
        curl -s -X POST \
            -H "Content-Type: application/json" \
            -d "$payload" \
            "$DINGTALK_WEBHOOK" >/dev/null 2>&1
    else
        echo "WARN: curl not found, skip dingtalk notify" >&2
    fi
}

# === 通用 Webhook 通知 ===
notify_webhook() {
    local url=$1
    local content=$2
    
    if [ -z "$url" ]; then
        echo "ERROR: webhook URL is empty" >&2
        return 1
    fi
    
    local payload=$(cat <<EOF
{
    "timestamp": "$(date +%s)",
    "level": "alert",
    "message": "${content}",
    "host": "$(hostname)"
}
EOF
)
    
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$url" >/dev/null 2>&1
}

# === 邮件通知（需要 mail 命令） ===
notify_email() {
    local subject=$1
    local content=$2
    
    if command -v mail &>/dev/null; then
        echo "$content" | mail -s "$subject" "$ALERT_EMAIL"
    else
        echo "WARN: mail command not found, skip email notify" >&2
    fi
}

# === 统一告警入口 ===
alert() {
    local level=$1      # info/warn/error
    local title=$2
    local content=$3
    
    case "$level" in
        info)  echo -e "\033[0;34m[INFO]\033[0m $title: $content" ;;
        warn)  echo -e "\033[0;33m[WARN]\033[0m $title: $content"; notify_dingtalk "[WARN] $title" "$content" ;;
        error) echo -e "\033[0;31m[ERROR]\033[0m $title: $content"; notify_dingtalk "[ERROR] $title" "$content" ;;
        *)     echo "$title: $content" ;;
    esac
}