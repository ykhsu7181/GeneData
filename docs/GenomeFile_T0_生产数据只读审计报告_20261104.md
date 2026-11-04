# GenomeFile T0 生产数据只读审计报告

审计日期：2026-11-04
审计目标：确认生产环境 `GenomeFile` 中是否仍存在尚未迁移到 `DataFile + FileRelation` 的真实数据
审计性质：只读审计
审计结果：**PASS，可以进入 GenomeFile 退役准备阶段，但不能立即删除模型或数据库表**

## 1. 证据边界

本报告依据本轮生产服务器终端输出、三个现有 management command 生成的审计报告，以及针对两条异常记录执行的补充只读查询整理。

整理者未从本地开发机直接连接生产数据库；生产数据结果来自操作者在真实生产 Linux 服务器执行命令后提供的终端证据。

本轮操作遵守以下边界：

- 未执行数据回填；
- 未执行 `INSERT`、`UPDATE` 或 `DELETE`；
- 未调用业务模型的 `save/create/update/delete`；
- 未执行 migration；
- 未修改生产业务文件；
- 仅在专用审计目录创建 TXT、TSV 等审计报告；
- 补充查询使用数据库只读事务；
- 未删除或修改 `GenomeFile`、`DataFile`、`FileRelation` 数据。

## 2. 生产环境身份确认

### 2.1 活动后端

```text
活动发布目录：/home/labuser/rdcheng/gd/releases/django2-d8312dd
生产 Python：/home/Software/anaconda3/envs/django2_env/bin/python3.9
Django 版本：3.2.9
生产进程：Gunicorn
监听端口：2025
WSGI：filemanager.wsgi:application
```

### 2.2 Django 与数据库

```text
SETTINGS_MODULE = filemanager.settings_production
DEBUG = False
数据库名 = gene_manage
配置主机 = 127.0.0.1
配置端口 = 3307
数据库用户 = gene_user
MySQL 内部端口 = 3306
MySQL 版本 = 5.7.44
```

配置端口 `3307` 与 MySQL 返回的内部端口 `3306` 可解释为宿主机到数据库容器或内部实例的端口映射，不影响本次审计身份确认。

## 3. 使用的现有审计工具

本次优先复用了仓库已有工具：

1. `audit_file_migration`
2. `report_legacy_usage`
3. `validate_new_file_structure`

生产部署版本的源码检查结果：

| 命令 | 数据库写入 | migration | 文件行为 |
|---|---|---|---|
| `audit_file_migration` | 无 | 无 | 创建输出目录，写 TXT 和 TSV 报告 |
| `report_legacy_usage` | 无 | 无 | 创建输出目录，写 TSV 报告 |
| `validate_new_file_structure` | 无 | 无 | 创建输出目录，写 TXT 和 TSV 报告 |

源码搜索未发现以下调用：

- ORM `save()`；
- ORM `create()`；
- ORM `update()`；
- ORM `delete()`；
- `bulk_create()` 或 `bulk_update()`；
- migration 调用；
- 业务文件修改。

三个命令的唯一命令专用参数均为：

```text
--output-dir OUTPUT_DIR
```

## 4. 审计执行位置

生产审计证据目录：

```text
/home/labuser/rdcheng/gd/audit_reports/genomefile_t0_20261104_124703
```

目录结构：

```text
genomefile_t0_20261104_124703/
├── 01_file_migration/
│   ├── file_migration_audit_20261104_124713.txt
│   └── file_migration_audit_20261104_124713.tsv
├── 02_legacy_usage/
│   └── legacy_usage_report_20261104_124725.tsv
└── 03_new_structure/
    ├── validate_new_file_structure_20261104_124735.txt
    └── validate_new_file_structure_20261104_124735.tsv
```

## 5. 自动审计结果

### 5.1 audit_file_migration

```text
genomefile_total                         2111
datafile_total                           4500
filerelation_total                       8820
genomefile_matched_datafile_count        2111
genomefile_missing_datafile_count        0
datafile_without_relation_count          0
broken_filerelation_count                0
duplicate_file_path_count                0
duplicate_filerelation_count             0
```

