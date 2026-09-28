#!/usr/bin/env bash
# 隔离测试：不启停真实服务、不访问远程主机、不发送告警。
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
passed=0
expect() {
    local expected=$1 actual=0
    shift
    "$@" >"$tmp/output" 2>&1 || actual=$?
    if [[ $actual != "$expected" ]]; then
        printf 'FAIL: expected=%s actual=%s command=' "$expected" "$actual"
        printf '%q ' "$@"; printf '\n'; cat "$tmp/output"; exit 1
    fi
    passed=$((passed+1))
}
for script in "$root"/bin/*.sh "$root"/lib/*.sh "$root"/setup.sh "$root"/tests/*.sh; do expect 0 bash -n "$script"; done
expect 2 bash "$root/bin/service_control.sh"
expect 2 bash "$root/bin/service_control.sh" '-bad' start
expect 2 bash "$root/bin/service_control.sh" nginx delete
expect 0 bash "$root/bin/service_control.sh" --dry-run nginx restart
expect 2 bash "$root/bin/grade.sh" '1+99'
expect 2 bash "$root/bin/grade.sh" 101
expect 0 bash "$root/bin/grade.sh" 080
grep -q 'B' "$tmp/output"
mkdir -p "$tmp/source space" "$tmp/backups" "$tmp/mock"
printf 'restore me\n' > "$tmp/source space/file"
expect 0 env BACKUP_DIR="$tmp/backups" bash "$root/bin/backup.sh" "$tmp/source space"
archives=("$tmp/backups/"*.tar.gz)
mkdir "$tmp/restore"
tar -xzf "${archives[0]}" -C "$tmp/restore"
cmp "$tmp/source space/file" "$tmp/restore/source space/file"
expect 2 env BACKUP_DIR="$tmp/source space/nested" bash "$root/bin/backup.sh" "$tmp/source space"
cat > "$tmp/mock/tar" <<'MOCK'
#!/usr/bin/env bash
exit 7
MOCK
chmod +x "$tmp/mock/tar"
expect 7 env PATH="$tmp/mock:$PATH" BACKUP_DIR="$tmp/backups" bash "$root/bin/backup.sh" "$tmp/source space"
[[ $(find "$tmp/backups" -type f | wc -l) -eq 1 ]]
rm "$tmp/mock/tar"
cat > "$tmp/mock/systemctl" <<'MOCK'
#!/usr/bin/env bash
exit 5
MOCK
cat > "$tmp/mock/timeout" <<'MOCK'
#!/usr/bin/env bash
[[ ${@: -1} == 80 ]]
MOCK
chmod +x "$tmp/mock/"*
expect 5 env PATH="$tmp/mock:$PATH" bash "$root/bin/service_control.sh" nginx restart
expect 1 env PATH="$tmp/mock:$PATH" bash "$root/bin/batch_service_check.sh"
printf '# comment\nlocalhost 80 web\r\nlocalhost 81 closed' > "$tmp/hosts"
expect 1 env PATH="$tmp/mock:$PATH" CONCURRENCY=1 bash "$root/bin/batch_service_check.sh" "$tmp/hosts"
grep -q '\[OK\].*web' "$tmp/output"
grep -q '\[FAIL\].*closed' "$tmp/output"
printf 'localhost 99999 bad\n' > "$tmp/hosts"
expect 2 env PATH="$tmp/mock:$PATH" bash "$root/bin/batch_service_check.sh" "$tmp/hosts"
printf 'localhost 80 web\n' > "$tmp/hosts"
expect 0 env PATH="$tmp/mock:$PATH" bash "$root/bin/batch_service_check.sh" "$tmp/hosts"
expect 2 env CONCURRENCY=0 bash "$root/bin/batch_service_check.sh" "$tmp/hosts"
printf '127.0.0.1 - - [28/Sep/2026:00:00:00 +0000] "GET / HTTP/1.1" 200 1\n127.0.0.1 - - [28/Sep/2026:00:00:00 +0000] "GET /error HTTP/1.1" 503 2' > "$tmp/access.log"
expect 0 bash "$root/bin/log_analyzer.sh" "$tmp/access.log"
grep -q '总请求数: 2' "$tmp/output"
grep -q '5xx 错误数: 1' "$tmp/output"
printf '\nbroken\n' >> "$tmp/access.log"
expect 1 bash "$root/bin/log_analyzer.sh" "$tmp/access.log"
: > "$tmp/empty.log"
expect 0 bash "$root/bin/log_analyzer.sh" "$tmp/empty.log"
# 受控采集器验证 Linux 检查逻辑，不依赖宿主机当前负载。
real_awk=$(command -v awk)
export REAL_AWK="$real_awk"
cat > "$tmp/mock/uname" <<'MOCK'
#!/usr/bin/env bash
echo Linux
MOCK
cat > "$tmp/mock/sleep" <<'MOCK'
#!/usr/bin/env bash
exit 0
MOCK
cat > "$tmp/mock/getconf" <<'MOCK'
#!/usr/bin/env bash
echo 4
MOCK
cat > "$tmp/mock/df" <<'MOCK'
#!/usr/bin/env bash
[[ ${TEST_DF_FAIL:-0} == 0 ]] || exit 1
printf 'Filesystem Blocks Used Available Use%% Mounted\n/dev/test 100 20 80 20%% /\n'
MOCK
cat > "$tmp/mock/awk" <<'MOCK'
#!/usr/bin/env bash
case ${@: -1} in
    /proc/stat)
        if [[ -f $TEST_STATE ]]; then echo '200 150'; else echo '100 60'; touch "$TEST_STATE"; fi;;
    /proc/meminfo) echo 30;;
    /proc/loadavg) echo "${TEST_LOAD:-0.25}";;
    *) exec "$REAL_AWK" "$@";;
esac
MOCK
chmod +x "$tmp/mock/"*
expect 0 env PATH="$tmp/mock:$PATH" TEST_STATE="$tmp/cpu1" bash "$root/bin/health_check.sh"
expect 1 env PATH="$tmp/mock:$PATH" TEST_STATE="$tmp/cpu2" TEST_LOAD=2 bash "$root/bin/health_check.sh"
expect 2 env PATH="$tmp/mock:$PATH" TEST_STATE="$tmp/cpu3" TEST_DF_FAIL=1 TEST_LOAD=2 bash "$root/bin/health_check.sh"
grep -q UNKNOWN "$tmp/output"
expect 2 env PATH="$tmp/mock:$PATH" CPU_THRESHOLD=invalid bash "$root/bin/health_check.sh"
expect 2 bash -c 'source "$1/lib/notify.sh"; unset DINGTALK_WEBHOOK; notify_dingtalk title text' bash "$root"
expect 2 bash -c 'source "$1/lib/notify.sh"; notify_webhook http://example.invalid text' bash "$root"
expect 0 bash -c 'source "$1/lib/log.sh"; log_debug hidden' bash "$root"
# 安装冲突不会覆盖已有文件，也不会提前安装部分脚本。
mkdir "$tmp/install"
printf 'keep\n' > "$tmp/install/service_control"
expect 1 env INSTALL_DIR="$tmp/install" bash "$root/setup.sh"
[[ $(cat "$tmp/install/service_control") == keep && ! -e $tmp/install/backup ]]
# JSON 编码与通知失败：curl 完全替换，绝不连接接收端。
if ! command -v python3 >/dev/null; then
    cat > "$tmp/mock/python3" <<'MOCK'
#!/usr/bin/env bash
exec python "$@"
MOCK
fi
cat > "$tmp/mock/curl" <<'MOCK'
#!/usr/bin/env bash
while (($#)); do
    if [[ $1 == --data-binary ]]; then printf '%s' "$2" > "$TEST_PAYLOAD"; shift; fi
    shift
done
printf '%s' "${TEST_RESPONSE:-{\"errcode\":0\}}"
exit "${TEST_CURL_EXIT:-0}"
MOCK
chmod +x "$tmp/mock/"*
expect 0 env PATH="$tmp/mock:$PATH" TEST_PAYLOAD="$tmp/payload" bash -c 'source "$1/lib/notify.sh"; notify_webhook https://example.invalid "$2"' bash "$root" $'quoted "hello"\nnew line\\slash'
expect 0 env PATH="$tmp/mock:$PATH" python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["message"] == sys.argv[2]' "$tmp/payload" $'quoted "hello"\nnew line\\slash'
expect 22 env PATH="$tmp/mock:$PATH" TEST_PAYLOAD="$tmp/payload" TEST_CURL_EXIT=22 bash -c 'source "$1/lib/notify.sh"; notify_webhook https://example.invalid text' bash "$root"
expect 1 env PATH="$tmp/mock:$PATH" TEST_PAYLOAD="$tmp/payload" TEST_RESPONSE='{"errcode":123}' DINGTALK_WEBHOOK=https://example.invalid DINGTALK_SECRET= bash -c 'source "$1/lib/notify.sh"; notify_dingtalk title text' bash "$root"
expect 0 env PATH="$tmp/mock:$PATH" TEST_PAYLOAD="$tmp/payload" TEST_RESPONSE='{"errcode":0}' DINGTALK_WEBHOOK=https://example.invalid DINGTALK_SECRET= bash -c 'source "$1/lib/notify.sh"; notify_dingtalk title text' bash "$root"
expect 2 env DINGTALK_WEBHOOK=https://example.invalid DINGTALK_SECRET=secret bash -c 'source "$1/lib/notify.sh"; notify_dingtalk title text' bash "$root"
mkdir "$tmp/logs"
touch "$tmp/logs/other.log" "$tmp/logs/sre-toolkit.log" "$tmp/logs/sre-toolkit.log.old.gz"
touch -t 202001010000 "$tmp/logs/"*
expect 0 env LOG_DIR="$tmp/logs" LOG_FILE="$tmp/logs/sre-toolkit.log" bash -c 'source "$1/lib/log.sh"; rotate_log 30' bash "$root"
[[ -f $tmp/logs/other.log && -f $tmp/logs/sre-toolkit.log && ! -e $tmp/logs/sre-toolkit.log.old.gz ]]
expect 0 bash -c 'source "$1/lib/color.sh"; print_info "$2"' bash "$root" 'literal\ntext'
grep -Fq 'literal\ntext' "$tmp/output"
printf 'PASS: %s assertions; archive restore and output checks passed\n' "$passed"
