# GeneData 整改与技术债治理方案

## 1. 文档目的

本方案用于治理 GeneData 当前的历史技术债，同时保持已经完成的 `DataFile + FileRelation` new-only 文件主链路稳定运行。文中的“关系缺失”“角色不一致”等表述，除已有审计报告明确证实外，均视为生产数据待审计项，而不是预先认定的缺陷。

治理原则：

1. 先审计、后修改：任何批量修复前必须输出只读审计报告与 dry-run 结果。
2. 先兼容、后清理：旧 `GenomeFile` 仅作为历史归档和审计依据，不恢复业务 fallback。
3. 先数据、后页面：页面无数据时先验证对象关系、文件关系和接口结果，再调整前端。
4. 小批量、可回滚：每类改动独立提交、独立验证，不做跨模块的大范围重构。
5. 新功能只使用新体系：文件查询、文件下载、扫描写入只使用 `DataFile + FileRelation`。
6. 代码与生产一致：开发环境存在模型、命令或测试，不等于生产环境已迁移、已导入或已验收；发布时必须分别验证代码版本、迁移版本和数据覆盖率。
7. 先过安全门禁：在继续 Query/API、前端或性能治理前，必须先完成 Security Baseline，并单独留存生产 canary 证据。

## 2. 目标架构

### 2.1 文件资产关系

```text
Species
  └─ Accession
       ├─ Assembly
       │    └─ Annotation
       ├─ DatasetAccession ─ Dataset ─ Project
       └─ Sample

DataFile ─ FileRelation ─ accession / assembly / annotation / dataset / sample
```

说明：`DataFile` 不是 Assembly 或 Annotation 的从属表。它通过 `FileRelation` 与不同业务对象建立多对多关系；同一文件可同时关联 Accession、Assembly、Annotation、Dataset 或 Sample。

### 2.2 约束边界

- 文件查询服务只返回 `source=new_relation`。
- 下载地址统一为 `/gd/api/files/data-files/<file_id>/download/`。
- `GenomeFile` 仅允许被 backfill、audit、validate、archive report、历史测试和只读后台使用。
- 业务接口不得返回 `/genome-files/` 下载地址。
- `raw_data_manifest` 仍是人工登记的原始文件资产清单，不与 ENA 外部 FASTQ 信息强行混合。

## 3. 当前技术债与优先级

| 优先级 | 问题 | 风险 | 治理目标 |
| --- | --- | --- | --- |
| P0 | 密钥、数据库密码和宽松 CORS 配置 | 生产安全风险 | 环境变量化、最小跨域授权、凭据轮换 |
| P0 | 生产 canary 缺少可审计证据 | 开发验收被误当成生产验收 | 在生产环境独立执行并归档 commit、环境、batch report 和 audit 结果 |
| P0 | 生产数据关系完整性尚未完成最终验收 | 若生产库存在缺失或错误关系，会造成 Accession 详情和列表页空数据 | 先审计生产覆盖率，仅对实际异常记录通过 manifest 或修复命令补齐 |
| P0 | 生产代码、迁移和导入数据可能不同步 | 开发已修复但生产页面仍显示旧结果 | 发布前核对目标目录、迁移状态、命令可发现性和导入验收结果 |
| P1 | Query context 曾使用 `assemblies.first()` | multi-Assembly 下可能误挂查询结果 | 已统一显式/default/唯一/ambiguous 解析规则；持续以回归测试防复发 |
| P1 | `views.py` 职责过多 | 修改容易回归 | 已抽离查询 parser、DataFile 下载和归档 API adapter；CodonW/admin 的物理拆分继续增量治理 |
| P1 | Genome/Annotation 前端组件过大 | 页面性能和维护困难 | 拆分筛选、表格、抽屉、可视化和请求逻辑 |
| P1 | 旧 GenomeFile URL 与 API 仍保留兼容路由 | 误用旧链路 | 已统一返回 410 并记录调用；生产日志确认零调用后再删除 |
| P1 | 仓库仍跟踪凭据文档、重复生产配置和历史压缩包 | 凭据泄露、配置漂移和仓库膨胀 | 先轮换凭据，再单独清理并完善 ignore 规则 |
| P2 | `.fai` 缺失时扫描 FASTA | 大文件场景下卡顿 | 先做存在性与陈旧检查，按监控结果再加缓存 |
| P2 | 测试目录与 CI 规则分散 | 回归发现晚 | 建立分层测试与渐进式 CI 门禁 |

