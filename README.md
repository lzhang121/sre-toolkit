# SRE Toolkit

面向 Linux 的小型运维 Shell 工具集。保留独立脚本入口，适合人工巡检及 Cron/CI 调用。当前提供隔离回归测试，**尚未经过你的生产环境验证**。

现已增加统一任务入口、Jenkins 巡检/维护流水线、Ansible SSH 分发和 JSON/CSV/HTML 报告。目标包含 **AWS Amazon Linux 2023** 与 Rocky/Alma/RHEL 9；完整部署和权限说明见 [Jenkins 集中运维指南](docs/JENKINS.md)。

```bash
bash bin/sre.sh list
bash bin/sre.sh run basic --format json
bash bin/sre.sh run service_status --params '{"service":"nginx.service"}'
```

`basic` 包含系统、存储、进程/服务、网络和日志元信息巡检。维护任务通过 `plan/apply` 和管理员预装的受限入口执行；Jenkins 默认仅预览，实际执行需要确认。旧脚本仍可独立运行。

## 运行环境

- Linux、Bash 4+、GNU coreutils、awk、tar、gzip；健康检查读取 `/proc`。
- 本机服务管理需要 systemd；远程端口检查需要 GNU `timeout` 和 Bash `/dev/tcp`。
- 可选通知需要 `curl`、`python3`；邮件需要已配置的 `mail`。
- macOS、原生 Windows 不属于运行支持范围。Git Bash 可运行隔离测试。

## 使用

```bash
bash bin/health_check.sh
DISK_PATH=/var CPU_THRESHOLD=85 bash bin/health_check.sh
CONCURRENCY=8 TIMEOUT=3 bash bin/batch_service_check.sh configs/hosts.example.txt
bash bin/batch_service_check.sh  # 兼容原有本机服务检查
bash bin/service_control.sh --dry-run nginx restart
bash bin/service_control.sh nginx status
BACKUP_DIR=/var/backups/sre-toolkit bash bin/backup.sh /etc/nginx
bash bin/log_analyzer.sh /var/log/nginx/access.log
bash bin/grade.sh 85
```

公开入口支持 `--help`（`inspect.sh` 是统一入口内部使用的采集脚本）。旧脚本配置通过环境变量传入，参考 [配置示例](configs/.env.example)；不会自动执行 `.env` 中的内容。新入口使用严格校验的 JSON 参数。

| 工具 | 行为与边界 |
|---|---|
| health_check | 1 秒 CPU 增量采样；内存按 MemAvailable；检查指定路径磁盘和 inode；1 分钟负载除以在线 CPU 数。超过阈值告警。容器中可能反映宿主机数据，不提供 cgroup 配额指标。 |
| batch_service_check | 清单格式为 `主机 端口 标签`；支持注释、CRLF、末行无换行；先验证全部配置，再按有限批次执行 TCP 连接；端口可连接不代表业务健康。 |
| backup | 普通文件/目录统一 tar.gz；默认私有权限；校验归档后原子发布；拒绝备份目录嵌套源目录；不覆盖历史备份、不自动清理。不是数据库一致性快照，备份变化中的文件可能失败。 |
| service_control | 校验服务名称和操作，支持 dry-run，原样返回 systemctl 退出码；不自动提权。 |
| log_analyzer | 标准 common/combined 格式，单次扫描，统计状态码和 Top IP/路径；单独报告无效行；空文件有效。高基数日志的内存占用随不同 IP/路径数增加。 |
| grade | 将人工输入的 0–100 分分级；并非自动服务健康评分。 |

## 退出状态

- 健康检查：`0` 正常，`1` 超阈值，`2` 参数/采集异常；采集异常优先。
- 批量检查：`0` 全部成功，`1` 至少一个失败，`2` 参数/依赖错误。
- 日志分析：`0` 全部可解析，`1` 存在无效行，`2` 输入错误。
- 备份、安装、通知：`0` 成功，非零失败；底层命令错误可原样传播。
- 服务控制：参数错误 `2`，执行后保留 systemctl 原始状态。

请检查退出码，而不是仅搜索输出中的“完成”。日志分析遇到 5xx 会统计但不会自动告警。

## 安装与验证

```bash
bash tests/test_toolkit.sh
INSTALL_DIR="$HOME/.local/bin" bash setup.sh
# 将 $HOME/.local/bin 加入 PATH 后使用 health_check 等命令
```

安装仅增加脚本执行权限并建立链接，不覆盖其他命令，不自动安装依赖或运行生产操作。仓库需保持在原位置。测试使用临时目录和模拟命令，不启停真实服务、不发网络告警。Linux CI 执行同一套测试及一次真实健康采集。

## 可选函数库

- `lib/color.sh`：非终端或设置 `NO_COLOR` 时关闭颜色。
- `lib/log.sh`：调用 `init_log` 初始化私有日志；失败不回退到共享 `/tmp`。`rotate_log` 只删除指定天数前的 `sre-toolkit.log.*.gz`，实际轮转交给系统 logrotate。
- `lib/notify.sh`：JSON 正确转义、连接/总时限、HTTP 失败传播；钉钉还检查业务 errcode。当前**不支持钉钉加签**，设置 `DINGTALK_SECRET` 会拒绝发送；通用 Webhook 只确认 HTTP 成功，不判断业务响应。SMTP 由本机 mail 配置。

设计取舍和上线检查见 [运维设计说明](docs/TUTORIAL.md)。
