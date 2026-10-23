# GeneData 外部工具数据 API Phase B：批量解析与不可变 Manifest

日期：2026-10-22

实施分支：`feature/external-file-batches-v1`

基线：`origin/feat/homepage-portal-redesign`（创建分支时为 `d9c801e`）

## 1. 本阶段交付

Phase B 只修改数据仓库，向 GeneScreen、CodonW 或其他远程工具提供统一的批量文件解析协议：

- 按稳定 `file_code` 批量选择；
- 按文件名及 accession、assembly、dataset、role、format 组合条件解析；
- 按 accession、assembly 或 dataset 一次选入全部匹配文件，可用 `roles` 限定类型；
- 重名且缺少限定条件时返回多个候选，不进行猜测；
- `strict=true` 时，只要存在歧义或缺失就不创建批次；
- `strict=false` 时，保存成功解析的文件，并把未解析项写入批次摘要；
- 创建不可变的数据库快照，提供 JSON 和 TSV Manifest；
- 支持 `Idempotency-Key`，相同 Token、相同键、相同请求只创建一个批次；
- 限制选择器数量、文件数量、总字节数和请求频率；
- Manifest 只对创建该批次的 Token 可见，不输出服务器物理路径。

本阶段不创建 ZIP/TAR、不在数据仓库执行分析程序，也不把文件主动推送到外部服务器。外部工具读取 Manifest 后，仍通过每个条目的 `content_url` 使用 HTTPS 下载或流式读取文件。

## 2. 权限

新增最小权限：

- `batch:create`：解析选择器并创建批次；
- `batch:read`：读取自己创建的批次和 Manifest。

如工具随后下载文件，还必须具有既有的 `file:read` 权限。内部材料同时要求 Token 的 `access_tier=internal`。不可见文件统一表现为 `not_found`，避免泄露内部文件是否存在。

## 3. API

### 3.1 只解析，不创建

```bash
curl --fail-with-body --silent --show-error \
  -X POST "$GENEDATA_BASE_URL/gd/api/v1/file-batches/resolve/" \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "selectors": [
      {"file_name": "genome.fasta", "accession": "IR64"}
    ],
    "datasets": ["DS_IR64_REFERENCE_V1"],
    "roles": ["genome_fasta", "annotation_gff3"],
    "strict": true
  }'
```

响应按 `resolved`、`ambiguous`、`missing`、`blocked` 分类。重复文件名的候选只返回稳定编号和业务元数据，不返回物理路径。

### 3.2 创建不可变批次

```bash
curl --fail-with-body --silent --show-error \
  -X POST "$GENEDATA_BASE_URL/gd/api/v1/file-batches/" \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  -H "Idempotency-Key: genescreen-run-20261022-001" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GeneScreen IR64 inputs",
    "file_codes": ["FILE000001", "FILE000013", "FAI_14"],
    "strict": true
  }'
```

成功时返回 `batch_id`、文件数、总字节数、`snapshot_sha256`、过期时间以及两个 Manifest URL。首次创建返回 201；幂等重放返回 200；相同幂等键配不同请求返回 409。

### 3.3 读取 Manifest

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/file-batches/$BATCH_ID/manifest/"

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/file-batches/$BATCH_ID/manifest.tsv" \
  -o "$BATCH_ID.manifest.tsv"
```

快照保存 `file_code`、`file_name`、`content_version`、文件大小、SHA-256、格式、角色及业务归属。若源 `DataFile` 的版本发生变化，旧 Manifest 返回 409 `snapshot_stale`，不会静默指向新内容；过期后返回 410 `batch_expired`。

## 4. 默认限额与环境变量

| 环境变量 | 默认值 | 含义 |
| --- | ---: | --- |
| `GENEDATA_BATCH_RATE` | `30/minute` | 单 Token/IP 请求频率 |
| `GENEDATA_BATCH_MAX_SELECTORS` | `1000` | 单请求选择器数量 |
| `GENEDATA_BATCH_MAX_FILES` | `1000` | 单批次文件数量 |
| `GENEDATA_BATCH_MAX_BYTES` | `536870912000` | 单批次总字节数（500 GiB） |
| `GENEDATA_BATCH_TTL_HOURS` | `24` | Manifest 有效期 |

生产环境应根据带宽、并发下载量和 GeneScreen 实际任务规模调整，不能只提高文件数而不评估总字节数。

## 5. 部署步骤

本次增加迁移 `files.0026_external_file_batch`。生产变更必须在维护窗口执行：

```bash
python manage.py check --deploy --settings=filemanager.settings_production
python manage.py migrate --plan
python manage.py migrate
python manage.py showmigrations files
```

然后签发同时具有 `batch:create`、`batch:read`、`file:read` 的专用工具 Token，执行一组小文件 Canary：解析、创建、JSON Manifest、TSV Manifest、逐文件下载和 SHA-256 校验。禁止在日志或验证记录中保存完整 Token。

## 6. 验收状态

- 已实现：数据模型、迁移、权限、批量解析、严格/宽松创建、幂等、不变快照、JSON/TSV Manifest、配额和 OpenAPI 1.2.0 契约。
- 开发机已验证：`python manage.py test` 共 495 项通过、1 项跳过；Phase B 与 OpenAPI 定向测试 9 项通过；`makemigrations --check --dry-run` 无未生成迁移；`python manage.py check` 无问题；`git diff --check` 通过。
- 开发机待验收：尚未针对开发机真实材料签发 Token 并执行 curl，因为本分支未向开发数据库应用迁移。
- 生产待验收：数据库备份、迁移、Token 签发、真实多材料 Canary、下载带宽与审计日志。

Phase B 完成不等于 GeneScreen 已经完成分析。它解决的是远程工具稳定、批量、可审计地取得输入文件清单；任务提交、结果回传、归档打包属于后续阶段。
