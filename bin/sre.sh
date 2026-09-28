#!/usr/bin/env bash
set -euo pipefail
source_path=$(readlink -f -- "${BASH_SOURCE[0]}")
root=$(cd -- "$(dirname -- "$source_path")/.." && pwd)
exec python3 "$root/tools/sre.py" "$@"