### 3.1 2026-09-10 项目核验基线

当前核验基于：

```text
branch: feature/stage5-scan-files-dual-write
commit: 3e747068f82fafdc190def95cfdde2772ff53f3a
```

已确认：

- Python ingestion hardening Phase 1–5 已进入当前 HEAD。
- ingestion 相关 46 个目标测试通过。
- `python manage.py check` 通过。
- `python manage.py makemigrations --check --dry-run files` 显示无 migration 变化。
- 开发 batch acceptance 为 `READY_TO_IMPORT=YES`、`post_apply_import=PASS`、`post_apply_audit=PASS`。

未确认：

- 上述 batch 报告明确标记为 `source=development_acceptance`，不得将其作为生产 canary 证据。
- 仓库内尚无可独立审计的生产 canary 报告。
- `python manage.py check --deploy --settings=filemanager.settings_production` 在当前环境因硬编码日志路径不存在而无法完成。

当前门禁：

| 门禁 | 状态 |
| --- | --- |
| Python ingestion hardening Phase 1–5 | PASS |
| 开发 batch acceptance | PASS |
| 生产 canary | NOT VERIFIED |
| Security Gate | FAIL / OPEN |
| Query/API Gate | PASS（开发环境；生产旧 URL 调用审计待完成） |
| Repository Cleanup Gate | OPEN |
| CI Gate | OPEN |

### 3.2 强制执行顺序

```text
Stage A  Security Baseline
    ↓
生产 canary 与数据关系验收
    ↓
Stage B  Query / API 治理
    ↓
Stage C  前端与性能治理
    ↓
Stage D  Repository Cleanup
    ↓
Stage E  CI / Release Gate
```

## 4. Stage A：Security Baseline

### 4.1 已核实问题

- `django2/filemanager/settings.py` 仍包含固定 `SECRET_KEY`、`DEBUG=True`、`ALLOWED_HOSTS=['*']`、`CORS_ALLOW_ALL_ORIGINS=True` 和明文数据库配置。
- `django2/filemanager/settings_production.py` 通过 `from .settings import *` 继承基础配置，未显式覆盖 `CORS_ALLOW_ALL_ORIGINS=False`，因而生产有效配置仍可允许全部 origin。
- 生产配置仍包含明文数据库密码，且没有独立覆盖源码内 `SECRET_KEY`。
- 生产 `filemanager.log` 和 `MANUAL_FILES_DIR` 使用硬编码绝对路径，配置不可移植。
- 仓库跟踪 `账号密码.docx`，且根目录与 Django package 内的两份 `settings_production.py` 内容不同。

### 4.2 实施要求

1. `SECRET_KEY`、DB NAME/USER/PASSWORD/HOST/PORT、CORS origins、日志路径和 `MANUAL_FILES_DIR` 改为环境配置。
2. 生产必须显式设置 `DEBUG=False` 和 `CORS_ALLOW_ALL_ORIGINS=False`。
3. 生产关键变量缺失时 fail-fast，不允许回退到弱默认值。
4. 新增不含真实凭据的 `.env.example` 和配置说明。
5. 先在生产服务器配置环境变量，再部署新代码，最后轮换 DB password 和 `SECRET_KEY`。
6. 凭据轮换后再单独清理明文凭据文档，并评估 Git 历史清理。

### 4.3 Security Gate

```text
源码中无生产 DB password 和生产 SECRET_KEY
production DEBUG=False
production CORS_ALLOW_ALL_ORIGINS=False
生产关键环境变量缺失时 fail-fast
python manage.py check --deploy --settings=filemanager.settings_production 可完成
生产服务正常启动
关键 API 正常
```

只有达到 `SECURITY GATE = PASS` 后，才进入后续 Query/API 治理。

