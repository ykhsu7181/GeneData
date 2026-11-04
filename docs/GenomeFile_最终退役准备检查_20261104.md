# GenomeFile 最终退役准备检查

检查日期：2026-11-04
仓库：`D:\gene_manage_system\gene_manage_system`
分支：`feature/external-tool-data-api-v1`

## 1. 检查范围

本次检查合并完成 GenomeFile 退役 T4 和 DeleteModel 前门禁判断。

本次仅执行：

- 只读代码搜索；
- 退役门禁测试；
- Django 配置和 migration state 检查；
- 生产日志来源及旧 410 URL 范围确认。

本次未执行：

- 未创建 DeleteModel migration；
- 未修改 GenomeFile 数据库表；
- 未连接或修改生产数据库；
- 未修改历史 migration；
- 未执行生产日志检查；
- 未进行无关重构。

本报告依据当前工作树，而不是仅依据当前 Git 提交。T1、T2、T3 相关修改目前仍在工作树中，尚未全部提交。

## 2. 代码侧门禁结果

| 检查项 | 结果 | 依据 |
|---|---:|---|
| GenomeFile 活动业务读取 | 0 | T3 AST 门禁及全仓搜索通过 |
| GenomeFile 活动业务写入 | 0 | T1 写入门禁通过 |
| 在线 fallback | 0 | 无 `.files`、`legacy_genomefile`、`organism_fallback` 活动路径 |
| 双读/双写 | 0 | 活动业务链路仅使用 DataFile + FileRelation |
| 前端旧 GenomeFile URL 依赖 | 0 | 前端退役和旧 URL 测试通过 |
| GenomeFileAdmin 依赖 | 0 | 无 GenomeFile Admin 注册 |
| CodonW → GenomeFileViewSet 依赖 | 0 | CodonW 解耦测试通过 |

`views.py` 中的 `genome_file` 局部变量和 `get_context_genome_file` 表示 DataFile 类型的基因组 FASTA 文件，不是对 GenomeFile model 的读取。

活动的 `query/genome-files/` 也是基于 DataFile + FileRelation 的查询接口，不属于旧 GenomeFile 410 API。

## 3. 剩余 GenomeFile 引用分类

### 3.1 A 类：历史 migration——必须保留

以下 migration 构成完整历史状态链，不能修改或删除：

- `django2/files/migrations/0001_initial.py`
  - 创建 GenomeFile model。
- `django2/files/migrations/0002_auto_20250701_2239.py`
  - 修改 GenomeFile 历史字段。
- `django2/files/migrations/0003_alter_genomefile_category.py`
- `django2/files/migrations/0004_alter_genomefile_category.py`
- `django2/files/migrations/0005_alter_genomefile_category.py`
- `django2/files/migrations/0006_tablecolumnconfig.py`
  - migration 依赖链引用 GenomeFile category migration。
- `django2/files/migrations/0008_genomefile_accession.py`
- `django2/files/migrations/0009_assembly_annotation_genomefile_links.py`
- `django2/files/migrations/0010_backfill_default_assembly_annotation.py`
  - 历史数据 migration，通过 `apps.get_model()` 读取和更新历史 GenomeFile。
- `django2/files/migrations/0012_alter_genomefile_category_variableblocks.py`
- `django2/files/migrations/0013_accession_genetic_stock_id_assembly_metadata.py`
  - migration 依赖链引用上一 GenomeFile migration。

其中 `0010_backfill_default_assembly_annotation.py` 的历史读写必须保持原样，否则新数据库无法完整重放 migration 历史。

### 3.2 B 类：审计、验证和退役工具——可在删表前使用

以下 management command 仍直接读取 GenomeFile：

- `audit_file_migration`
- `audit_legacy_fallback`
- `backfill_genomefile_to_datafile`
- `cleanup_placeholder_hierarchy`
- `compare_accession_files`
- `compare_annotation_files`
- `compare_overview_files`
- `generate_legacy_fix_todo`
- `migrate_placeholder_hierarchy`
- `report_genomefile_archive_status`
- `report_legacy_usage`
- `validate_new_file_structure`

此外：

- `cleanup_data` 已禁用；
- `link_genomefiles_to_accessions` 已禁用；
- `command_lifecycle.py` 仅保存命令生命周期分类。

这些工具不在在线业务调用链中，因此当前不阻挡创建 DeleteModel migration。但删除 GenomeFile model/table 后，它们不能继续 import 或查询 GenomeFile，必须在 DeleteModel 同一变更中退役、删除旧 import，或者改写为不访问旧表的最终状态检查。

### 3.3 C 类：410 archive adapter——暂时保留

继续保留：

- `django2/files/archive_views.py` 中的 `ArchivedGenomeFileViewSet`；
- `django2/files/urls.py` 中的旧 GenomeFile 410 路由；
- `django2/files/views.py` 中旧管理端点的 410 响应。

410 adapter 不 import、不读取、不写入 GenomeFile，因此删除 model/table 后仍可继续返回 `410 Gone`。

### 3.4 D 类：测试和历史证据

DeleteModel 阶段需要处理的测试包括：

