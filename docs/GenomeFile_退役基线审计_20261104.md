# GenomeFile 退役基线审计

审计日期：2026-11-04
仓库：`D:\gene_manage_system\gene_manage_system`
分支：`feature/external-tool-data-api-v1`

## 1. 审计范围

本次审计仅进行了静态读取与代码分析：

- 未修改或删除既有文件；
- 未执行 migration；
- 未连接或修改数据库；
- 未运行会创建测试数据库的 Django 测试；
- 未执行 management command；
- 未暂存、提交或推送代码；
- 未进行通用代码清理。

搜索排除了 `.git`、`node_modules`、`dist`、`__pycache__`、常见缓存、覆盖率、构建和产物目录。

搜索结果：

- `GenomeFile|genomefile|genome_file`：115 个文件、约 1015 行命中；
- 另外检查了 3 个仅通过相关 URL 或调用链关联的文件：`CodonCard.vue`、前端路由和 `unified-accession-page.test.mjs`；
- 很多 `genome_file` 只是 `DataFile` 变量名或 `GenomeFileSelectionError` 异常名，并非旧模型依赖。

## 2. Git 与规则加载状态

### 2.1 基线信息

1. 仓库根目录：`D:\gene_manage_system\gene_manage_system`
2. 实际读取的规则文件：`D:\gene_manage_system\gene_manage_system\AGENTS.md`
3. 当前分支：`feature/external-tool-data-api-v1`
4. `docs/ACTIVE_DOCUMENTS.md`：存在，当前为已暂存新增文件

`git status --short --branch` 摘要：

```text
## feature/external-tool-data-api-v1...origin/feature/external-tool-data-api-v1
A  AGENTS.md
A  docs/ACTIVE_DOCUMENTS.md
 M 开发环境启动流程.md
?? .artifacts/
?? .codex_tmp/
?? artifacts/
?? django2/derived_data/
?? 多个文档、metadata、实验记录及 manual_files_quarantine/
```

工作区并不干净。本次审计没有触碰上述已有变更。

### 2.2 本任务适用规则

- `DataFile + FileRelation` 是目标模型；
- 不得新增 `GenomeFile` 依赖、fallback、双读或双写；
- 必须区分当前实现、目标状态和待验证状态；
- 旧模型、410 兼容路由、测试、历史 migration、审计和回填工具需分别评估，不能批量删除；
- 历史 migration 必须保留；
- 生产数据是否完成迁移必须以数据库审计结果为准，不能从代码推断；
- 保护当前脏工作区，只读审计不产生代码变更。

`ACTIVE_DOCUMENTS.md` 没有登记正在执行的 GenomeFile 退役实施文档，因此本报告只给出基线和任务拆分，不把任何退役步骤标记为已完成。

## 3. 引用统计

| 分类 | 文件数 | 结论 |
|---|---:|---|
| A. 活动业务代码 | 18 | 4 个文件直接依赖旧模型；14 个主要是 DataFile 变量名或异常名 |
| B. API 和 URL | 2 | 旧 URL 仍存在但返回 410；CodonW 路由仍耦合旧类名 |
| C. Django Admin | 1 | 仍可真实查询 GenomeFile；禁止新增、修改和删除 |
| D. 前端 | 5 个关键词文件，另 2 个相关文件 | 未发现调用旧 GenomeFile API |
| E. 自动化测试 | 31 | 覆盖旧模型封存、无 fallback、`scan_files` 仅写新结构等边界 |
| F. management command / 审计 / 回填 | 25 | 15 个直接读取旧模型，其中 4 个仍能写 GenomeFile |
| G. 历史 migration | 11 | 必须永久保留 |
| H. 文档 | 20 | 历史设计、部署、规则和交接材料，不属于运行时依赖 |
| I. 数据库和生产数据依赖 | 2 个历史元数据文件 | 不能代表当前生产数据库状态 |

## 4. 活动读取入口

### 4.1 确认仍在读取 GenomeFile

