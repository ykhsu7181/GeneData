# 文件资产 new-only 与 GenomeFile 归档说明

## 当前结论

当前项目文件业务主链路已经切换为 `DataFile + FileRelation` new-only。

`DataFile` 是正式文件资产表，用于记录文件编号、文件名、文件路径、文件大小、MD5 等文件自身信息。

`FileRelation` 是正式文件归属表，用于记录文件属于哪个业务对象，例如 accession、assembly、annotation、dataset 等。

业务查询、页面展示、文件下载、扫描写入都应以 `DataFile + FileRelation` 为准。

新功能不得直接依赖 `GenomeFile`，不得依赖 `organism` 兜底查询，也不得返回 `/genome-files/` 下载链接。

## GenomeFile 当前定位

`GenomeFile` 仍保留为 historical archive table，仅用于历史数据追溯、迁移校验和审计报告。

当前不删除 `GenomeFile` model，不删除 `GenomeFile` 数据库表，也不删除历史字段。

但 `GenomeFile` 不再参与业务主链路：

- 不再作为文件查询来源。
- 不再作为文件写入目标。
- 不再作为业务下载入口。
- 不再作为页面统计来源。
- 不再通过 `organism` 字段做 fallback。

旧 `GenomeFileViewSet` 和旧 `/genome-files/` 下载入口应保持 archived/deprecated 行为，返回 410 Gone 或明确归档提示。

## 允许读取 GenomeFile 的位置

只允许以下历史或审计类逻辑读取 `GenomeFile`：

- `backfill_genomefile_to_datafile`
- `audit_file_migration`
- `audit_legacy_fallback`
- `audit_file_relations`
- `validate_new_file_structure`
- `report_genomefile_archive_status`
- 历史迁移相关测试
- admin 只读归档展示

除此之外，业务接口、服务层、扫描逻辑、下载逻辑、前端页面都不应读取或返回 `GenomeFile` 数据。

## fallback 状态

`GenomeFile fallback` 和 `organism fallback` 已不再作为业务兜底路径。

当前预期行为：

- `file_relation_service` 只查询 `FileRelation + DataFile`。
- 查询不到文件时返回空列表。
- 返回结果的 `source` 只应为 `new_relation`。
- 不应再返回 `legacy_genomefile`。
- 不应再返回 `organism_fallback`。

历史文档中提到的 `ENABLE_GENOMEFILE_FALLBACK`、`ENABLE_ORGANISM_FALLBACK` 仅作为旧阶段记录，不应作为新功能依赖。

## scan_files 写入策略

`scan_files` 当前应为 new-only：

```bash
python manage.py scan_files
```

默认行为：

- 创建或复用 `DataFile`。
- 创建或复用 `FileRelation`。
- 不创建 `GenomeFile`。
- 不更新 `GenomeFile`。
- 不依赖 `GenomeFile.organism`。

仍保留：

```bash
python manage.py scan_files --dry-run
python manage.py scan_files --path <path>
python manage.py scan_files --limit <N>
python manage.py scan_files --output-dir ./audit_reports
```

不再支持 legacy / dual 写入：

```bash
python manage.py scan_files --write-mode legacy  # unsupported
python manage.py scan_files --write-mode dual    # unsupported
```

如果保留 `--write-mode` 参数，也只允许 `new`。

## 文件下载策略

业务页面和接口返回的下载链接必须使用 DataFile 下载入口：

```text
/gd/api/files/data-files/<file_id>/download/
```

禁止业务页面返回：

```text
/gd/api/files/genome-files/<id>/download/
```

旧 GenomeFile download 如仍保留 URL，仅用于归档提示，不再实际下载历史文件。

## 进入生产或关闭旧逻辑前的检查

每次生产部署或清理旧逻辑前，建议运行：

```bash
python manage.py validate_new_file_structure --settings=filemanager.settings_production
python manage.py report_genomefile_archive_status --settings=filemanager.settings_production --output-dir ./audit_reports
```

如需更细审计，可继续运行：

```bash
python manage.py audit_file_migration --settings=filemanager.settings_production --output-dir ./audit_reports
python manage.py audit_file_relations --settings=filemanager.settings_production --output-dir ./audit_reports
```

通过标准：

- `validate_new_file_structure` 输出 `PASS`。
- `GenomeFile` 缺失迁移数为 0，或有明确归档说明。
- `DataFile` 均有有效 `FileRelation`，或无关系文件已明确标记可忽略。
- `broken_filerelation_count = 0`。
- `duplicate_filerelation_count = 0`。
- `legacy_fallback_count = 0`。
- `organism_fallback_count = 0`。
- 业务接口不返回 `/genome-files/`。

## 新功能开发约束

新增页面、接口或导入命令时，应遵循：

- 文件资产只写入 `DataFile`。
- 文件归属只写入 `FileRelation`。
- 文件查询只通过 `DataFile + FileRelation`。
- 文件下载只使用 DataFile download。
- 不新增 `GenomeFile` 依赖。
- 不新增 `organism fallback`。
- 不恢复 legacy / dual write。
- 不新增 migration，除非明确进入数据库结构调整阶段。

## 当前待继续完善

虽然文件链路已经 new-only，但数据关系仍需持续补齐：

- `Accession -> Species`
- `Accession -> Dataset`
- `Dataset -> Project`
- `DataFile -> FileRelation -> Dataset / Accession / Assembly / Annotation`

页面中出现 `未归属物种`、`Project -`、`Dataset -` 时，优先通过 metadata manifest 或管理命令补齐关系，而不是在前端写死展示字段。
