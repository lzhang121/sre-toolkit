# 变更记录

## Jenkins 集中运维与 AWS 主机支持

- 增加统一任务注册表、JSON 协议、限时执行及系统/存储/服务/网络/日志检查。
- 增加 root 所有的受限维护入口、默认拒绝策略、绑定计划、逐台执行和防重放。
- 增加静态 inventory、Ansible SSH 分发、结果补齐及安全转义的 HTML/CSV/JSON 报告。
- 增加独立 Jenkins 巡检/维护 Pipeline、审批和归档；不连接实际生产环境。
- 增加 Amazon Linux 2023 / Rocky 9 双主机集成测试环境与部署指南。

## 2026-09-28

- 修复服务控制和备份无法正确执行；增加 dry-run、私有临时归档及校验后发布。
- 实现主机清单 TCP 有限并发探测，保留无参数本机服务检查。
- 重做 Linux 健康采集、阈值校验与异常退出状态，增加 inode 检查。
- 日志单次解析，异常行单独报告；限制日志归档清理范围。
- 通知 JSON 编码、超时和失败传播；明确不支持钉钉加签。
- 安装拒绝覆盖现有命令；补充隔离回归测试和 Linux CI。
- 明确 Linux 支持边界，移除未经证实的生产验证声明。

# 📝 更新日志

所有项目的变更都会记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 计划中
- Python 版本工具（健康检查 API 接口）
- VictoriaMetrics exporter 集成
- 钉钉告警机器人示例

---

## [0.1.0] - 2026-07-01

### 新增
- 🎉 项目初始化
- `bin/health_check.sh` - 服务器健康检查（CPU/内存/磁盘/负载）
- `bin/log_analyzer.sh` - Nginx 日志分析（状态码/IP/路径统计）
- `bin/batch_service_check.sh` - 多主机批量服务检查
- `bin/backup.sh` - 配置文件自动备份
- `bin/grade.sh` - 服务健康评分
- `bin/service_control.sh` - 服务启停管理
- `lib/color.sh` - 终端颜色输出函数库
- `lib/log.sh` - 日志记录函数库
- `lib/notify.sh` - 钉钉/Webhook 告警通知
- `configs/hosts.example.txt` - 主机列表示例
- `configs/.env.example` - 环境变量配置示例
- `tests/test_health_check.sh` - 健康检查测试
- 完整文档（README、TUTORIAL）

### 文档
- 中英文双语 README
- 项目结构说明
- 实战场景示例
- 贡献指南

---
