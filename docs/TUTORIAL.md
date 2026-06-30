# 📚 SRE Toolkit 教程

本教程介绍 SRE Toolkit 中各个工具的设计思路和使用方法，适合 Shell 脚本学习者参考。

---

## 📑 目录

- [工具1：健康检查脚本](#工具1健康检查脚本)
- [工具2：日志分析脚本](#工具2日志分析脚本)
- [工具3：批量服务检查](#工具3批量服务检查)
- [设计模式](#设计模式)
- [扩展开发](#扩展开发)

---

## 工具1：健康检查脚本

### 解决的问题

SRE 日常需要快速判断服务器状态。手动执行 `top`、`free`、`df` 效率低，输出格式不一致。

### 核心设计

```
1. 函数化：每个检查项封装为独立函数（check_cpu / check_memory / ...）
2. 颜色化：用 ANSI 转义码标识状态（绿=正常 / 黄=警告 / 红=错误）
3. 阈值化：通过变量配置告警阈值
4. 易扩展：新增检查项只需写一个函数
```

### 关键代码讲解

```bash
# 1. CPU 检查 - 用 top + awk 提取使用率
cpu_usage=$(top -bn1 | grep "Cpu" | tr ',' '\n' | grep "us" | awk '{print $1}')

# 解读:
# top -bn1          一次性输出（batch mode，-n 1 表示只执行1次）
# grep "Cpu"        过滤出 CPU 行
# tr ',' '\n'       把逗号变成换行符，方便按行处理
# grep "us"         提取 us 行（user CPU time）
# awk '{print $1}'  打印第一个字段（数值）
```

### 进阶改造

```bash
# 增加配置化阈值
CPU_THRESHOLD=${CPU_THRESHOLD:-80}
if (( $(echo "$cpu_usage > $CPU_THRESHOLD" | bc -l) )); then
    print_warn "CPU 使用率: ${cpu_usage}%"
fi
```

---

## 工具2：日志分析脚本

### 解决的问题

Nginx access.log 动辄几十 MB，肉眼无法快速分析。需要自动统计关键指标。

### 核心模式："管道 + 文本处理三剑客"

```
日志文件 → awk(提取字段) → sort(排序) → uniq(去重计数) → sort -rn(按次数倒序) → head(取Top N)
```

### 关键命令链

```bash
# 统计 Top 10 IP
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -10

# 解读:
# awk '{print $1}'   提取每行的第1列（IP）
# sort                按字母排序（让相同 IP 相邻）
# uniq -c             合并相邻重复并计数
# sort -rn            按数字倒序（r=reverse, n=numeric）
# head -10            取前10行
```

### 为什么用 `uniq -c` 而不是 `wc -l`？

- `wc -l` 只能统计总行数
- `uniq -c` 能告诉你每种值的出现次数

---

## 工具3：批量服务检查

### 解决的问题

几十台主机的服务端口是否存活？手动一个个 `telnet` 太慢。

### 核心设计：并发探测

```bash
# 用 & 启动后台任务，用 wait 等待
for host in $(cat hosts.txt); do
    check_service "$host" &
done
wait
```

### 进阶：用 nc 而不是 telnet

```bash
# nc 更轻量，且大多数 Linux 默认安装
nc -z -w 3 $host $port
# -z  扫描模式（不发送数据）
# -w 3 超时时间 3 秒
```

---

## 设计模式

### 模式1：函数库 + 主脚本分离

```
bin/script.sh       # 主流程（thin script）
lib/colors.sh       # 通用函数（color / log / notify）
```

**好处**：
- 代码复用（多个脚本共享 lib/）
- 易于维护（修改 lib/ 不影响 bin/）
- 测试友好（lib/ 可以单独测）

### 模式2：参数化

```bash
LOG_FILE=${1:-/var/log/nginx/access.log}
THRESHOLD=${CPU_THRESHOLD:-80}
```

**好处**：
- 默认值让脚本开箱即用
- 环境变量可灵活覆盖

### 模式3：彩色输出 + 日志双轨

```bash
# 屏幕：彩色，人类可读
echo -e "${GREEN}[OK]${NC} 检查通过"

# 日志：纯文本，机器可解析
echo "$(date) [INFO] 检查通过" >> /var/log/check.log
```

---

## 扩展开发

### 如何添加新工具？

1. 在 `bin/` 创建新脚本，参考现有脚本结构
2. 在 `lib/` 添加可复用函数（如有）
3. 在 `tests/` 添加测试
4. 更新 `README.md` 工具清单
5. 更新 `docs/CHANGELOG.md`

### 脚本模板

```bash
#!/bin/bash
# ===============================================
# <工具名> - <功能简介>
# 作者: <your-name>
# 版本: 0.1.0
# ===============================================

set -euo pipefail

# 加载函数库
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/color.sh"
source "${SCRIPT_DIR}/../lib/log.sh"

# === 配置 ===
DEFAULT_VALUE="..."

# === 函数 ===
main() {
    print_title "工具名称 v0.1.0"
    # 你的逻辑
    print_ok "完成"
}

main "$@"
```

### 代码规范

- 使用 4 空格缩进
- 函数名用 `snake_case`
- 常量用 `UPPER_SNAKE_CASE`
- 关键逻辑加中文注释
- 错误信息用 `print_error` 输出到 stderr

---

## 参考资料

- [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
- [Bash 高级编程](https://tldp.org/LDP/abs/html/)
- [SRE Google 运维解密](https://sre.google/sre-book/)

---

*遇到问题？提交 Issue 一起讨论。*