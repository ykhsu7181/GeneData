# GeneData 生产 Manifest 导入手册

本手册仅用于 `production_full_manifest_20260922`。所有写操作必须在维护窗口执行，并保留数据库和 `manual_files` 备份。

## 1. 部署前准备

1. 部署与本 Manifest 同一 Git 提交的后端代码，并安装锁定的依赖。
2. 配置生产环境变量，至少包括 `DJANGO_SETTINGS_MODULE=filemanager.settings_production`、数据库连接和 `MANUAL_FILES_DIR`。
3. 确认 `MANUAL_FILES_DIR=/home/labuser/rdcheng/gd/manual_files`（如生产实际路径不同，以实际配置为准）。
4. 备份数据库；记录备份文件、时间、操作者和恢复命令。
5. 对 `manual_files` 做快照或只读备份。本流程不会修改源文件，但回滚依据必须独立保存。

## 2. 校验部署包

在本目录执行：

```bash
sha256sum -c SHA256SUMS
python manage.py validate_hierarchy_manifest_package \
  --manifest-dir metadata/production_full_manifest_20260922
```

两条命令均须成功。任何哈希不一致都应停止导入，禁止现场修改 TSV 后继续。

## 3. 验收生产文件实体

```bash
python manage.py validate_hierarchy_manifest_package \
  --manifest-dir metadata/production_full_manifest_20260922 \
  --verify-source-files \
  --report audit_reports/production_manifest_file_acceptance.txt

python manage.py validate_manual_files \
  --path /home/labuser/rdcheng/gd/manual_files \
  --checksum sha256 \
  --output-dir audit_reports/production_manual_files_preimport \
  --fail-on-errors
```

`--verify-source-files` 使用 `files.full.tsv` 中的生产绝对路径；若服务器目录不同，应先重新生成并重新人工确认整包，而不是直接替换路径文本。

## 4. 全量层级导入预演

```bash
python manage.py import_incremental_hierarchy_manifest \
  --assembly-file metadata/production_full_manifest_20260922/assemblies.full.tsv \
  --annotation-file metadata/production_full_manifest_20260922/annotations.full.tsv \
  --manual-files-dir /home/labuser/rdcheng/gd/manual_files \
  --output-dir audit_reports/production_hierarchy_dry_run \
  --batch-id production-full-20260922 \
  --source public_database_import \
  --source-version 20260922 \
  --dry-run
```

仅当报告无错误、待清理对象均为安全 placeholder，且新增/更新数量与本包摘要一致时，才能继续。

## 5. 写入层级和主文件绑定

```bash
python manage.py import_incremental_hierarchy_manifest \
  --assembly-file metadata/production_full_manifest_20260922/assemblies.full.tsv \
  --annotation-file metadata/production_full_manifest_20260922/annotations.full.tsv \
  --manual-files-dir /home/labuser/rdcheng/gd/manual_files \
  --output-dir audit_reports/production_hierarchy_apply \
  --batch-id production-full-20260922 \
  --source public_database_import \
  --source-version 20260922 \
  --apply
```

该命令在单个数据库事务内写入 Assembly、Annotation，并绑定对应 FASTA/GFF。失败时不得跳过错误强行续跑。

## 6. 绑定其余真实文件

先预演，再应用：

```bash
python manage.py bind_manual_files \
  --path /home/labuser/rdcheng/gd/manual_files \
  --output-dir audit_reports/production_file_binding_dry_run \
  --dry-run

python manage.py bind_manual_files \
  --path /home/labuser/rdcheng/gd/manual_files \
  --output-dir audit_reports/production_file_binding_apply \
  --apply
```

`files.full.tsv` 是完整绑定预期和复核基线。CG14/R498 的多版本 GFF 已由第 5 步按显式 Annotation 代码绑定；3 个非业务文件应保持在例外清单中，不得导入。

## 7. 导入后验收

```bash
python manage.py audit_file_relations
python manage.py validate_new_file_structure --path /home/labuser/rdcheng/gd/manual_files
python manage.py check --deploy --settings=filemanager.settings_production
```

同时抽查 IR64、MH63、CG14、R498：Assembly 页面能打开真实 FASTA 信息，Annotation 页面能读取真实 GFF，CG14/R498 默认 Annotation 指向标准命名 GFF。

## 8. 回滚

1. 立即停止应用写入和后台任务。
2. 保存本次所有 `audit_reports`，不要覆盖失败现场。
3. 恢复维护窗口开始前的数据库备份。
4. 如 `manual_files` 被其他操作改动，恢复对应快照；本手册中的命令本身不修改源文件。
5. 重新执行第 2、3、7 节，只读验收通过后再开放服务。

不要通过手工删除部分 Assembly/Annotation 行来代替数据库恢复，这会破坏默认关系和文件外键的一致性。