| 文件及行号 | 当前用途 | 活动调用链 | 读旧表 | 写旧表 | 替代实现 | 删除判断、风险与阶段 |
|---|---|---|---:|---:|---|---|
| `django2/files/admin.py:11-32` | 注册只读 `GenomeFileAdmin` | 是，标准 Django Admin 已在 `filemanager/urls.py:46` 暴露 | 是 | 否 | `DataFile/FileRelation` 已存在，但没有等价 Admin 替换 | 不能直接删除；先确认运维是否仍依赖旧表查看。中风险，T3/T7 |
| `django2/files/models.py:757-853` | 旧模型定义；`get_all_organisms()` 查询旧表 | 模型活动；静态方法未找到调用者 | 是 | 模型允许写 | 新结构已存在 | 需完成生产数据审计并新增 `DeleteModel` migration。高风险，T7 |
| `django2/files/management/commands/*` | 人工运行的审计、迁移和修复入口 | 条件活动 | 是 | 部分命令是 | 多数命令用于迁移到新结构 | 生产迁移结束前不能整体删除 |

### 4.2 潜在或休眠读取

| 文件及行号 | 当前用途 | 活动调用链 | 删除风险与阶段 |
|---|---|---|---|
| `django2/files/serializers.py:116-120,159-163` | 对象没有 `prefetched_files` 时，通过反向 `files` 读取 GenomeFile | 当前 `accession_detail` 在 `views.py:4175-4182` 显式设置空列表，因此已知入口不会触发 | 潜在 fallback；T3 清除 |
| `django2/files/views.py:2607-2754` | `GenomeFileViewSet.paginated_overview` 仍预取旧 `files` 关系 | 当前未被 URL 映射；同名旧 URL 指向 410 adapter | 休眠旧代码；T3 单独删除并回归 |
| `django2/files/views.py:3180-3314` | `admin_login()` 返回语句后的旧 overview 实现 | 不可达 | 低风险候选，但应以独立变更处理 |
| `django2/files/models.py:821-844` | `get_all_organisms()` 查询旧表 | 未找到调用者 | 随模型在 T7 删除 |
| `django2/files/views.py:3350-3401` | `_analyze_uploaded_file()` 使用旧模型分类常量 | 未找到调用者，不查询旧表 | T3 清理候选 |

### 4.3 不读取旧数据但仍引用旧类型

- `django2/files/views.py:195-219`：活动 `accession_detail` 使用 `GenomeFile.FILE_CATEGORY_CHOICES` 构建兼容字段。数据来自 `DataFile/FileRelation`，但代码仍依赖旧模型常量；
- `django2/files/archive_views.py:19`：使用 `.none()` 作为 DRF queryset，所有动作返回 410，不读取数据行；
- `django2/files/views.py:374-408`：旧 CRUD 同样直接返回 410。

### 4.4 仅为 DataFile 变量名或业务概念的文件

以下命中不是旧模型依赖，不应为追求字符串归零而机械删除：

- `django2/files/assembly_api_views.py:14,100`
- `django2/files/query_views.py:33-706`
- `django2/files/services/accession_context.py:169-188`
- `django2/files/services/assembly_detail_service.py:7-63`
- `django2/files/services/external_api_readiness_service.py:180`
- `django2/files/services/external_sequence_service.py:22-302`
- `django2/files/services/fasta_index_service.py:19-149`
- `django2/files/services/file_relation_service.py:8-97`
- `django2/files/services/genome_list_service.py:8-230`
- `django2/files/services/jbrowse_config_service.py:15-342`
- `django2/files/services/jbrowse_index_service.py:17-79`
- `django2/files/services/jbrowse_location_service.py:89-91`
- `django2/files/services/query_service.py:11-38`
- `django2/files/services/reference_name_service.py:15-326`

这些文件中的 `genome_file` 代表 DataFile、基因组文件业务概念或选择异常。

## 5. 活动写入入口

### 5.1 普通 API 和 Admin

