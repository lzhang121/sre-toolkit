#!/usr/bin/env bash
# 可选依赖 python3（JSON 编码）和 curl；不会自动发送告警。
notify_dingtalk() {
    [[ -n ${DINGTALK_WEBHOOK:-} ]] || { echo '错误: 未配置 DINGTALK_WEBHOOK' >&2; return 2; }
    # 不假装支持未实现的加签；配置了 secret 时明确拒绝发送。
    [[ -z ${DINGTALK_SECRET:-} ]] || { echo '错误: 尚不支持钉钉加签机器人' >&2; return 2; }
    local payload response
    payload=$(python3 -c 'import json,sys; print(json.dumps({"msgtype":"markdown","markdown":{"title":sys.argv[1],"text":sys.argv[2]}}))' "$1" "$2") || return
    response=$(curl --silent --show-error --fail --connect-timeout 5 --max-time 15 \
        --proto '=https' -H 'Content-Type: application/json' --data-binary "$payload" -- "$DINGTALK_WEBHOOK") || return
    printf '%s' "$response" | python3 -c 'import json,sys; r=json.load(sys.stdin); sys.exit(0 if r.get("errcode")==0 else 1)'
}
notify_webhook() {
    local url=${1:-} content=${2:-} payload
    [[ $url == https://* ]] || { echo '错误: Webhook 必须为 HTTPS URL' >&2; return 2; }
    payload=$(python3 -c 'import json,socket,sys,time; print(json.dumps({"timestamp":int(time.time()),"level":"alert","message":sys.argv[1],"host":socket.gethostname()}))' "$content") || return
    curl --silent --show-error --fail --connect-timeout 5 --max-time 15 \
        --proto '=https' -H 'Content-Type: application/json' --data-binary "$payload" -- "$url" >/dev/null
}
notify_email() {
    [[ -n ${ALERT_EMAIL:-} && $ALERT_EMAIL != -* ]] || { echo '错误: 未配置有效 ALERT_EMAIL' >&2; return 2; }
    printf '%s\n' "$2" | mail -s "$1" "$ALERT_EMAIL"
}
alert() {
    local level=$1 title=$2 content=$3
    printf '[%s] %s: %s\n' "$level" "$title" "$content" >&2
    case $level in
        info) return 0;;
        warn|error) notify_dingtalk "[$level] $title" "$content";;
        *) echo '错误: 不支持的告警级别' >&2; return 2;;
    esac
}