## 5. 已完成 ingestion 基线与生产数据验收

### 5.1 当前基线边界

Python ingestion hardening Phase 1–5 已完成新写入防复发、metadata overwrite policy、统一 import report/provenance、file write service hardening 和 `import_data_batch`。这一结论仅表示代码和开发验收已完成，不表示生产数据已验收。

新写入必须继续满足：

- unknown accession/sample/role 不创建 `DataFile`。
- 任何 importer 不产生 relationless `DataFile`。
- multi-Assembly 无明确上下文时报 ambiguous，不允许 `first()` 猜测。
- dry-run 不写库，rerun 幂等。
- `import_data_batch --apply` 执行后自动运行导入与关系审计，结果写入 batch reports。

### 5.2 固定执行的只读审计

在开发环境和生产环境分别执行。生产报告必须带时间戳归档，并在发布记录中注明数据版本：

```bash
python manage.py validate_new_file_structure --settings=filemanager.settings_production
python manage.py audit_file_relations --settings=filemanager.settings_production
python manage.py audit_genome_transcriptome_readiness --output-dir audit_reports --settings=filemanager.settings_production
```

审计重点：

- Accession 是否已关联 Species。
- Assembly 是否关联 Accession，Annotation 是否关联 Assembly。
- DataFile 是否至少有一条有效 FileRelation。
- `related_type`、`related_id`、`file_role` 是否为空或失效。
- DatasetAccession、Sample 与 Accession 的覆盖率是否符合已审核 manifest；对未覆盖记录输出原因，而不是默认判定为数据错误。
- Genome、Annotation、Transcriptome 文件是否分别能按业务关系查到。

### 5.3 canonical `file_role` registry 与历史角色边界

不要假定生产库历史数据已全部使用 canonical role，也不要预设 `genome_fasta` 等新的 rename 目标。先统计：

```bash
python manage.py shell --settings=filemanager.settings_production -c "
from django.db.models import Count
from files.models import FileRelation
print(list(FileRelation.objects.values('file_role').annotate(total=Count('id')).order_by('file_role')))
"
```

新写入统一使用 `django2/files/services/ingestion/roles.py` 中的 canonical validator。当前保留已有业务 role，不做历史 mass rename。unknown role 必须拒绝写入。

canonical roles 为：

```text
genome
annotation
centromere
codon
coreBlocks
variableBlocks
miRNA
tRNA
rRNA
TEs
transcriptome.all
transcriptome.root
transcriptome.stem
transcriptome.leaf
transcriptome.panicles
transcriptome.shoot
hifi_reads
raw_reads_R1
raw_reads_R2
rnaseq_raw
wgs_reads
other
```

历史角色只做盘点，先形成并冻结映射表：`历史角色`、`数量`、`业务含义`、`候选 canonical 角色`、`处理动作`。不得将 `genome` 自动 rename 为 `genome_fasta`，也不得仅根据名称相似自动合并 raw/RNA-seq roles。

若发现确有需要规范化的历史角色，再新增或使用独立的规范化命令，要求：

1. 支持 `--dry-run`。
2. 输出变更明细 TSV：文件、旧角色、新角色、关联对象、原因。
3. 仅按明确映射更新，不靠文件名模糊猜测。
4. 可重复执行，不重复创建关系。
5. 修复后重新运行上述审计。

### 5.4 Assembly 与 Annotation 上下文修复

对 `manual_files` 已存在的 genome/annotation 文件，使用：

```bash
python manage.py reconcile_assembly_annotation_context --dry-run --output-dir audit_reports
```

确认明细无误后执行正式命令。验收要求：

- 不再为无真实文件的 Accession 人工补出 `default Assembly`。
- `backfill_assembly_from_genome_relations` 默认不创建 placeholder Assembly；`--allow-placeholder` 仅允许用于显式 legacy repair，不得用于日常导入。
- 有 genome 文件的 Accession 必须存在可用 Assembly，并有 `related_type=assembly` 的 genome 文件关系。
- 有 annotation 文件的 Accession 必须存在 Annotation，且 Annotation 关联正确 Assembly。
- 重复执行不新增重复 Assembly、Annotation 或 FileRelation。

