---
title: GeneData API 使用说明
status: active
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes:
  - GeneData_外部工具数据API_使用手册.md
---

# GeneData API 使用说明

本文只记录当前活动 API 的稳定入口和使用边界。机器可读的外部 API 契约以
`/gd/api/v1/openapi.json` 为准；实现状态以代码和自动化测试为准。

## 1. 数据与安全边界

- 文件统一使用 `DataFile` 表示，归属关系使用 `FileRelation` 表示。
- API 不得返回服务器物理路径 `file_path`。
- 页面下载统一使用 `/gd/api/files/data-files/<file_id>/download/`。
- 外部工具读取文件统一使用 `/gd/api/v1/files/<file_id>/content/`。
- 私有对象、未发布对象和无权访问对象必须在服务端重新授权，不能依赖前端隐藏。
- `GenomeFile` 已从当前模型状态删除；历史 migration 仅用于重建历史数据库状态。

## 2. 页面 API

| 功能 | 主要接口 | 主要数据来源 |
| --- | --- | --- |
| 首页 Portal | `GET /gd/api/warehouse/dashboard/` | `Assembly / Species / Annotation / Accession` |
| 数据一览 | `GET /gd/api/files/query/data-overview/` | `DataFile + FileRelation` |
| DataFile 详情 | `GET /gd/api/files/data-files/<id>/detail/` | `DataFile + FileRelation` |
| DataFile 下载 | `GET /gd/api/files/data-files/<id>/download/` | `DataFile` |
| Assembly 详情 | `GET /gd/api/files/assemblies/<id>/summary/` | Assembly 及关联实体 |
| Accession 文件 | `GET /gd/api/files/accessions/<accession>/files/` | `DataFile + FileRelation` |
| Transcriptome 列表 | `GET /gd/api/files/query/transcriptome-list/` | 业务实体及文件关系 |
| Transcriptome 文件 | `GET /gd/api/files/query/transcriptome-files/` | `DataFile + FileRelation` |

复杂查询应放入 `django2/files/services/`，view 只负责参数、service 调用和响应。

## 3. 外部工具 API v1

契约入口：

```text
GET /gd/api/v1/openapi.json
GET /docs/api/
```

当前活动接口：

```text
GET /gd/api/v1/accessions/<accession>/
GET /gd/api/v1/accessions/<accession>/files/
GET /gd/api/v1/files/<file_id>/content/
GET /gd/api/v1/datasets/<dataset>/manifest/
GET /gd/api/v1/datasets/<dataset>/manifest.tsv
GET /gd/api/v1/assemblies/<assembly>/sequence/?sequence=<name>&start=<1-based>&end=<inclusive>
```

不要根据本文猜测响应字段；客户端应以 OpenAPI 契约为准。

### 3.1 Token

Token 只能通过环境变量或密钥管理器注入，不得写入脚本、仓库、命令历史或日志。

```bash
export GENEDATA_BASE_URL="https://example.org"
export GENEDATA_TOKEN="<token>"
```

PowerShell：

```powershell
$env:GENEDATA_BASE_URL = "https://example.org"
$env:GENEDATA_TOKEN = "<token>"
```

### 3.2 查询和下载

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/accessions/IR64/files/?role=genome&format=FASTA"

curl --fail-with-body --location \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  -o input.fasta \
  "$GENEDATA_BASE_URL/gd/api/v1/files/14/content/"

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/assemblies/ASM_IR64/sequence/?sequence=Chr01&start=1&end=120"
```

调用方必须检查非 2xx 状态、响应校验值和内容长度。不要用忽略 `curl` 失败的管道继续分析。

## 4. 状态码

| 状态码 | 调用方处理 |
| --- | --- |
| `200/206` | 接收完整内容或 Range 内容，并校验响应 |
| `400` | 修正参数，不自动重试 |
| `401/403` | 停止任务并检查 Token、scope 和对象权限 |
| `404` | 核对标识符和发布状态；不要据此推断私有对象是否存在 |
| `409` | 停止任务，报告 Assembly 歧义或 FASTA/索引冲突 |
| `429` | 按 `Retry-After` 退避 |
| `5xx` | 有上限地重试并保留 request id |

## 5. 导入日志约定

导入命令至少记录命令、输入路径、dry-run、开始/结束时间以及 scanned、created、
updated、skipped、unmapped、error 等计数。真实数据导入必须先 dry-run，并保存报告和输入文件校验值。
