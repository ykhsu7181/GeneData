# 文件资产与兼容逻辑说明

## 当前主路径

`DataFile` 是正式文件资产表，用于记录文件编号、文件名、文件路径、文件大小、校验值等文件自身信息。

`FileRelation` 是正式文件归属表，用于记录文件属于哪个业务对象，例如 accession、assembly、annotation、dataset 等。

新功能应优先通过 `DataFile + FileRelation` 查询和下载文件，不得直接依赖 `GenomeFile` 作为主数据来源。

## 历史兼容路径

`GenomeFile` 是历史兼容表，保留用于旧接口、旧页面和过渡期 fallback。

`organism` 是历史兼容字段，保留用于旧数据识别和兜底查询。

当前不会删除 `GenomeFile`，也不会删除 `organism` 字段。

## fallback 开关

项目提供两个兼容开关：

```python
ENABLE_GENOMEFILE_FALLBACK = True
ENABLE_ORGANISM_FALLBACK = True
```

`ENABLE_GENOMEFILE_FALLBACK` 控制是否允许按 `GenomeFile.accession_id / assembly_id / annotation_id` 兜底。

`ENABLE_ORGANISM_FALLBACK` 控制是否允许按 `GenomeFile.organism` 兜底。

即使 fallback 关闭，`DataFile + FileRelation` 查询仍然是第一优先级并保持可用。

## scan_files 写入策略

`scan_files` 当前默认 `dual-write`：

```bash
python manage.py scan_files
```

等价于：

```bash
python manage.py scan_files --write-mode dual
```

显式模式仍可使用：

```bash
python manage.py scan_files --write-mode legacy
python manage.py scan_files --write-mode new
python manage.py scan_files --write-mode dual
```

`--dry-run` 仍然不写入数据库。

## 关闭 fallback 前的检查

关闭任何 fallback 前必须先运行审计命令：

```bash
python manage.py audit_file_migration --output-dir ./audit_reports
python manage.py audit_legacy_fallback --limit 100 --output-dir ./audit_reports
python manage.py audit_file_relations --output-dir ./audit_reports
python manage.py report_legacy_usage --output-dir ./audit_reports
```

建议满足以下条件后再考虑降低旧逻辑依赖：

- `broken_file_relations` 报告为空或已确认可接受。
- `legacy_fallback_report` 中 organism fallback 依赖已清零或有明确豁免。
- `legacy_usage_report` 中所有可修复项已完成回填。
- 前端已优先使用 `datafile_download_url`。