没有发现可成功写入 GenomeFile 的普通 HTTP 入口：

- 旧 ViewSet 的 `create/update/partial_update/destroy` 均返回 HTTP 410；
- 旧管理 API 上传、删除和批量删除接口均返回 410；
- Django Admin 明确禁止新增、修改和删除。

### 5.2 仍可写 GenomeFile 的 management command

| 文件及行号 | 写入行为 | 默认安全性 | 是否可直接删除 | 推荐阶段 |
|---|---|---|---|---|
| `cleanup_data.py:9-40` | `delete()` 旧行；修改 category 后 `save()` | 无 dry-run/apply 保护 | 暂不能直接删，先确认无调用 | T1 优先禁用或增加显式 apply，最终退役 |
| `link_genomefiles_to_accessions.py:11-55` | 修改 `GenomeFile.accession` 并保存 | 无 dry-run/apply 保护 | 生产关联修复完成前不能删 | T1/T5 |
| `seed_ir64_demo_hierarchy.py:195-267` | `GenomeFile.objects.update_or_create()` | 无 dry-run；事务内直接写 | 不应继续保留为活动演示入口 | T1 改为只写新结构或退役 |
| `migrate_placeholder_hierarchy.py:252-290` | 重绑 FileRelation，同时更新 `GenomeFile.assembly_id` | 默认 dry-run，需 `--apply` | 迁移完成前不能删 | T5 后退役 |

`backfill_genomefile_to_datafile.py:19-291` 读取 GenomeFile，写 `DataFile/FileRelation`，不写旧表。但该命令仅提供 `--dry-run` 标志，未指定时默认会写数据库。正式生产使用前应改成默认只读、必须显式 `--apply`。

## 6. 前端依赖

未发现前端调用以下旧接口：

- `/genome-files/`
- `/download-transcriptome/`
- `/gd/api/files/genome-files/...`

| 文件及行号 | 当前用途 | 是否依赖旧模型接口 | 风险与阶段 |
|---|---|---|---|
| `vue_project/src/views/AssemblyView.vue:90,468-469` | 使用 `genome_download_url` 下载主基因组 | 否，来自新结构 | 保留 |
| `AdminDataManager.vue:109-113,860,978` | `genomeFile` 是前端字段名 | 未发现旧 API 调用 | 可后续语义重命名，不是退役前置条件 |
| `CodonWTool.vue:63-123,331-835` | 上传基因组文件，调用 `/files/codonw/*` | 不读 GenomeFile 表，但后端绑定旧 ViewSet 类 | T2 拆分后端 View |
| `CodonCard.vue:628,789,854` | CodonW 结果查询和上传 | 同上 | T2 |
| `en-US.js:225,877,1097-1132` | UI 文案 | 否 | 保留 |
| `zh-CN.js:225,877,1097-1132` | UI 文案 | 否 | 保留 |
| `router/index.js:106-118,184-186` | Assembly/CodonW 页面路由 | 无旧 GenomeFile 页面 | 保留 |

结论：前端业务没有旧表查询或下载依赖，但 CodonW 后端实现仍寄居在 `GenomeFileViewSet` 中。删除该类前必须先拆出独立 CodonW View。

## 7. fallback / 双读 / 双写

### 7.1 GenomeFile → DataFile fallback

活动业务服务中未发现“新结构查不到就回退 GenomeFile”的在线实现。

需要区分：

1. `validate_new_file_structure`、`audit_legacy_fallback` 等命令会比较新旧结构，但不是在线 fallback；
2. serializer 的反向 `files` 逻辑是潜在旧读取，当前已知活动入口通过 `prefetched_files=[]` 阻断；
3. `views.py:3180-3314` 包含旧 fallback，但控制流不可达。

### 7.2 DataFile → GenomeFile fallback

未发现活动业务代码从 DataFile 回退 GenomeFile。

`file_relation_service.py:8-9` 的 `genome_fasta` → `genome` 是 FileRelation role 兼容，两者都指向 DataFile，不是 GenomeFile fallback。