### 5.5 Dataset 与 Sample 补齐

使用已审核的 manifest 分别导入：

```bash
python manage.py import_dataset_manifest --input metadata/prjeb73710/dataset_manifest.PRJEB73710.v2.tsv
python manage.py import_sample_manifest --input metadata/prjeb73710/sample_manifest.PRJEB73710.v2.tsv
python manage.py import_dataset_accession_manifest --input metadata/prjeb73710/dataset_manifest.PRJEB73710.v2.tsv
```

导入前先 dry-run；导入后检查：

- DatasetAccession 已将 Dataset 与 Accession 连接。
- Sample 关联了 Accession，并保留 `biosample_accession` 与 `experiment_accession`。
- 页面中“数据集”和“样本”为空时，先检查关系表，不以文件存在与否代替业务关系。

对新 batch 优先使用 `import_data_batch`统一编排，不把多个单命令的手工成功视为 batch 验收成功。

### 5.6 生产 canary 证据要求

生产验收必须单独归档：

```text
environment: production
code_commit: <deployed commit>
batch_id: <production canary batch>
READY_TO_IMPORT=YES
post_apply_import=PASS
post_apply_audit=PASS
error_count=0
conflict_count=0
unmapped_count=0（或具备已审批豁免）
```

未留存上述证据时，状态必须保持 `PRODUCTION CANARY = NOT VERIFIED`。

## 6. Stage B：查询和接口治理

### 6.1 实施结果与 Service 层边界

Stage B 已在开发代码中实施并通过自动测试：

- 已建立 `django2/files/parsers/`，将 FASTA/GFF/BED、archive、chromosome alias/length 和 query codon payload 解析从 `query_views.py` 抽离。
- `query_views.py` 不再依赖大型 `files.views`，DataFile 下载与 GenomeFile 归档响应也已拆为独立 adapter。
- Query context 已统一到 `files/services/accession_context.py`；显式 ID 无效不再 fallback，多 default 或 multi-Assembly/Annotation 无唯一上下文时返回结构化 `409 ambiguous_context`。
- 旧 `/genome-files/*`、旧 transcriptome 和旧根下载路由仍保留 URL 兼容，但统一返回 `410 Gone` 并记录调用日志，不再进入旧业务查询/下载实现。
- active business query/write/download 已通过静态回归测试确认不使用 `GenomeFile.objects`。

保留并统一以下服务职责：

- `file_relation_service`：按业务对象读取文件及主文件。
- `accession_context`：组装 Accession、Assembly、Annotation 上下文，不直接访问 GenomeFile。
- `dashboard_service`：首页统一统计口径。
- 列表查询服务：Data Overview、Genome、Transcriptome、Raw Data 分别负责筛选、分页和序列化。
- 解析服务：FASTA、GFF、BED、压缩包、chromosome alias 和 chromosome length 处理从 HTTP 层抽离。

禁止在 View 中直接混合：数据库聚合、文件系统扫描、FASTA/GFF 解析、下载响应和复杂业务规则。

### 6.2 Parser extraction

新增：

```text
django2/files/parsers/
├── __init__.py
├── fasta.py
├── gff.py
├── bed.py
├── archive.py
└── codon.py
```

parser 只负责格式解析，service 负责业务规则，view 只负责 HTTP 参数和 Response。抽取时保持 API schema 和错误行为不变。

### 6.3 Context resolution

Assembly 必须统一使用：

```text
显式 assembly_id
→ 使用指定 Assembly

否则存在且只有一个 is_default=True
→ 使用 default

否则只有一个 Assembly
→ 使用唯一 Assembly

否则
→ ambiguous，禁止 first() 猜测
```

Annotation 使用同等规则。规则统一收口到 `files/services/accession_context.py`，禁止在不同 View/Service 各自实现 fallback。

MySQL 当前不支持项目对 default Assembly/Annotation 定义的条件唯一约束，因此 context resolver 和写入服务必须显式检测多 default 冲突，不能只依赖数据库约束。

### 6.4 `views.py` 与 `query_views.py` 拆分边界