结论：全部 2111 条 GenomeFile 均能匹配 DataFile；没有无关系 DataFile、破损关系、重复旧路径或重复关系键。

### 5.2 report_legacy_usage

异常类型汇总：

```text
unresolved_legacy  2
```

该命令发现两条旧 GenomeFile 无法仅依靠旧字段自动判断业务对象。它们随后通过补充只读查询完成核验，详见第 7 节。

### 5.3 validate_new_file_structure

```text
genomefile_total_count                   2111
genomefile_missing_datafile_count        0
datafile_total_count                     4500
datafile_without_relation_count          0
broken_filerelation_count                0
duplicate_filerelation_count             0
legacy_fallback_count                    0
organism_fallback_count                  0
result                                   PASS
cannot_enter_new_only                    false
message                                  PASS: ready to start file_relation_service new-only refactor.
```

结论：按现有 new-only 门禁规则，生产文件结构通过验证。

## 6. 补充只读核验

由于三个现有命令没有完整覆盖物理文件存在性、正确关系总数和无法自动映射记录，额外执行了补充只读查询。

查询在事务内执行：

```sql
SET TRANSACTION READ ONLY
```

结果：

```text
genomefile_total_count                         2111
correct_filerelation_count                     2109
missing_or_unresolved_filerelation_count       2
physical_missing_count                         0
unmapped_accession_count                       2
assembly_scope_total                           1725
unmapped_assembly_count                        1725
annotation_scope_total                         386
unmapped_annotation_count                      386
cannot_auto_determine_count                    2
```

其中 `correct_filerelation_count=2109` 是自动判断结果；剩余两条记录随后通过实际 DataFile 和 FileRelation 只读查询确认关系正确，因此最终正确关系总数为 2111。

## 7. 两条例外记录

### 7.1 GenomeFile 1405

旧记录：

```text
GenomeFile ID：1405
文件名：genome.Nanoay P.A.fasta
category：genome
organism：Nanoay P
accession_id：NULL
assembly_id：NULL
annotation_id：NULL
```

对应新结构：

```text
DataFile ID：1242
file_code：FILE001242
is_current：True
```

实际关系：

```text
FileRelation 3345
  related_type = accession
  related_id = 376
  file_role = genome
  target = Nanoay P.A

FileRelation 4863
  related_type = assembly
  related_id = 1476
  file_role = genome
  target = Nanoay P.A / Nanoay P.A genome assembly
```

判定：迁移正确。自动判断失败是因为旧 `GenomeFile.organism` 为 `Nanoay P`，而实际 accession 为 `Nanoay P.A`，同时旧 FK 为空。

### 7.2 GenomeFile 1726

旧记录：

```text
GenomeFile ID：1726
文件名：annotation.Nanoay P.A.gff
category：annotation
organism：Nanoay P
accession_id：NULL
assembly_id：NULL
annotation_id：NULL
```

对应新结构：

```text
DataFile ID：426
file_code：FILE000426
is_current：True
```

实际关系：

```text
FileRelation 3346
  related_type = accession
  related_id = 376
  file_role = annotation
  target = Nanoay P.A

FileRelation 5583
  related_type = assembly
  related_id = 1476
  file_role = annotation
  target = Nanoay P.A / Nanoay P.A genome assembly

FileRelation 5584
  related_type = annotation
  related_id = 770
  file_role = annotation
  target = Nanoay P.A / Nanoay P.A genome assembly / Nanoay P.A annotation
```

判定：迁移正确。新结构已具备 accession、assembly 和 annotation 层级关系。

## 8. T0 指标汇总