### 7.3 双读

- 在线 API 主链：未发现活动双读；
- 审计、比较和迁移命令：有意读取两边，用于发现差异；
- 休眠 serializer 和死代码：仍保留双结构语义，应在最终退役前清除。

### 7.4 双写

- `scan_files` 只支持新结构，测试明确拒绝 `legacy` 和 `dual` 模式；
- 普通 API 未发现双写；
- `migrate_placeholder_hierarchy` 在迁移时同时调整新关系和旧 FK；
- `seed_ir64_demo_hierarchy` 直接创建旧记录，属于纯旧写而非双写。

## 8. 数据迁移与生产风险

生产数据库中仍可能存在只记录于 GenomeFile、尚未迁移到 `DataFile + FileRelation` 的数据。

代码依据：

- `audit_file_migration.py:40-59` 专门统计旧行与缺失新记录；
- `validate_new_file_structure.py:49-94` 计算 legacy fallback；
- `generate_legacy_fix_todo.py`、`report_legacy_usage.py`、`backfill_genomefile_to_datafile.py` 均处理未映射旧记录；
- 两份历史 `exceptions.full.tsv` 包含 `database_accession_without_genome_file`，但只能证明历史清单状态，不能证明当前生产库已经或尚未完成迁移。

本次未连接生产数据库，因此以下项目全部是待验证状态：

- GenomeFile 总行数；
- 每条旧记录是否有路径一致的 DataFile；
- 是否有正确的 FileRelation；
- 缺失物理文件数；
- 未映射 accession、assembly、annotation 数；
- 是否仍有运维脚本调用旧命令；
- 旧 410 路由是否仍有真实访问流量。

这些计数归零前，不能删除旧表、模型、审计命令或回填命令。

## 9. 必须保留的历史 migration

| 文件 | 关键行 | 当前用途 | 是否可删除 |
|---|---:|---|---|
| `0001_initial.py` | 29 起 | 创建 GenomeFile | 否 |
| `0002_auto_20250701_2239.py` | 38-45 | 修改旧字段 | 否 |
| `0003_alter_genomefile_category.py` | 14-16 | category 演进 | 否 |
| `0004_alter_genomefile_category.py` | 14-16 | category 演进 | 否 |
| `0005_alter_genomefile_category.py` | 14-16 | category 演进 | 否 |
| `0006_tablecolumnconfig.py` | 9 | migration 依赖链 | 否 |
| `0008_genomefile_accession.py` | 15-17 | 增加 accession FK | 否 |
| `0009_assembly_annotation_genomefile_links.py` | 48-55 | 增加 assembly/annotation FK | 否 |
| `0010_backfill_default_assembly_annotation.py` | 73-138 | 历史数据迁移及逆操作 | 否 |
| `0012_alter_genomefile_category_variableblocks.py` | 14-17 | category 演进 | 否 |
| `0013_accession_genetic_stock_id_assembly_metadata.py` | 7 | migration 依赖链 | 否 |

未来应新增一个新的删除模型 migration，而不是编辑或删除这些历史文件。

## 10. 可直接删除的代码

严格按当前证据，暂时没有建议“不经独立变更和测试即可直接删除”的 GenomeFile 文件。

可以作为低风险清理候选，但仍应通过单独任务处理：

- `views.py:3180-3314`：位于 `admin_login` 返回后的不可达旧实现；
- `views.py:3350-3401`：未找到调用者的 `_analyze_uploaded_file()`；
- `views.py:222-249`：未找到调用者的 `_adapt_accession_file_service_result()`；
- 未路由的 `GenomeFileViewSet.paginated_overview` 及已被 archive adapter 替代的方法。

风险在于 `views.py` 同时承载活动 CodonW 功能，因此不应整类或整文件删除。

## 11. 必须先迁移再删除的代码

### 11.1 审计、回填和修复工具

