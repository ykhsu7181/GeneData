# 基因数据仓库 API 页面调用说明

本项目后端接口当前遵循 new-only 文件体系：

- 正式文件资产表：`DataFile`
- 正式文件归属表：`FileRelation`
- 历史归档表：`GenomeFile`
- 业务查询禁止返回 `legacy_genomefile`
- 业务下载禁止返回 `/genome-files/`
- 新下载入口统一使用 `/gd/api/files/data-files/<file_id>/download/`

## 页面与接口总览

| 页面 | 前端路由 | 主要接口 | 后端入口 | 查询 service | 数据来源 |
| --- | --- | --- | --- | --- | --- |
| 首页 Dashboard | `/dashboard` | `GET /gd/api/warehouse/dashboard/` | `files.dashboard_views.warehouse_dashboard` | `files.services.dashboard_service.build_dashboard_payload` | `Species / Accession / Sample / Dataset / DataFile / FileRelation` |
| 数据一览表 | `/data-overview` | `GET /gd/api/files/query/data-overview/` | `files.query_views.query_data_overview` | `files.services.query_service.get_data_overview_payload` | `Accession + DataFile + FileRelation` |
| 数据一览表文件抽屉 | `/data-overview` | `GET /gd/api/files/query/data-overview-files/` | `files.query_views.query_data_overview_files` | `files.services.query_service.get_data_overview_files_payload` | `DataFile + FileRelation` |
| 原始数据 | `/raw-data` | `GET /gd/api/files/query/raw-data/` | `files.query_views.query_raw_data` | `files.services.query_service.get_raw_data_payload` | `DataFile.description.raw_data + FileRelation` |
| Genome 数据列表 | `/genome-card` | `GET /gd/api/files/query/genome-list/` | `files.query_views.query_genome_list` | `files.services.query_service.get_genome_list_payload` | `Species / Accession / Assembly / DataFile / FileRelation` |
| Genome 文件抽屉 | `/genome-card` | `GET /gd/api/files/query/genome-files/` | `files.query_views.query_genome_files` | `files.services.query_service.get_genome_files_payload` | `DataFile + FileRelation` |
| Transcriptome 数据列表 | `/transcriptome-overview` | `GET /gd/api/files/query/transcriptome-list/` | `files.query_views.query_transcriptome_list` | `files.services.query_service.get_transcriptome_list_payload` | `Species / Accession / Assembly / Sample / DataFile / FileRelation` |
| Transcriptome 文件抽屉 | `/transcriptome-overview` | `GET /gd/api/files/query/transcriptome-files/` | `files.query_views.query_transcriptome_files` | `files.services.query_service.get_transcriptome_files_payload` | `DataFile + FileRelation` |
| Accession 合并页 | `/accession-card` | `GET /gd/api/files/accessions/<accession>/` | `files.views.accession_detail` | `files.services.file_relation_service` | `Accession / Assembly / Annotation / DataFile / FileRelation` |
| DataFile 下载 | 所有文件列表 | `GET /gd/api/files/data-files/<file_id>/download/` | `files.views.download_datafile` | - | `DataFile.file_path` |

## Dashboard 单聚合接口

首页只允许调用一个统计聚合接口：

```http
GET /gd/api/warehouse/dashboard/
```

返回内容包含：

- `summary`：总体统计
- `species_cards`：首页物种卡片
- `resource_summary`：数据资源统计
- `sub_population_distribution`：亚群分布
- `xi_distribution`：XI 分布
- `geo_distribution`：地理分布
- `recent_updates`：最近更新
- `hot_keywords`：热门搜索词

前端不应再自行并发多个接口后拼首页统计，避免口径不一致。

## 查询 Service 层约定

`files.query_views` 只做三件事：

1. 读取 HTTP 参数；
2. 调用 `files.services.query_service`；
3. 返回 `Response`。

具体查询逻辑按页面拆分：

- `dashboard_service.py`：首页统计聚合
- `data_overview_service.py`：数据一览表矩阵和明细
- `raw_data_service.py`：原始数据人工登记展示
- `genome_list_service.py`：Genome 数据列表和文件抽屉
- `transcriptome_list_service.py`：Transcriptome 数据列表和文件抽屉
- `file_relation_service.py`：统一文件归属查询，new-only

后续新增页面时，优先新增 service，再让 view 调用 service；不要把复杂 ORM 查询直接写进 view。

## 导入日志标准字段

导入命令日志统一使用 key-value 文本格式，并至少包含：

```text
command: import_raw_data_manifest
input_path: metadata/raw_data_manifest.normalized.tsv
dry_run: False
started_at: 2026-08-14T10:00:00
finished_at: 2026-08-14T10:00:02
scanned_count: 100
created_count: 20
reused_count: 80
updated_count: 5
skipped_count: 0
unmapped_count: 0
error_count: 0
```

命令可以继续输出业务专用字段，例如：

- `created_accession_count`
- `updated_accession_count`
- `created_datafile_count`
- `created_filerelation_count`
- `reused_filerelation_count`

这样既方便人工排查，也方便后续自动汇总。
