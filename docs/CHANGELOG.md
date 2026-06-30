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