| 文件 | 关键行 | 当前用途 | 读旧表 | 写旧表 | 替代/退出条件 | 推荐阶段 |
|---|---:|---|---:|---:|---|---|
| `audit_file_migration.py` | 9,40-59,141 | 迁移审计 | 是 | 否 | 生产迁移最终验收 | T6 |
| `audit_legacy_fallback.py` | 8,140-144 | fallback 审计 | 是 | 否 | fallback 计数归零 | T6 |
| `backfill_genomefile_to_datafile.py` | 10,73-291 | 读旧写新 | 是 | 否 | 回填完成且复核通过 | T5 |
| `cleanup_data.py` | 4,16-34 | 清理和修改旧表 | 是 | 是 | 先确认无生产调用 | T1 |
| `cleanup_placeholder_hierarchy.py` | 9,103-154 | 旧表作为删除保护条件 | 是 | 否 | placeholder 清理完成 | T5/T6 |
| `compare_accession_files.py` | 7,82-86 | 新旧比较 | 是 | 否 | 差异归零 | T6 |
| `compare_annotation_files.py` | 8,95 | 新旧比较 | 是 | 否 | 差异归零 | T6 |
| `compare_overview_files.py` | 7,131-135 | 新旧比较 | 是 | 否 | 差异归零 | T6 |
| `generate_legacy_fix_todo.py` | 7,39 | 生成修复清单 | 是 | 否 | 修复项归零 | T6 |
| `link_genomefiles_to_accessions.py` | 5,16-47 | 修改旧 FK | 是 | 是 | 生产关联修复完成 | T1/T5 |
| `migrate_placeholder_hierarchy.py` | 11,229-290 | 同步新关系与旧 FK | 是 | 是 | placeholder 迁移完成 | T5 |
| `report_genomefile_archive_status.py` | 13,65-230 | 归档门禁报告 | 是 | 否 | 最终删除模型前门禁 | T6/T7 |
| `report_legacy_usage.py` | 7,36 | 旧使用情况报告 | 是 | 否 | 使用计数归零 | T6 |
| `seed_ir64_demo_hierarchy.py` | 6,195-267 | 创建演示旧数据 | 是 | 是 | 改成只写新结构或退役 | T1 |
| `validate_new_file_structure.py` | 9,49-207 | 新结构验收和旧依赖统计 | 是 | 否 | 最终验收完成 | T6/T7 |

`command_lifecycle.py:9-64` 已将相关命令分类为 `retain_audit`、`legacy_repair` 或 `retire_pending_usage_confirmation`，应随各命令一起维护。

其余 management command 命中主要是变量或函数名，并不依赖旧模型：

- `audit_external_api_readiness.py`
- `audit_genome_transcriptome_readiness.py`
- `audit_public_fasta_indexes.py`
- `backfill_assembly_fasta_statistics.py`
- `backfill_assembly_from_genome_relations.py`
- `backfill_jbrowse_refname_aliases.py`
- `build_fasta_indexes.py`
- `generate_hierarchy_manifests_from_file_list.py`
- `reconcile_assembly_annotation_context.py`

### 11.2 API 和 URL 路由

`django2/files/urls.py`：

- 87：`query/genome-files/` 名称包含 genome-files，但实际使用 DataFile/FileRelation；
- 104-110：活动 CodonW 路由绑定 `GenomeFileViewSet`；
- 111-125、155：旧 GenomeFile 路由，全部转到 410 archive adapter。

`django2/filemanager/urls.py`：

- 46：Django Admin 暴露；
- 65-71：旧 transcriptome 下载兼容路由，返回 410。

处理顺序应为：先拆 CodonW View；再保留 410 tombstone 并结合访问日志确认旧调用方；最后删除旧路由和 archive adapter。

## 12. 自动化测试和文档引用

### 12.1 自动化测试

这些测试会在测试库中创建或查询 GenomeFile，但不代表生产写入口：