`views.py` 和 `query_views.py` 都纳入治理范围，但不进行一次性目录大迁移。推荐按可独立验证的功能逐步抽取：

```text
views.py       -> archive/admin、download、CodonW、普通 API adapter
query_views.py -> HTTP adapter、Genome/Annotation 查询 adapter
parsers/       -> fasta、gff、bed、archive
services/      -> genome、annotation、feature track、列表查询
```

每次抽取一个功能模块，保持 URL、响应字段和行为测试不变；抽取完成后，View 只负责参数读取、Service 调用和 Response 返回。

### 6.5 API 收口

1. 建立页面到 API 的文档清单。
2. 搜索并替换业务页面中的旧 `/genome-files/` 调用。
3. 对旧 URL 先返回 `410 Gone`，并记录调用次数。
4. 内部系统可通过前端代码、部署脚本和 Nginx 日志确认无调用后删除旧 URL。
5. 不把“保留归档 model”误认为“保留旧业务 API”。

### 6.6 Stage B Gate

- **PASS**：View 不再包含 active query 所需的复杂 FASTA/GFF/BED/archive parser。
- **PASS**：Query context 不使用 arbitrary `first()`，多 default 和 multi-Assembly/Annotation 明确报 ambiguous。
- **PASS**：关键 API success response schema 和 DataFile download URL 保持不变。
- **PASS**：Stage B 所属 API、command、unit、regression 显式测试集共 217 个测试通过。
- **PASS**：旧 GenomeFile API 保持 archived/410 行为并记录调用。
- **PASS**：active business query/write/download 无 `GenomeFile.objects`。
- **PASS**：`python manage.py makemigrations --check --dry-run files` 无迁移变化，`python manage.py check` 无问题。

Stage B 的开发门禁通过不解除 Stage A：Security Gate 仍为 `FAIL / OPEN`，生产发布仍被阻断。删除旧 URL 前还必须根据 Nginx/应用日志证明正式客户端调用为零。`views.py` 中未进入 active query 路由的 CodonW/admin 与历史实现仍较大，后续只做增量物理拆分，不影响本阶段业务边界结论。

## 7. Stage C：前端与性能治理

### 7.1 组件拆分

优先拆分：

- `GenomeCard.vue`：筛选栏、可视化视图、数据列表、文件抽屉。
- `AnnotationView.vue`：搜索选择、染色体列表、Feature 表、详情抽屉。
- `DataChartView.vue`：筛选栏、矩阵、明细表、文件抽屉。

拆分要求：接口返回结构不变；每次只拆一个页面；保留组件行为测试。

### 7.2 Genome 与 Annotation 页面

- 输入 Accession 后支持搜索按钮和 Enter 精确匹配。
- Genome 可视化只在已选择有效 Accession、Assembly、Chromosome 后加载数据。
- Annotation 页面只展示已通过 Annotation/FileRelation 关系定位的文件。
- 无数据时显示明确空状态，不伪造数据。

### 7.3 首页性能验收

已完成的基础治理：

1. 首页使用 dashboard 聚合接口，不在前端拼多个统计接口。
2. DistributionPanel、GeoMapPanel 使用异步加载和可视区域延迟渲染。
3. GeoJSON 与 ECharts 初始化延迟到组件实际可见后执行。

待验收指标：

1. 首屏加载时间基线。
2. dashboard API 的 P95 响应时间。
3. ECharts 初始化耗时。
4. GeoJSON 请求与解析耗时。

只有指标证明仍存在瓶颈时，才引入缓存或进一步拆包。

### 7.4 `.fai` 策略

- 优先读取已关联的 `.fai` DataFile。
- 缺失时仅做受控 FASTA 扫描：限制路径、大小和超时，并记录 warning。
- 首先检查 `.fai` 是否存在及是否陈旧；缓存不是首要工作。

### 7.5 `is_primary` 约束

先审计同一业务对象和文件角色下是否存在多个 primary，并确认是否存在并发设置 primary 的真实场景。低并发后台不预先引入复杂锁；仅当审计和并发场景证明必要时，再增加事务、行锁或数据库约束。

