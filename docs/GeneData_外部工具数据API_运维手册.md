# GeneData 外部工具数据 API v1 运维手册

## 1. 责任边界与默认值

- Django 负责 Token、权限决策、Manifest 和 FASTA Region；Nginx 通过 internal location 发送完整文件与 Range。
- 生产 settings：`filemanager.settings_production`；生产根目录：`/home/labuser/rdcheng/gd`。
- 默认限流：metadata `120/minute`、content `30/minute`、manifest `30/minute`、sequence `60/minute`。
- 默认 Region 上限：`GENEDATA_SEQUENCE_MAX_BASES=1000000`，响应上限 `GENEDATA_SEQUENCE_MAX_RESPONSE_BYTES=1100000`。
- 日志、工单、聊天和命令历史中不得出现明文 Token。

## 2. 发布前门禁

1. 候选包来源为固定 Git commit，外层 SHA-256 与包内清单全部通过。
2. 生产主机、维护窗口、执行人和回滚人明确；不得使用文档中的占位主机。
3. 已确认活动服务 PID、cwd、Python、settings、端口和 Nginx 配置归属。
4. 数据库、活动后端、Nginx 配置均已备份并记录 SHA-256。
5. `manage.py check --deploy --settings=filemanager.settings_production` 通过；migration plan 仅含已评审迁移。
6. `/_protected_manual_files/` 与 `/_protected_derived_data/` 为 `internal`，alias 指向真实目录，`nginx -t` 通过。
7. Canary 的 IR64 文件、Dataset、Assembly 与索引状态均完成只读核对。

任一门禁失败即停止，不运行 `--apply`，不切换服务。

## 3. Token 生命周期

先 dry-run，再 apply；明文只在签发时显示一次，应直接写入批准的 Secret Manager。

```bash
cd /home/labuser/rdcheng/gd/django2
python manage.py issue_data_access_token \
  --name production-canary-YYYYMMDD \
  --scope file:read --scope dataset:manifest --scope sequence:read \
  --access-tier public --expires-in-hours 2

python manage.py issue_data_access_token \
  --name production-canary-YYYYMMDD \
  --scope file:read --scope dataset:manifest --scope sequence:read \
  --access-tier public --expires-in-hours 2 --apply
```

盘点与撤销：

```bash
python manage.py list_data_access_tokens --include-inactive
python manage.py revoke_data_access_token --token-prefix '<exact-prefix>'
python manage.py revoke_data_access_token --token-prefix '<exact-prefix>' --apply
```

轮换顺序为“签发新 Token → 用新 Token 完成 200/206/Manifest/Region 验证 → 切换调用方 Secret → 撤销旧 Token → 验证旧 Token 返回 403”。常规服务 Token 应设置有效期；Canary Token 在验收结束后立即撤销。

## 4. 数据发布与审计

发布清单必须包含 `file_code`、`access_level`，建议附 `sha256`。以下操作默认 dry-run：

```bash
python manage.py publish_datafiles \
  --manifest /absolute/approved_publication.tsv \
  --output-dir /home/labuser/rdcheng/gd/audit_reports/external_api/canary

python manage.py publish_datafiles \
  --manifest /absolute/approved_publication.tsv \
  --published-by '<approved-user>' \
  --output-dir /home/labuser/rdcheng/gd/audit_reports/external_api/canary \
  --apply

python manage.py audit_public_fasta_indexes --assembly ASM_IR64
```

只有报告 `blocked=0`、FASTA 审计 `PASS`，且 Dataset 为 `visibility=public,status=released` 时才能进入 HTTP Canary。不得以数据库主键跨环境推断对象；使用 `file_code`、`dataset_code`、`assembly_code` 核对后再记录生产主键。

## 5. 监控与告警

每 5 分钟使用独立、最小权限监控 Token 依次检查：OpenAPI 200、IR64 accession 200、Manifest 200 且文件数符合基线、120 bp Region 200 且 `X-Coordinate-System=1-based-inclusive`。完整文件下载只在发布 Canary 执行，不用于高频探活。

建议从 Nginx access log 统计 `/gd/api/v1/`：

| 指标 | 告警条件 | 处置 |
| --- | --- | --- |
| 5xx 比例 | 5 分钟 > 1% 或连续 3 次探活失败 | 停止扩大流量，检查 Django/Nginx |
| 401/403 激增 | 相比 7 日同时间段 > 3 倍 | 检查 Token 轮换和异常调用 |
| 409 Region | 任意出现 | 检查 FASTA/FAI 选择、时效与映射 |
| 429 比例 | 5 分钟 > 5% | 确认调用方并发；评审后调整限流 |
| p95 延迟 | metadata > 1 s，Region > 3 s 持续 15 分钟 | 检查数据库、磁盘和上游代理 |
| 磁盘 | 数据卷可用 < 20% 或 inode < 10% | 停止新发布并清理已批准内容 |

访问日志建议记录 request id、路径模板、状态码、响应字节、耗时和 Token prefix/内部 token id；禁止记录 `Authorization` 头和完整查询敏感值。

## 6. 故障定位

```bash
nginx -t
pgrep -af 'manage.py|gunicorn|uwsgi'
python manage.py check --deploy --settings=filemanager.settings_production
python manage.py showmigrations files
python manage.py audit_public_fasta_indexes --assembly ASM_IR64
python manage.py list_data_access_tokens --include-inactive
```

- 401：请求未携带 Bearer Token。
- 403：Token 无效/撤销/过期，或缺 scope/access tier。
- 404：对象未发布、物理文件不在受保护根目录、关系缺失，或故意隐藏。
- 409：FASTA/FAI 缺失、歧义、损坏或 FAI 早于 FASTA。
- 206 未出现：检查客户端 Range、Nginx internal alias 和 gzip 是否关闭。

## 7. 回滚

1. 立即停止新 Canary 请求并撤销 Canary Token。
2. 将服务切回已备份的旧后端目录，恢复旧 Nginx 配置并执行 `nginx -t` 后 reload。
3. 数据库仅使用维护窗口前生成且已验证的备份恢复；不得用反向 migration 猜测回滚。
4. 若只需撤回数据，按审计记录将本次对象恢复到发布前状态，不删除物理文件；记录操作者、时间和对象代码。
5. 回滚后验证旧健康检查、旧下载路径和管理后台，再归档日志、备份哈希与事件时间线。

回滚触发条件：任何 5xx、权限绕过、非预期物理路径泄漏、错误文件内容/校验和、迁移异常，或无法在维护窗口内解释的 409。