- 回填：`test_backfill_genomefile_to_datafile.py:16`；
- API 集成：
  - `test_accession_detail_file_relation_integration.py:16`
  - `test_annotation_file_relation_integration.py:8`
  - `test_assembly_detail_api.py:92`
  - `test_data_overview_api.py:101`
  - `test_download_datafile.py:7`
  - `test_genome_chromosome_query.py:38`
  - `test_genome_list_api.py:69`
  - `test_new_query_entrypoints.py:172`
  - `test_paginated_overview_file_relation_integration.py:9`
  - `test_query_context_ambiguity.py:152`
  - `test_raw_data_api.py:88`
  - `test_transcriptome_list_api.py:100`
- command：
  - `test_audit_file_migration.py:17`
  - `test_migrate_placeholder_hierarchy.py:10`
  - `test_reconcile_assembly_annotation_context.py:37`
  - `test_scan_files_new_only.py:10`
  - `test_validate_new_file_structure.py:10`
- regression：
  - `test_stage_b_query_boundaries.py:6`
  - `test_stage12b_archive_genomefile.py:12`
  - `test_stage7_reduce_legacy_dependency.py:10`
  - `test_stage8_fallback_switches.py:9`
  - `test_legacy_models_and_api.py:16`
- unit：
  - `test_fasta_index_service.py:51`
  - `test_file_relation_service.py:3`
  - `test_jbrowse_index_service.py:47`
- 前端退役边界：
  - `data-overview-matrix.test.mjs:58`
  - `genome-retirement.test.mjs:40`
  - `raw-data-page.test.mjs:24`
  - `transcriptome-list-view.test.mjs:25`
  - `unified-accession-page.test.mjs:69`

这些测试应随阶段逐步改写，不能在旧表删除前整体移除。尤其应保留“前端不出现旧 URL”“`scan_files` 不支持 legacy/dual”“旧 API 返回 410”等门禁，直到对应退役阶段完成。

### 12.2 文档和历史证据

20 个文档命中文件包括：

- `AGENTS.md:47`
- `django2/docs/file_storage_compatibility.md:1`
- `docs/ACTIVE_DOCUMENTS.md:17`
- `docs/AGENTS_仓库级开发约束_评审与修改意见_20261103.md:15`
- `docs/api_pages.md:7`
- 三份生产部署或迁移记录与指南
- 外部工具 FASTA Region 验证文档
- 三份 superpowers 设计或计划文档
- 第一阶段交接文档
- 四份仓库根目录历史实施或整改方案
- `git_commit_log.md:43`
- `生产环境部署中的问题.md:527`
- `数据库逻辑梳理模板.md:27`

它们不读写数据库，不属于运行时删除对象。应在功能退役后更新过时描述，但无需为了活动代码引用归零而删除。

两份 metadata 例外表：

- `django2/metadata/production_full_manifest_20260922/exceptions.full.tsv:5`
- `django2/metadata/production_full_manifest_20260924/exceptions.full.tsv:7`

它们属于历史生产清单证据，建议保留。

## 13. 建议任务拆分

### T0：生产只读审计

- 在单独获准任务中运行只读审计；
- 输出旧行总数、缺失 DataFile、缺失 FileRelation、缺失物理文件和未映射层级；
- 保存可复现报告和时间点。

### T1：关闭旧写入口

- 禁用或保护 `cleanup_data`、`link_genomefiles_to_accessions`；
- 将 `seed_ir64_demo_hierarchy` 改为只写新结构或删除该命令；
- 把回填命令改为默认 dry-run、必须显式 `--apply`；
- 添加“非 migration 代码不得对 GenomeFile 执行 save/create/update/delete”的门禁。

### T2：拆分 CodonW

- 将 CodonW 方法从 `GenomeFileViewSet` 移至独立 View/ViewSet；
- 保持现有 `/files/codonw/*` URL 和返回格式；
- 完成前后端回归验证。

### T3：清除活动业务引用

- 将分类常量移入独立配置或 FileRole 定义；
- 删除 serializer 对反向 `files` 的 fallback；
- 删除不可达旧 overview 和未调用 helper；
- 评估 Admin 是否改为 DataFile/FileRelation 只读界面。