### 7.6 当前实施状态（2026-09-10）

- **PASS（首个页面拆分批次）**：`GenomeCard.vue` 的数据列表和文件抽屉已拆为独立展示组件，查询、下载、路由和状态仍由页面层管理，API schema 未改变。
- **PASS**：Genome 精确 Accession 搜索同时支持按钮和 Enter；可视化现在要求有效 Accession、明确 Assembly 和 Chromosome。多 Assembly 仅在唯一 Assembly 或唯一 default 时自动选择，不再猜测第一条记录。
- **PASS**：FASTA 查询优先读取与本次 Assembly/Accession 上下文明确定义关系、文件名匹配且不陈旧的 `.fai` DataFile；无可用索引时按 512 MiB/5 秒预算受控扫描并记录 warning，超限返回可识别的 `fasta_scan_limit_exceeded`。
- **PASS**：`audit_file_relations` 新增同一 `(related_type, related_id, file_role)` 多个 `is_primary=True` 的只读审计与报告；本阶段未增加锁或数据库约束。
- **PASS（构建基线）**：生产构建成功；当前 app 入口约 1.53 MiB，vendor JavaScript 约 1.17 MiB，构建工具仍报告体积告警。该结果作为后续浏览器性能验收的拆包候选证据，不直接触发缓存变更。
- **DEFERRED**：遵循“每次只拆一个页面”，`AnnotationView.vue`、`DataChartView.vue` 及 Genome 筛选/可视化子组件继续按独立批次拆分。
- **DEFERRED**：首屏时间、dashboard API P95、ECharts 初始化及 GeoJSON 请求/解析耗时必须在可重复的浏览器与部署环境中采集；未取得数据前不宣称 Stage C 性能验收完成。
- **DEFERRED**：生产数据上的 multiple-primary 报告和并发写入场景确认仍需在 Stage A 安全门禁关闭后由人工执行；当前只完成无生产写入的审计能力与自动测试。
- **OPEN**：全量 Node 静态测试为 39 项中 34 项通过，5 项为进入 Stage C 前已存在的路由/测试期望不一致；本批次新增 Genome 边界测试通过。后续应在独立前端测试治理批次确认产品路由后修正，避免混入组件拆分。

## 8. Stage D：仓库清理与历史命令退役

### 8.1 Repository Cleanup

当前已核实：

- Git 跟踪 6 个根目录 `django2.zipYYYYMMDD` 历史归档和 5 个 `vue_project` zip-like 归档。
- Git 跟踪 `账号密码.docx` 和两份内容不同的 `settings_production.py`。
- 还有未跟踪的 `django2.zip20260814`、`django2.zip20260824-1`、`vue_project/dist.zip20250824-1` 和 `vue_project/dist.zip20260814`。
- 根 `.gitignore` 中的 `*.zip` 无法匹配 `django2.zip20260814` 这类后缀为 `.zipYYYYMMDD` 的文件。
- `django2/` 下已累积大量未跟踪 importer log/unmapped/conflict 报告，当前 ignore 规则未有效覆盖。

1. 先使用 `git ls-files`、发布目录清单和团队确认，区分被跟踪源码、部署备份、运行产物和个人资料。
2. 历史 `django2.zip*`、`dist.zip*`、日志、审计 TSV、构建产物不纳入源码仓库，并加入 `.gitignore`。
3. 账号密码类文档不得保留在仓库；若曾提交过明文凭据，先轮换凭据，再评估 Git 历史清理。
4. 删除必须单独提交，不与迁移、数据修复或业务重构混在同一提交。

5. ignore 规则必须覆盖 `*.zipYYYYMMDD*`、batch `tmp/` 和 importer `*_log_*`/`*_unmapped_*`/`*_conflicts_*` 运行产物，但不得将需要归档的生产验收报告无区分忽略。

### 8.2 历史命令分类退役

```text
迁移/审计/验证命令：保留到归档策略和数据保留期结束
演示或临时命令：确认生产不用后删除
旧数据修复命令：迁移完成、审计 PASS 且具备替代审计后归档或删除
GenomeFile 归档读取命令：不属于业务主链路，按审计保留策略处理
```

