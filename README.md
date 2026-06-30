<h1 align="center">🛠️ SRE Toolkit</h1>

<p align="center">
  <strong>面向 SRE 工程师的运维自动化工具箱</strong><br>
  Shell 脚本 + Python 工具，覆盖服务器巡检、日志分析、监控告警等日常运维场景
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Shell-Bash-4EAA25?logo=gnu-bash&logoColor=white" alt="Bash">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Linux-Ubuntu-E95420?logo=ubuntu&logoColor=white" alt="Linux">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
</p>

---

## 📖 项目简介

`SRE Toolkit` 是一个面向 SRE 工程师的运维自动化工具集，所有脚本都经过实际环境验证，可直接用于生产环境的日常运维工作。

**适合人群**：
- 🎯 准备求职 SRE / DevOps / 运维开发岗位的同学
- 🔧 需要快速搭建运维工具的小团队
- 📚 Shell 脚本学习者（每个脚本都有详细中文注释）

---

## ✨ 功能特性

| 模块 | 工具 | 功能 |
|------|------|------|
| **健康检查** | `health_check.sh` | CPU/内存/磁盘/负载实时监控 |
| **日志分析** | `log_analyzer.sh` | Nginx/Apache 日志统计分析 |
| **批量检查** | `batch_service_check.sh` | 多主机并发服务存活探测 |
| **配置备份** | `backup.sh` | 关键配置自动备份（带时间戳） |
| **评分检测** | `grade.sh` | 服务健康评分（百分比） |
| **综合工具** | `service_control.sh` | 服务启停 + 状态查询 |

---

## 🚀 快速开始

### 环境要求

```bash
# Linux / macOS / WSL
bash --version   # >= 4.0
```

### 克隆仓库

```bash
git clone https://github.com/<your-username>/sre-toolkit.git
cd sre-toolkit
```

### 运行示例

```bash
# 服务器健康检查
chmod +x bin/health_check.sh
./bin/health_check.sh

# 日志分析
./bin/log_analyzer.sh /var/log/nginx/access.log

# 批量服务检查
./bin/batch_service_check.sh hosts.txt
```

---

## 📂 目录结构

```
sre-toolkit/
├── bin/                  # 可执行脚本（核心工具）
│   ├── health_check.sh
│   ├── log_analyzer.sh
│   ├── batch_service_check.sh
│   ├── backup.sh
│   ├── grade.sh
│   └── service_control.sh
├── lib/                  # 函数库（被 bin/ 调用）
│   ├── color.sh          # 颜色输出
│   ├── log.sh            # 日志记录
│   └── notify.sh         # 告警通知（钉钉/邮件）
├── configs/              # 配置文件模板
│   └── hosts.example.txt
├── tests/                # 测试脚本
│   └── test_health_check.sh
├── docs/                 # 文档
│   ├── CHANGELOG.md
│   └── TUTORIAL.md
├── README.md
├── LICENSE
└── .gitignore
```

---

## 📋 工具清单

### 1. `bin/health_check.sh` - 服务器健康检查

**功能**：检查 CPU、内存、磁盘、负载，给出彩色报告

```bash
$ ./bin/health_check.sh
==========================================
       服务器健康检查报告
       2026-07-01 00:30:00
==========================================

[正常] CPU 使用率: 12.5%
[正常] 内存使用率: 45.20% (1200/2650MB)
[正常] 磁盘使用率: 30%
[正常] 系统负载:  0.52, 0.58, 0.59

检查完成
```

### 2. `bin/log_analyzer.sh` - 日志分析

**功能**：统计请求数、状态码、Top IP、Top 路径、错误数

```bash
$ ./bin/log_analyzer.sh access.log
==========================================
       日志分析报告
==========================================
总请求数: 12345
状态码统计:
   4523 200
    123 404
     12 500
Top 10 请求 IP:
   523 192.168.1.100
   ...
```

### 3. `bin/batch_service_check.sh` - 批量服务检查

**功能**：并发检测多台主机的服务端口

```bash
$ ./bin/batch_service_check.sh configs/hosts.example.txt
```

更多工具请查看 `bin/` 目录。

---

## 🎯 实战场景

### 场景 1：每日巡检

```bash
# 添加到 crontab，每天 9 点执行
0 9 * * * /path/to/sre-toolkit/bin/health_check.sh >> /var/log/health_check.log 2>&1
```

### 场景 2：日志异常告警

```bash
# 检测到 5xx 错误时发送告警
./bin/log_analyzer.sh access.log | grep -E "5xx 错误数: [^0]"
```

### 场景 3：服务上线验证

```bash
# 部署后批量验证服务可用性
./bin/batch_service_check.sh production_hosts.txt
```

---

## 🛠️ 技术栈

- **Shell**: Bash 4.0+
- **核心命令**: `awk`, `sed`, `grep`, `find`, `top`, `free`, `df`
- **工具链**: Git, Bash, Cron

---

## 📚 学习路径

如果你想学习这些脚本是怎么写出来的，可以参考：

1. [Shell 基础教程](https://github.com/<your-username>/sre-journey)（学习笔记仓库）
2. [docs/TUTORIAL.md](docs/TUTORIAL.md) - 工具开发教程

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

- 🐛 Bug 反馈：[Issues](../../issues)
- 💡 功能建议：[Issues](../../issues)
- 📝 文档改进：[Pull Requests](../../pulls)

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

## 🙏 致谢

- 参考了 Google SRE 运维解密、SRE Workbook
- 工具设计参考了多个生产环境 SRE 团队的最佳实践

---

<p align="center">
  Made with ❤️ by an aspiring SRE engineer
</p>