---
title: GeneData 开发、部署与运维手册
status: active
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes:
  - ci_gate.md
  - GeneData_生产环境部署与开发环境准备手册.md
  - GeneData_外部工具数据API_运维手册.md
  - management_command_lifecycle.md
---

# GeneData 开发、部署与运维手册

本文是唯一活动运维入口。它不绑定某个提交号、服务器目录或一次发布；具体生产参数由部署负责人
在发布执行单中临时填写，执行单不作为长期架构文档提交。

## 1. 状态边界

- 代码通过、migration 已应用、数据已验收、生产已发布是四个独立结论。
- 开发机或 CI 通过不能替代生产只读预检、备份、迁移和真实数据验收。
- 历史 migration 不得修改；schema 变化只能新增 migration。
- 发布必须固定提交或 tag，记录包校验值，并能恢复数据库、代码和配置。
- 任何生产写入、migration、服务切换和回滚都需要人工批准。

## 2. 开发与 CI 门禁

后端：

```bash
cd django2
python manage.py check
python manage.py makemigrations --check --dry-run files
python manage.py test files --noinput
python manage.py check --deploy --fail-level ERROR --settings=filemanager.settings_production
```

前端：

```bash
cd vue_project
npm ci
npm test
npm run build
```

文档任务至少运行引用检查、UTF-8 检查和 `git diff --check`。不得通过删除测试、弱化断言或
无条件 skip 绕过失败。

## 3. 发布流程

### 3.1 发布前

1. 检查工作区，只打包已批准且已验证的提交。
2. 记录 Git commit/tag、依赖锁文件和发布包 SHA-256。
3. 执行第 2 节门禁，确认没有未评审 migration。
4. 列出所需环境变量，但不把值写入仓库或执行单。
5. 在生产执行数据库、文件目录、Nginx、进程和磁盘空间的只读预检。
6. 准备数据库备份、文件清单或快照，以及经过验证的恢复命令。

### 3.2 生产部署

1. 进入批准的维护窗口，停止写入或切换到维护模式。
2. 备份数据库和相关配置，记录备份校验值。
3. 部署固定版本并安装锁定依赖。
4. 使用生产设置执行 `check --deploy` 和 `showmigrations`。
5. 先查看 migration plan，经人工确认后再执行 `migrate`。
6. 对数据导入先执行 dry-run，再执行 apply，并保存报告。
7. 执行文件关系、文件实体和权限检查。
8. 收集静态文件，运行 `nginx -t`，再按现场批准命令切换服务。
9. 验证健康检查、关键页面、权限边界、下载、Range 和真实数据关系。

仓库文档不固化 `systemctl` 服务名、生产绝对路径或数据库凭据；这些值由生产环境配置提供。

### 3.3 回滚

失败时停止继续写入，保存日志和报告，然后按已批准顺序恢复旧代码与配置、恢复数据库或撤销本次
数据发布状态。不要通过删除物理科研文件代替回滚。回滚后重新执行健康、权限和数据一致性检查。

## 4. 外部数据 API 运维

相关命令的参数以 `python manage.py <command> --help` 和代码为准。核心活动命令包括：

```text
issue_data_access_token
list_data_access_tokens
revoke_data_access_token
publish_datafiles
publish_external_datasets
audit_public_fasta_indexes
audit_external_api_readiness
```

要求：

- Token 只展示一次完整值；日志只能记录内部 ID 或非敏感前缀。
- 发布命令先 dry-run，再 apply；保存 manifest、SHA-256、操作者和报告。
- 每次返回文件或上下游对象时重新授权，不得暴露 `file_path`。
- Nginx 内部文件位置必须是 `internal`，Range、HEAD 和权限均需验收。
- 监控 `/gd/api/v1/` 的状态码、响应字节和耗时，不记录 Authorization 头。

## 5. JBrowse 运维

索引命令仍是活动能力：

```bash
cd django2
python manage.py build_jbrowse_indexes --assembly-id <id> --dry-run
python manage.py build_jbrowse_indexes --assembly-id <id> --apply
```

批量构建必须使用 checkpoint 和报告；只有 `remaining_count=0` 且
`failed_checkpoint_count=0` 才能描述为本批完成。上线前还需核对参考序列、注释 seqid、索引新鲜度、
文件授权、Nginx Range 和浏览器实际加载。

## 6. Management command 生命周期

机器可读事实来源是 `files.management.command_lifecycle.COMMAND_LIFECYCLE`。新增或删除命令时必须同步
更新该注册表并通过回归测试。没有源码调用者不能证明生产脚本、定时任务或人工流程未使用该命令。

## 7. 安全与验收

- 生产必须显式提供安全配置，缺失时安全失败。
- 当前已知安全例外见 `docs/security_exceptions.md`，在关闭条件满足前不得宣称 Security Gate 全部通过。
- 生产验收至少覆盖 migration、真实数据、逐对象授权、文件访问、回滚可用性和审计报告。
- 生产证据应保存到受控发布系统或工单；仓库只保留长期有效的规则，不累积逐次执行记录。
