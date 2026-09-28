#!/usr/bin/env bash
# 兼容旧测试入口。
set -euo pipefail
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/test_toolkit.sh"
