#!/bin/bash

# 期望输出示例：
# ./backup.sh /home/user/data
# 备份成功: /tmp/backup/data_20260623_103045.tar.gz

PATH=$1
BACKUP_DIR="/tmp/backup"

if [ -z "$PATH"]; then
    echo "请输入要备份的文件或目录"
    exit 1
fi

if [ ! -e "$PATH" ]; then
    echo "文件或目录不存在"
    exit 1
fi

if [ -d "$PATH" ]; then
    tar -czf "$BACKUP_DIR/$(basename $PATH)_$(date +%Y%m%d_%H%M%S).tar.gz" "$PATH"
else
    cp "$PATH" "$BACKUP_DIR/$(basename $PATH)_$(date +%Y%m%d_%H%M%S)"
fi

echo "备份完成: $BACKUP_DIR/$(basename $PATH)_$(date +%Y%m%d_%H%M%S)"