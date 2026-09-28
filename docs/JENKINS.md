# Jenkins 集中运维部署指南

## 架构与支持范围

当前按单机 Jenkins 部署：Controller 管理任务和审批，内置节点（Built-In Node）运行 Ansible；Ansible 经 SSH 将固定脚本包送到目标主机；目标机执行后，经现有 SSH 连接返回结果。两条 Pipeline 使用 `agent any`，不要求 `master` 或 `sre-runner` 标签。无需新增 Jenkins 服务器，也无需目标机 Jenkins Agent、Git 或回调 HTTP 服务。

首要目标为 **AWS Amazon Linux 2023**，兼容设计覆盖 Rocky/Alma/RHEL 9。`amzn2023` 内核标识是 Amazon Linux 2023 的线索，最终以 `/etc/os-release` 为准。目标机使用 `/usr/bin/python3`（Python 3.9）；执行节点单独使用 Python 3.12 虚拟环境，不修改目标机系统 Python。

参考：[AWS Python 版本说明](https://docs.aws.amazon.com/linux/al2023/ug/python.html)、[Jenkins 执行隔离](https://www.jenkins.io/doc/book/security/controller-isolation/)、[Ansible 批次执行](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_strategies.html)。

支持的是人工/定时运维，不是监控守护进程。目标机的 CPU、内存信息仍可能在容器内反映宿主机；不提供 cgroup 配额监控。第一版不修改用户、防火墙、软件包或内核参数，也不自动重启主机。

## 1. 目标机准备（管理员一次性操作）

先确认系统：

```bash
cat /etc/os-release
/usr/bin/python3 --version
systemctl --version
```

在 Amazon Linux 2023 / Rocky 9 上准备依赖（不是业务任务的一部分）：

```bash
sudo dnf install -y python3 bash coreutils util-linux findutils procps-ng iproute tar gzip curl openssh-server sudo
```

新建专用 `sreops` 普通账号，由管理员配置其 `~/.ssh/authorized_keys`；目录权限 `0700`、文件 `0600`，所有者必须为该账号。账号不加入 `wheel`，不授予 `NOPASSWD: ALL`，不授予 Docker socket 权限。

你当前的 `ec2-user` 可以用于初次部署；若它已有完整 sudo，则给它新增受限 sudoers **不会撤销已有权限**。生产任务应使用单独的 `sreops`。为读取 system journal，可由管理员按需授予 `systemd-journal` 组权限；不授予时相关检查应报告权限/采集异常，而不是“没有错误”。

将审核过的仓库版本放到管理员控制的目录，执行：

```bash
sudo bash admin/install-maintenance.sh sreops
```

这只安装受限入口，不创建账号，不启停服务：

- `/usr/local/sbin/sre-maint`：固定入口，Python isolated mode，禁止额外命令行参数。
- `/opt/sre-toolkit-privileged`：root 所有代码，普通账号不可写。
- `/etc/sre-toolkit/policy.json`：root 所有策略，默认不允许任何维护对象。
- `/var/lib/sre-toolkit`：私有计划及全局维护锁。
- `/etc/sudoers.d/sre-toolkit`：仅允许该入口，安装时使用 `visudo` 检验。

升级需停用维护任务、由管理员部署；安装与执行使用同一文件锁。涉及高权限行为变更时必须同步递增 `sretoolkit/__init__.py` 的版本，旧计划不跨版本使用。不要让流水线更新该安装目录或策略。

策略示例（自行替换为已经确认的实际对象）：

```json
{
  "schema_version": 1,
  "services": {"nginx.service": ["start", "stop", "restart"]},
  "backups": [{"source": "/etc/nginx", "destination": "/var/backups/sre-toolkit"}],
  "cleanup": [{
    "directory": "/var/lib/app-archives",
    "pattern": "*.log.gz",
    "min_days": 14,
    "max_files": 100,
    "max_bytes": 1073741824
  }]
}
```

源路径、目标路径及其祖先必须已经存在、归 root 所有、无组/其他用户写权限且无符号链接。清理只针对 root 控制的历史归档目录；不开放 `/tmp`、应用用户可写目录或活动日志目录。不跨文件系统、不删除目录、不处理硬链接。服务白名单的 unit、执行程序及配置也必须由管理员控制，避免借服务启动运行可被普通账号替换的代码。

备份不提供数据库事务一致性；归档只保留在主机上，Jenkins 得到路径、大小和 SHA-256。管理员另行配置异地备份与保留策略。被强制中断的备份可能留下私有 `.backup.*` 暂存目录，不能视为完成的归档。

## 2. 单机 Jenkins 执行环境

在 Manage Jenkins → Nodes → Built-In Node → Configure 中，确认节点在线、执行器数量至少为 1，Usage 选择“Use this node as much as possible”。现有 2 个执行器可保留，不需要创建新节点或添加标签。`agent any` 使用可用节点；将来新增其他节点时，应改回明确的运维节点标签。

在这台 Jenkins 的实际运行环境准备 Python 3.12、Git、OpenSSH client、tar/gzip，以及独立虚拟环境。如果 Jenkins 运行在容器中，依赖必须安装到 Jenkins 容器镜像中，仅在宿主机安装不生效。下面由有权限的管理员在仓库目录执行：

```bash
python3.12 -m venv /opt/sre-runner-venv
/opt/sre-runner-venv/bin/pip install -r requirements-controller.txt
```

将 `/opt/sre-runner-venv/bin` 加入 Jenkins 服务的 PATH（或在节点 Environment variables 中设置 `PATH+SRE=/opt/sre-runner-venv/bin`），确保 Jenkins 服务账号有读取和执行权限。以该账号确认 `python3 --version` 和 `ansible-playbook --version`。当前锁定 [ansible-core 2.19.13](https://pypi.org/project/ansible-core/2.19.13/)，真实 Linux 集成尚需验收，升级补丁必须重新执行集成测试。

单机内置节点执行的脚本拥有 Jenkins 服务账号的权限，因此只运行可信运维仓库，限制 Configure/Replay 与仓库写入权限。后续需要隔离时，可以在同一台服务器用另一个 OS 账号运行独立 Agent，不一定需要购买新服务器，参见 [Jenkins Controller 隔离说明](https://www.jenkins.io/doc/book/security/controller-isolation/)。

2 个执行器代表可同时执行的 Jenkins 构建数量，不是被管理主机数；Ansible 仍可批量调度目标主机。同一 Job 禁止并发，巡检与维护两个不同 Job 可以并行；维护等待人工确认时会占用一个执行器，目标机的维护锁仍然生效。

AWS 网络建议：这台 Jenkins 放在可达目标私网地址的 VPC/网络中；目标安全组的 SSH 入站只接受 Jenkins 主机或跳板机，不需要开放给公网。示例清单的 `192.0.2.*` 是文档地址，不会自动发现或操作 AWS 实例；本工具不修改安全组、IAM 或 EC2 配置。

## 3. 清单与 SSH 凭据

当前 `configs/inventory.json` 已配置 `test` 环境的 `10.172.36.7`，SSH 端口为 `22`，用户为 `ec2-user`。主机标识直接使用 IP，无需额外起名字或创建分组；两条 Pipeline 的 `TARGETS` 默认值也是该 IP。新增机器时按相同格式增加 IP 条目，用户填写 `ec2-user`。

清单中的 `sre-test-ssh`、`sre-test-known-hosts`、`sre-test-ssh-config` 和 `sre-approvers` 仍是待配置的凭据 ID / 审批组名称，需要在 Jenkins 创建或替换为现有实际 ID；GitHub 拉代码凭据不能代替目标机 SSH 私钥。此文件不存密码或私钥，可在受保护的运维仓库中版本管理；控制其可见范围。新环境的结构参考 `configs/inventory.example.json`。

`TARGETS` 只接受已有别名/分组的逗号列表，如 `web` 或 `aws-test-01,aws-test-02`，不接受通配符、Ansible pattern、临时 IP。最多选择 50 台。主机集合在准备阶段固定，不会在审批后重新扩展分组。

每个环境创建三个 Jenkins Credentials，ID 对应清单中的字段：

| 字段 | 凭据类型 | 内容 |
|---|---|---|
| ssh_credential_id | SSH Username with private key | 专用运维密钥；连接用户名以清单为准 |
| known_hosts_credential_id | Secret file | 已核验的目标机及跳板机 SSH host keys |
| ssh_config_credential_id | Secret file | 管理员控制的 SSH 配置；直连可用空文件 |

Host key 必须经控制台、CMDB 或可信渠道校验；不要直接信任未经核验的 `ssh-keyscan` 输出。强制 `StrictHostKeyChecking=yes`，不会自动接受新主机密钥。`ProxyJump` 写在 SSH config 中；跳板机自己的密钥、known_hosts 和 IdentityFile 必须一并配置，不能假设目标机 `-i` 参数自动传给跳板机。不要开启 Agent Forwarding。

私钥文件由 Jenkins 临时绑定，不复制到目标主机或报告中。不要把 token 放进 HTTP URL、任务参数或 inventory。

## 4. 两个 Jenkins Job

安装/启用 Pipeline、Pipeline Input Step、Credentials Binding、SSH Credentials、Git、Timestamper。不再依赖 Pipeline Utility Steps：JSON 由 Python 标准库解析，使用已有的 `sh` 步骤传回必要字段，无需安装 JSON 插件或批准 Groovy JSON 解析器。HTML 报告直接归档下载，不要求 HTML Publisher，不需要放宽 Jenkins CSP。

创建两个 **Pipeline script from SCM** Job，使用同一受保护分支：

SCM 选择 Git，Repository URL 填写 `https://github.com/lzhang121/sre-toolkit.git`。两条流水线的 Checkout 阶段也已显式固定此地址；分支、检出版本相关扩展及 Git 凭据沿用 Job 的 SCM 配置。Job 中仍需填写仓库地址，供 Jenkins 首次读取 Jenkinsfile；这与目标机的 SSH 凭据是两套独立配置。

- 巡检：`jenkins/Jenkinsfile.inspect`
- 维护：`jenkins/Jenkinsfile.maintain`

不给调用者选择任意分支的参数；限制 Job Configure、Replay、仓库写入及凭据管理权限。Jenkins 管理员仍有最高权限，不能把 `input` 当作管理员隔离机制。配置清单中的 `approvers` 为实际 Jenkins 用户/外部组，替换示例 `sre-approvers`。

操作参数：

| 参数 | 说明 |
|---|---|
| ENVIRONMENT | 选择清单环境，模板提供 test/production；使用前配置对应环境 |
| TARGETS | 已知主机/分组，逗号分隔 |
| TASK | 固定任务 ID，无任意命令入口 |
| TASK_PARAMS | JSON 对象，键必须与任务要求完全一致 |
| APPLY | 仅维护任务；默认 false，仅生成预览 |

常用参数：

```text
basic          {}
directory      {"path":"/var/lib/myapp"}
service_status {"service":"nginx.service"}
dns            {"host":"example.com"}
tcp            {"host":"example.com","port":443}
http           {"url":"https://example.com/health"}
journal        {"service":"nginx.service","minutes":30}
access_log     {"path":"/var/log/nginx/access.log"}
service        {"service":"nginx.service","action":"restart"}
backup         {"source":"/etc/nginx"}
cleanup        {"directory":"/var/lib/app-archives","days":14}
```

基础巡检不读取任意日志内容，也不默认递归扫描目录。HTTP 只接受 2xx，不跟随重定向、不输出响应体。journal 只读取指定服务最近 1–1440 分钟、最多 200 条 error 级别记录。诊断 stdout/stderr 各限制 32 KiB，报告显示是否截断；进程列表只显示命令名，不采集完整命令行。

定时巡检在 Job 的 Build periodically 中配置，例如 `H 9 * * *`（使用 Jenkins 配置的时区）。默认不启用定时器，也不配置定时维护。

## 5. 审批、执行及失败行为

巡检默认并发 5 台，每项 60 秒，SSH 连接 10 秒；一台异常不影响其他主机。

维护预览展示固定主机集合、Git 提交、脚本包校验和、具体服务操作或清理文件及容量。所有目标预览成功才进入审批。`APPLY=true` 时，授权人员查看归档的 `index.html` 和 `approval.json` 后确认；30 分钟未确认则 Jenkins ABORTED。审批绑定摘要，执行前再次验证包内容及本地策略。

每台主机的计划自创建起有效 30 分钟，执行逐台进行。长时间备份可能使后续主机的计划过期，此时安全停止；应按预计耗时缩小批次，而不是自动延期或重新预览。单次清理最多 500 文件、计划最多 256 KiB，且受本机策略更小的限制。

执行前核验文件身份、大小与时间信息；变化则拒绝。开始实际维护后计划即被消费，失败或断连均不可重放。再次尝试必须创建新预览并重新确认。

第一台失败停止后续主机，后续记为 `skipped`。服务执行后核验 active/inactive；备份校验归档并返回 SHA-256。无自动回滚、重试或自动恢复备份。

目标机维护入口有独立超时，Jenkins 取消不能保证 root 进程瞬间停止。尤其 systemctl 已提交的 job 可能继续运行。断连/无响应的实际操作标记 `unknown`，先检查主机实际状态，不能直接重试。正常异常路径会归档部分结果；如果 Agent 被强制销毁/工作区丢失，则只能保留之前已归档的数据。

## 6. 报告与接口

每个主机 × 检查项都生成记录：

```text
schema_version, run_id, host, task, status, exit_code,
started_at, duration, changed, summary, metrics, artifact_refs
```

`changed` 为 true/false；无法确认是否改变时为 null。远端路径仅作为元数据，不按目标机返回的任意路径下载文件。`artifact_refs` 为未来本地附件保留，当前为空数组。

结果状态：ok、warning、error、unreachable、timeout、skipped、unknown。缺失/重复/格式错误的结果不能视为成功。构建映射为全正常 SUCCESS、仅告警 UNSTABLE、执行/连接/结果异常 FAILURE；取消或审批超时保持 ABORTED。

产物在 `reports/run/`：JSON 明细与汇总、CSV、静态 HTML、受限事件输出、运行 manifest 与审批文件。Jenkins 默认保留 30 天、最多 100 次构建。HTML 转义所有远端输出，CSV 防公式注入。日志内容可能含业务敏感数据，应按运维报告配置 Artifact 访问权限。

独立本机运行示例：

```bash
bash bin/sre.sh list --format json
bash bin/sre.sh run basic --format json
bash bin/sre.sh run journal --params '{"service":"nginx.service","minutes":30}'
bash bin/sre.sh plan service --run-id manual001 --params '{"service":"nginx.service","action":"restart"}' --format json
# 确认预览后，使用返回的 plan_id 和 digest；账号还必须在目标机 sudoers 中获得授权。
bash bin/sre.sh apply service --run-id manual001 --plan-id PLAN_ID --digest SHA256 --format json
```

本机 CLI 不提供 Jenkins 审批界面；有受限 sudo 权限的账号可以直接执行策略允许的维护。审批属于 Jenkins 操作流程，主机策略才是本地权限边界。

## 7. 验证与上线演练

```bash
bash tests/test_toolkit.sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

临时 Linux Docker 主机上运行双目标集成测试，测试容器为 privileged，仅用于隔离测试机，绝不放在生产节点：

```bash
SRE_TEST_BASE=amazonlinux:2023 bash tests/integration/run.sh
SRE_TEST_BASE=rockylinux:9 bash tests/integration/run.sh
```

测试创建唯一 Compose 项目，生成临时 SSH 密钥，从容器控制面提取 host keys，验证真实 SSH、受限 sudo、服务预览与执行、备份恢复内容、清理和首台失败停止；退出时清理该项目，报告在 `test_output/integration`。GitHub 的手动集成工作流执行两种镜像。容器不能完全替代真实 EC2 的 systemd、SELinux、网络和磁盘行为。

首次真实接入顺序：单台测试 EC2 只读巡检 → 两台测试机巡检报告 → 测试服务维护预览 → 人工确认维护 → 人为制造一台失败检查停止行为。验证通过后再配置生产环境和策略。

本次开发环境是 Windows + Git Bash：Shell 和跨平台 Python 隔离测试可执行；Linux flock/dir_fd 测试、真实 Ansible、目标机 systemd 和 Jenkins 输入审批需 Linux/真实环境验证。Docker 引擎未运行时不能宣称容器集成通过；Alma/RHEL 和真实 AWS 主机需独立记录验收结果。
