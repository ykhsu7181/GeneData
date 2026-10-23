# GeneData 外部工具数据 API Phase C：批量归档任务与受保护下载

日期：2026-10-22

实施分支：`feature/external-file-archives-v1`

基线：`origin/feat/homepage-portal-redesign`，提交 `7153a1a`

## 1. 目标与边界

Phase C 在 Phase B 不可变 Manifest 上增加异步 ZIP/TAR.GZ 归档。GeneScreen 等远程工具可以先创建批次，再请求生成单个归档包，轮询任务状态，最后通过 HTTPS 下载。

本阶段只负责文件交付，不在数据仓库运行 GeneScreen、CodonW 或其他分析程序，不接收分析结果，也不把服务器物理路径暴露给调用方。

## 2. 为什么使用持久化 Worker

Web API 只把任务写入数据库并返回 202，绝不在请求线程中打包大文件。独立 Worker 使用以下命令处理队列：

```bash
python manage.py process_external_archive_jobs --once
python manage.py process_external_archive_jobs --limit 10 --recover-stale-minutes 60
```

生产环境应由 systemd、Supervisor 或周期调度器重复执行第二条命令。任务状态保存在 `ExternalFileArchive`，Web 服务或 Worker 重启不会丢失排队记录；中断任务可有限次重新排队，超过重试次数后明确失败。

## 3. 权限

- `batch:archive`：为自己创建的批次排队归档任务；
- `batch:read`：查询归档任务状态；
- `batch:download`：下载归档成品。

Worker 打包时会重新检查 Token 是否有效、是否仍有 `batch:archive`，并重新检查每个文件的当前访问策略。下载时再次检查 `batch:download`、Token access tier 和材料策略。Token 撤销或材料撤权后不能通过旧任务绕过权限。

## 4. API 调用

### 4.1 创建归档任务

```bash
curl --fail-with-body --silent --show-error \
  -X POST "$GENEDATA_BASE_URL/gd/api/v1/file-batches/$BATCH_ID/archives/" \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  -H "Idempotency-Key: genescreen-archive-20261022-001" \
  -H "Content-Type: application/json" \
  -d '{"format":"zip"}'
```

支持 `zip` 和 `tar.gz`。首次排队返回 202；相同 Token、幂等键和请求返回原任务及 200；同一幂等键配不同请求返回 409。

### 4.2 查询状态

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/file-archives/$ARCHIVE_ID/"
```

状态包括 `queued`、`running`、`ready`、`failed`、`expired`。仅当状态为 `ready` 时返回 `download_url` 和归档 SHA-256。

### 4.3 下载

```bash
curl --fail-with-body --location --continue-at - \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/file-archives/$ARCHIVE_ID/content/" \
  -o "$ARCHIVE_ID.zip"

sha256sum "$ARCHIVE_ID.zip"
```

下载响应包含 `ETag`、`X-Archive-SHA256`、`Content-Length` 和 `Accept-Ranges: bytes`。Django 完成授权后通过 `X-Accel-Redirect` 交给 Nginx 发送文件，支持大文件 Range 和断点续传。

## 5. 归档内容与完整性

每个包固定包含：

- `manifest.json`；
- `manifest.tsv`；
- `files/0001-FILE_CODE/original-name` 形式的材料文件。

文件名只作为归档成员名，稳定编号和顺序保证重名文件不会覆盖。打包过程流式读取文件，不把大文件载入内存；每个源文件在写入归档时重新计算 SHA-256，若与不可变快照不一致则整个任务失败，不发布部分归档。最终归档通过临时文件生成，完成后原子移动，并再次计算归档 SHA-256。

## 6. 配置

| 环境变量 | 默认值 | 说明 |
| --- | ---: | --- |
| `GENEDATA_EXTERNAL_ARCHIVE_ROOT` | 开发默认 `django2` 同级 `protected_archives` | 归档物理根目录；生产配置中为必填变量 |
| `GENEDATA_EXTERNAL_ARCHIVE_INTERNAL_URI` | `/_protected_external_archives/` | Nginx internal URI |
| `GENEDATA_ARCHIVE_TTL_HOURS` | `24` | 归档有效期 |
| `GENEDATA_ARCHIVE_MAX_INPUT_BYTES` | `536870912000` | 单任务最大输入，500 GiB |
| `GENEDATA_ARCHIVE_MIN_FREE_BYTES` | `10737418240` | 打包后必须保留的空间，10 GiB |
| `GENEDATA_ARCHIVE_WORKER_MAX_ATTEMPTS` | `2` | Worker 中断后的最大尝试次数 |
| `GENEDATA_ARCHIVE_MAX_ACTIVE_PER_TOKEN` | `3` | 单 Token 排队或运行中的任务上限 |
| `GENEDATA_ARCHIVE_MAX_ACTIVE_PER_BATCH` | `2` | 单批次排队或运行中的任务上限 |

Nginx 示例：

```nginx
location /_protected_external_archives/ {
    internal;
    alias /srv/genedata/protected_archives/;
    gzip off;
}
```

## 7. 清理

清理命令默认只报告，不删除：

```bash
python manage.py cleanup_external_archives
python manage.py cleanup_external_archives --apply
```

`--apply` 删除过期成品并将数据库状态改为 `expired`。应先确认备份、归档根目录和待清理数量，再由定时任务执行。

## 8. 部署门禁

本阶段新增迁移 `files.0027_external_file_archive`。生产部署前必须：

1. 备份数据库并检查 `migrate --plan`；
2. 创建独立归档数据卷，验证所有者、权限和可用空间；
3. 配置 Nginx internal alias 并执行 `nginx -t`；
4. 部署和启动单并发 Worker，确认日志不记录 Token 或物理路径；
5. 签发最小权限 Canary Token；
6. 使用两个小文件验证 ZIP、TAR.GZ、状态轮询、Range、SHA-256、过期清理和撤权阻断；
7. 观察磁盘、任务失败率、队列长度和下载带宽后再扩大并发。

## 9. 验收状态

- 已实现：持久化任务模型、排队 API、幂等、ZIP/TAR.GZ 流式 Worker、双重权限复核、源文件及成品 SHA-256、状态 API、受保护下载、失效恢复、过期清理和 OpenAPI 1.3.0。
- 开发机已验证：全部 API 测试 188 项通过；完整 Django 测试 504 项通过、1 项跳过；迁移一致性、默认设置检查、提供必填环境变量后的生产设置检查以及差异格式检查通过。
- 开发机待验收：尚未向开发数据库应用迁移，也未配置真实 Nginx alias/常驻 Worker，因此真实材料 curl 与 Range 交付留待部署前集成环境验收。
- 生产待验收：数据库迁移、归档卷、Nginx 映射、Worker 服务、真实多材料 Canary 和容量监控。