| 编号 | 指标 | 最终结果 | 判定 |
|---:|---|---:|---|
| 1 | GenomeFile 总记录数 | 2111 | 已确认 |
| 2 | 有对应 DataFile 的记录数 | 2111 | 全部匹配 |
| 3 | 缺失 DataFile 的记录数 | 0 | PASS |
| 4 | 有正确 FileRelation 的记录数 | 2111 | 2109 自动确认，2 条补充核验确认 |
| 5 | 缺失正确 FileRelation 的记录数 | 0 | PASS |
| 6 | 缺失物理文件的记录数 | 0 | PASS |
| 7 | 未映射 accession 的记录数 | 旧表自动映射失败 2；新结构缺失 0 | 两条例外均已正确关联 accession 376 |
| 8 | 未映射 assembly 的记录数 | 旧表严格字段口径 1725；本次迁移缺失 0 | 旧 FK 缺失不等同于新结构关系缺失 |
| 9 | 未映射 annotation 的记录数 | 旧表严格字段口径 386；本次迁移缺失 0 | 旧 FK 缺失不等同于新结构关系缺失 |
| 10 | 不能自动判断的异常记录 | 2 | 均已补充只读核验并确认迁移正确 |

## 9. 关于旧 assembly/annotation FK 统计的解释

补充查询中的：

```text
unmapped_assembly_count = 1725
unmapped_annotation_count = 386
```

统计的是旧 `GenomeFile` 是否具有可直接使用的 `assembly_id` 或 `annotation_id`，不能解释为新结构缺少 1725 个 assembly 关系或 386 个 annotation 关系。

本次迁移完成性的判断依据是：

- GenomeFile 对应 DataFile 是否存在；
- DataFile 是否为当前记录；
- 是否存在符合现行迁移规则的 FileRelation；
- FileRelation 目标对象是否存在；
- 是否存在破损或重复关系；
- 物理文件是否存在；
- 无法自动判断的记录是否经过实际关系核验。

按该口径，未发现需要通用回填的数据。

## 10. 阶段判断

```text
T0 生产数据只读审计：PASS
需要通用 DataFile 回填：否
需要通用 FileRelation 回填：否
需要修复物理文件：否
允许进入 GenomeFile 退役准备下一阶段：是
允许立即删除 GenomeFile：否
```

可以进入以下后续任务：

1. 关闭非 migration 的 GenomeFile 写入入口；
2. 将 CodonW 功能从 `GenomeFileViewSet` 拆分；
3. 清除 serializer 潜在 fallback 和活动业务代码中的 GenomeFile 引用；
4. 保留历史 migration、410 兼容层和审计工具，直至后续门禁完成；
5. 完成部署和访问日志验证后，再单独评审删除模型 migration。

当前不得：

- 执行 GenomeFile 通用回填；
- 修改两条旧 GenomeFile 记录以“美化”旧数据；
- 删除旧模型或数据库表；
- 删除历史 migration；
- 删除生产审计报告；
- 直接移除 410 兼容路由。

## 11. 可复现性与证据保全

建议在生产审计目录生成并验证校验文件：

```bash
AUDIT_ROOT=/home/labuser/rdcheng/gd/audit_reports/genomefile_t0_20261104_124703

(
  cd "$AUDIT_ROOT" || exit 1

  find . -type f ! -name SHA256SUMS -print0 |
    sort -z |
    xargs -0 sha256sum > SHA256SUMS

  sha256sum -c SHA256SUMS
)
```

校验完成后，应将以下信息共同纳入退役审批证据：

- 活动发布目录；
- 生产 Python 和 Django 版本；
- 数据库身份信息，不包含密码；
- 三个审计命令的源码 SHA-256；
- 审计报告目录及 `SHA256SUMS`；
- 两条例外记录的只读核验结果；
- 本报告。

## 12. 最终结论

生产环境共有 2111 条 GenomeFile。全部记录均有对应 DataFile，全部物理文件存在，未发现无关系 DataFile、破损 FileRelation 或重复关系。

自动审计有两条记录因旧 `organism` 值和旧 FK 不完整而无法自动映射；补充只读核验证明两条记录在新结构中均已正确关联到 `Nanoay P.A` 的 accession、assembly，并在注释文件场景下正确关联 annotation。

因此，本次 T0 审计确认：**生产环境不存在尚未迁移到 DataFile + FileRelation、需要执行通用回填的 GenomeFile 真实数据。项目可以进入关闭旧写入口和清除活动代码依赖的退役准备阶段，但尚不能直接删除 GenomeFile 模型、表、历史 migration 或兼容路由。**