不得因为命令仍能运行就永久保留，也不得因为目标是 new-only 就立即删除所有历史审计能力。

### 8.3 当前实施状态（2026-09-10）

- **PASS**：当前版本删除 11 个已跟踪历史压缩包（合计约 209 MiB），未删除工作区内未跟踪的本地备份。
- **PASS**：`账号密码.docx` 和根目录重复 `settings_production.py` 已从当前版本移除；活动配置仅保留 `django2/filemanager/settings_production.py`。
- **PASS**：生产 `SECRET_KEY`、数据库密码改为必需环境变量，其他数据库连接项允许环境变量覆盖；`.env.example` 只保留空值和非敏感默认值。
- **PASS**：根 `.gitignore` 覆盖 `*.zipYYYYMMDD*`、batch `tmp/` 及 importer/backfill/reconcile 运行报告；不再无差别忽略 `audit_reports/`，生产验收报告可显式归档。
- **PASS**：所有 `files` management command 已纳入机器可校验的生命周期清单，并由回归测试防止新增未分类命令。
- **DEFERRED**：`cleanup_data`、`seed_ir64_demo_hierarchy` 当前标记为 `retire_pending_usage_confirmation`。只有生产脚本、定时任务、runbook 和调用日志均证明零使用后才删除。
- **DEFERRED / SECURITY**：凭据文件及生产数据库密码曾进入 Git 历史；当前版本删除不能清除历史。必须轮换相关凭据，再单独评估受协调的历史重写和所有 clone 的同步方式。

## 9. Stage E：测试、CI 与交付门禁

当前仓库没有 `.github` 目录或 GitHub Actions workflow，`CI GATE = OPEN`。

### 9.1 测试分层

```text
files/tests/unit/          模型、服务、格式化规则
files/tests/commands/      导入、审计、修复命令
files/tests/integration/   API、下载、页面数据关系
vue_project/tests/         页面结构、关键交互、构建检查
```

每项数据修复命令必须具备：dry-run、幂等测试、日志/明细报告测试、正式执行测试。

MySQL 测试会报告条件唯一约束不受支持和超长唯一 `CharField` 风险；这些 warning 必须记录为已知风险，不得被 CI 无声忽略。CI 应使用独立测试库，避免因本地遗留 `test_gene_manage` 而进入交互删库提示。

### 9.2 CI 接入顺序

1. Django `check`、迁移检查、核心单测。
2. 前端构建。
3. 核心 API 与页面行为测试。
4. 在修复现有 lint 基线后，再将 lint 设为阻塞门禁。

### 9.3 CI Gate

```text
python manage.py check
python manage.py makemigrations --check --dry-run
核心 Django tests
npm install / npm ci
npm run build
前端关键行为测试
核心 API integration tests
security check
```

### 9.4 当前实施状态（2026-09-10）

- **IMPLEMENTED / 待首次 CI 验证**：新增 GitHub Actions workflow，PR、`main`/`master` push 和手工触发均执行独立 Django 与前端 job。
- **IMPLEMENTED / 待首次 CI 验证**：Django job 使用临时 MySQL 8 service 和环境变量连接，不接触生产数据库；依次执行 system check、迁移漂移检查、完整 `files` 测试和 production deploy check。
- **PASS**：原 `files/tests.py` 已迁入 `files/tests/` package，消除 `python manage.py test files` 的模块发现冲突。
- **SECURITY EXCEPTION / OPEN**：按当前项目要求，基础 settings 暂时保留本地数据库密码作为 fallback；CI 仍通过 `GENEDATA_DB_PASSWORD` 覆盖。由于凭据仍在源码和 Git 历史中，Security Gate 不得标记为 PASS。
- **PASS**：前端新增标准 `npm test` 入口，`package-lock.json` 已与声明依赖同步；5 个落后于当前路由/拆包实现的测试期望已校正，`npm ci`、全量 39 项行为测试和 production build 均通过。
- **PASS**：MySQL 条件唯一约束和超长 unique `CharField` warning 保持可见，未使用 silence 绕过。
- **LOCAL BLOCKED / CI COVERED**：本机已成功发现 238 项 Django 测试，但 `python manage.py test files` 因本地 MySQL 拒绝当前凭据（1045）而未启动；不得据此声称本地全量测试通过，首次 GitHub Actions 的隔离 MySQL 结果仍须审阅。
- **OPEN / STAGE A**：production deploy check 当前对 error 阻塞，但仍显示 HSTS、SSL redirect、secure cookie 等 Stage A warning；在代理/HTTPS 策略人工确认前不把 warning 提升为阻塞。
- **DEFERRED**：lint 在现有基线专项清理完成前不进入阻塞门禁。