- 创建 GenomeFile fixture 的 API 和 410 测试；
- `test_legacy_models_and_api.py`；
- `test_backfill_genomefile_to_datafile.py`；
- 审计、验证和比较命令测试；
- `test_stage12b_archive_genomefile.py`。

应继续保留但需要调整断言的测试包括：

- T1 写入门禁；
- T3 读取和 fallback 门禁；
- CodonW 解耦测试；
- 410 路由测试；
- DataFile + FileRelation API 测试。

仓库文档和 `AGENTS.md` 中的 GenomeFile 退役说明属于历史证据，不是活动代码依赖。

### 3.5 E 类：不应继续存在的活动代码

结果：`0`

未发现活动 serializer、view、service、admin、frontend 或 CodonW 对 GenomeFile model 的 import、query、write 或 fallback。

## 4. 生产环境唯一外部检查

唯一尚需人工执行的生产外部检查是：

> 确认 T3 部署后到计划删表前，旧 GenomeFile 410 URL 是否仍有真实访问。

### 4.1 仓库确认的真实日志链路

`ArchivedGenomeFileViewSet` 每次被调用都会写入：

```text
Archived GenomeFile API called: method=... path=...
```

`django2/filemanager/settings_production.py` 将 `files` logger 同时写入 console 和 FileHandler。FileHandler 路径来自：

```text
GENEDATA_LOG_PATH
```

仓库部署文档使用 `/home/labuser/rdcheng/gd/logs/filemanager.log`，但生产环境可能通过环境变量覆盖，因此不能直接假定该路径。

仓库中的 Nginx 示例没有声明生产 `access_log` 路径，因此不能猜测 Nginx 日志位置。旧 GenomeFile adapter 自身的应用日志是本检查的直接证据来源。

### 4.2 生产只读检查命令

先确认活动 Gunicorn 进程、工作目录、settings 和日志环境变量：

```bash
PIDS=$(pgrep -f 'gunicorn.*filemanager\.wsgi:application')
test -n "$PIDS" || { echo "GeneData gunicorn not found"; exit 1; }

for pid in $PIDS; do
  printf 'PID=%s CWD=%s\n' "$pid" "$(readlink -f "/proc/$pid/cwd")"
  tr '\0' '\n' < "/proc/$pid/environ" \
    | grep -E '^(DJANGO_SETTINGS_MODULE|GENEDATA_LOG_PATH)=' || true
done

for pid in $PIDS; do
  for fd in /proc/"$pid"/fd/*; do
    readlink -f "$fd" 2>/dev/null
  done
done | sort -u | grep -E '/filemanager[^/]*\.log$'
```

从上述输出确认唯一实际应用日志文件后执行：

```bash
APP_LOG='上一步确认的实际路径'

grep -F 'Archived GenomeFile API called:' "$APP_LOG" | tail -n 200
```

### 4.3 需要检查的旧 410 URL

包括：

- `/gd/api/download/`
- 以下前缀下的 `genome-files/*`：
  - `/gd/api/files/`
  - `/gd/api/admin/`
  - `/api/files/`
  - `/api/admin/`
- 同一前缀下的：
  - `download-transcriptome/`
  - `transcriptome-types/`

应按照“T3 部署后至计划删表前”的约定观察窗口判断。

存在旧 URL 访问记录不会阻止创建 DeleteModel migration，但在生产正式应用 migration 前，必须确认调用方，并决定是否继续保留当前 410 adapter。

## 5. 最终门禁判断

```text
READY_FOR_DELETE_MODEL = YES
```

该结论表示：

- 当前工作树满足创建 DeleteModel migration 的代码条件；
- 可以开始准备下一次最小 DeleteModel 变更；
- 不表示已经批准在生产执行 migration；
- 生产应用前仍需完成第 4 节的唯一日志访问检查；
- DeleteModel 应建立在 T1、T2、T3 修改完整纳入目标分支之后。

## 6. 下一步最小实施方案

下一阶段仅实施以下内容：

1. 新增一个 migration，仅删除 GenomeFile model；
2. 从 `django2/files/models.py` 删除 GenomeFile model 定义；
3. 删除或退役删表后已无用途的 management command import 和旧表查询；
4. 完整保留所有历史 migration；
5. 暂时保留 `ArchivedGenomeFileViewSet` 和全部 410 route；
6. 更新依赖 GenomeFile fixture/table 的测试；
7. 保留并更新零读取、零写入、无 fallback、CodonW 解耦和 410 路由门禁；
8. 运行 `makemigrations --check`、完整后端测试和最小前端退役测试；
9. 不进行任何无关模型、API、前端或通用代码重构。

## 7. 验证结果

- 后端退役门禁：25 个测试通过；
- 前端退役和旧 URL 检查：9 个测试通过；
- Django system check：通过；
- `makemigrations --check --dry-run`：`No changes detected`；
- `git diff --check`：通过。

## 8. 结论

代码侧 DeleteModel 前门禁已经通过。

当前唯一未完成事项是生产环境旧 410 URL 最近访问情况的人工只读检查。完成该检查并确认处置策略后，可以进入 GenomeFile DeleteModel 最小实施阶段。