### T4：稳定 410 兼容层

- 保留旧 URL 的 410 adapter；
- 检查生产访问日志，确认没有调用方；
- CI 保证旧 API 不恢复查询或写入。

### T5：生产迁移

- 备份；
- dry-run 回填；
- 审核 unmapped 清单；
- 显式 apply；
- 重新执行审计，要求缺失 DataFile/FileRelation 为零。

### T6：退役审计和修复工具

- 连续审计结果及调用日志满足门禁后，删除只为 GenomeFile 服务的 repair/compare 命令；
- 保留最终报告和迁移证据。

### T7：删除模型

- 新增独立 Django migration 删除 GenomeFile；
- 删除模型、serializer、Admin 注册和相关导入；
- 历史 migration 保持不变。

### T8：删除兼容路由

- 经调用方和访问日志确认后删除 410 tombstone；
- 更新前端门禁、API 文档和运维文档。

## 14. 当前不应执行的删除操作

当前不应：

- 删除 GenomeFile 数据库表或模型；
- 删除任何历史 migration；
- 删除 backfill、audit、validate、report 命令；
- 删除 410 archive adapter；
- 直接删除 `GenomeFileViewSet`，因为 CodonW 仍依赖它；
- 删除旧模型相关测试；
- 根据代码推断生产数据已迁移完成；
- 执行 `cleanup_data`、`link_genomefiles_to_accessions` 或 `seed_ir64_demo_hierarchy`；
- 在当前脏工作区进行批量清理。

## 15. 重点问题结论

1. **当前是否仍有 GenomeFile 写入入口？**
   有。普通 API 和 Admin 已无有效写入口，但 4 个 management command 仍可能写入或删除旧表。

2. **当前是否仍有 GenomeFile 查询或下载入口？**
   公共旧查询和下载接口仍存在但返回 410；Admin 仍能真实查询，审计和迁移命令也能查询。

3. **是否存在 GenomeFile → DataFile fallback？**
   活动在线业务主链未发现。存在审计比较以及潜在 serializer 旧读取。

4. **是否存在 DataFile → GenomeFile fallback？**
   未发现。

5. **是否存在双读或双写？**
   在线业务未发现；审计工具会双读，placeholder 迁移会同时调整新关系和旧 FK。

6. **前端是否仍然调用 GenomeFile 接口？**
   未发现。CodonW 调用活动 CodonW URL，但后端类结构仍与旧 ViewSet 耦合。

7. **生产数据库中是否可能存在仅记录于 GenomeFile 的数据？**
   可能，且仓库明确提供了审计和回填工具；本次没有生产数据库证据确认数量。

8. **哪些引用属于历史 migration，必须保留？**
   第 9 节列出的 11 个 migration 全部保留。

9. **哪些引用是迁移或审计工具，暂时不能删除？**
   第 11.1 节列出的 15 个直接依赖旧模型的命令，至少在生产审计、回填和验收完成前需要保留或受控隔离。

10. **要实现“活动代码中的 GenomeFile 引用为 0”，应如何拆分？**
    按 T0-T8 执行：先取得生产证据，再关闭写入口、拆 CodonW、清除业务引用、迁移生产数据、退役工具、删除模型，最后删除 410 路由。

## 16. 总体结论

GenomeFile 已退出主要在线查询和下载主链，但尚未达到可删除状态，也尚未达到“活动代码引用为 0”。

当前主要剩余阻碍是：

- 只读 Django Admin；
- 4 个仍能写旧表的 management command；
- 必须暂时保留的审计、迁移和回填工具；
- serializer 中的潜在 fallback；
- CodonW 与 `GenomeFileViewSet` 的类级耦合；
- 尚未通过生产数据库审计确认的数据迁移状态。

因此，当前正确状态应标记为：**旧在线 API 已封存；新结构主链已建立；生产数据完整迁移、旧写入口关闭和模型删除均待实施与验收。**