## 10. 生产发布流程

1. 创建数据库备份，并演练或确认恢复方式；TSV 明细仅用于审计和定位，不能替代数据库备份、事务、反向命令或回滚 SQL。
2. 将代码包解压到新版本目录，确认 `manage.py`、`files`、`filemanager` 均来自目标目录。
3. 安装依赖并执行：

```bash
python manage.py migrate --settings=filemanager.settings_production
python manage.py check --settings=filemanager.settings_production
python manage.py check --deploy --settings=filemanager.settings_production
```

4. 先运行所有导入/修复命令的 `--dry-run`，审阅 TSV 明细。
5. 正式执行数据导入和修复命令。
6. 运行验收审计命令。
7. 构建前端并部署 `dist`。
8. 重启 Django 服务，检查日志、健康接口和关键页面。
9. 如出现关系异常，优先停止后续修复并按备份、反向命令或回滚 SQL 恢复；TSV 明细用于确认受影响范围和问题定位。

## 11. 最终验收标准

### 11.1 数据

- Accession、Species、Assembly、Annotation、Dataset、Sample 的关系经过审计，异常项有明确处理结论或豁免说明。
- 无失效 FileRelation、无重复主文件、无未解释的未关联 DataFile。
- 有真实 genome/annotation 文件的 Accession 可在对应页面查询到。
- Dataset 和 Sample 页面显示基于真实关系，不用假数据填充。

### 11.2 文件体系

- 业务查询返回仅来自 `new_relation`。
- 业务下载仅使用 DataFile 下载接口。
- `scan_files` 只写 DataFile 和 FileRelation。
- GenomeFile 仅作为历史归档，不参与业务写入、查询和下载。
- 运行时业务接口、服务层、扫描/导入写入路径中不使用 `GenomeFile.objects`；迁移、回填、审计、历史测试和只读归档后台按白名单保留。
- production 中旧 `/genome-files/*` 的正式客户端调用已盘点为零后，才允许最终下线归档 URL。

### 11.3 工程质量

- 关键页面无白屏，空数据有明确提示。
- 生产密钥不在代码库明文保存。
- 核心 Django 测试、前端构建和迁移检查通过。
- 每次发布均有备份、dry-run 报告、正式报告和验证记录。
- 开发 acceptance 和生产 canary 报告分开归档，生产报告可追溯到实际部署 commit。
- production 已确认加载目标代码目录，迁移版本、管理命令可发现性、前端 `dist` 版本与发布记录一致。
- `FileRelation.file_role` inventory 已归档；canonical role 映射表已冻结；新增数据不再产生已废弃角色。
- 源码仓库不提交运行日志、审计产物、历史构建包或明文账号密码资料。

## 12. 明确禁止事项

- 不恢复 `GenomeFile` fallback、`organism_fallback`、legacy/dual write。
- 不使用 `/genome-files/<id>/download/` 作为业务下载入口。
- 不因页面缺数据而伪造 Assembly、Annotation、Dataset 或 Sample。
- 不在未审计生产数据前批量修改 `file_role` 或 `is_primary`。
- 不将 canonical `genome`/`annotation` 自动 rename 为 `genome_fasta`/`annotation_gff3`，不开展无审批的历史 role mass rename。
- 不在没有备份和回滚说明的情况下执行生产数据修复。
- 不以“开发命令已存在”代替生产迁移、数据导入和页面验收。
- 不将 `source=development_acceptance` 的 batch report 当作生产 canary 证据。
