---
title: GeneData Dataset 到 DataAsset 实施前审计
status: reference
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes: null
---

# GeneData Dataset 到 DataAsset 实施前审计

## 1. 审计结论

`DataAsset` 取代 `Dataset` 的方向合理，但不能采用简单改名或一次性替换。

当前 `Dataset` 同时承担以下职责：

1. 科研数据身份与名称；
2. 数据类型与版本；
3. Project、Species 和 BioProject 上下文；
4. 数据发布状态与可见性策略；
5. DataFile 分组与访问策略继承；
6. Accession 关联；
7. 外部 Dataset Manifest 和查询过滤边界。

此外，文件与 Dataset 的关系同时存在 `DataFile.dataset` 真实外键和 `FileRelation(related_type="dataset")` 字符串关系。现有访问控制、Manifest 和文件发现服务会合并读取两条路径。这是迁移前必须消除的双重关系来源，不能原样复制到 DataAsset。

代码级 Phase 0 审计已经完成。由于本次任务没有连接生产数据库、生产文件系统或访问日志，真实记录数、悬空关系、双路径冲突和外部调用量仍属于生产只读审计 Gate；在该 Gate 完成前不得执行回填或生产切换。

## 2. 范围与证据边界

- 仓库：`D:\gene_manage_system\gene_manage_system`
- 分支：`feature/external-tool-data-api-v1`
- 审计基线提交：`9a231564d3a5590f35205d74b674505455b8e6ae`
- 审计日期：2026-11-18
- 范围：tracked Django、Vue、migration、测试、命令、API 契约及当时的 DataAsset v0.2 草案；草案的稳定内容现已整合到 active 总体设计
- 未执行：生产数据库查询、生产文件扫描、生产日志分析、schema 修改、数据回填、API 或前端修改

本报告区分：

- **已验证**：由当前代码、migration、测试或 CI 配置直接证明；
- **待生产核验**：需要只读生产查询、日志或人工语义确认；
- **目标决策**：由 active ADR 固定，但尚未实现。

## 3. 已验证的当前模型

### 3.1 Dataset

`django2/files/models.py` 中的 `Dataset` 当前包含：

- 唯一 `dataset_code`；
- `dataset_name`、`dataset_type`、`version`、`description`；
- 可空的 `species` 和 `project`；
- `bioproject_accession`；
- `visibility = private / lab_internal / public`；
- `status = draft / submitted / approved / released / archived`。

这证明 Dataset 既是身份对象，也是发布和访问策略对象，并非纯粹的目录标签。

### 3.2 DatasetAccession

`DatasetAccession` 是 Dataset 与 Accession 的显式中间表：

- 使用真实外键；
- 支持 `primary / derived / reference` 角色；
- `(dataset, accession)` 有唯一约束；
- 一个 Dataset 可关联多个 Accession；
- Accession 不是 Dataset 的必填上级。

### 3.3 DataFile 与 Dataset

`DataFile.dataset` 是可空、`on_delete=PROTECT` 的真实外键。同时，`FileRelation` 的受控字符串类型中也存在 `dataset`。

因此当前至少存在两种 Dataset 文件归属表达：

```text
DataFile.dataset -> Dataset

DataFile <- FileRelation(related_type="dataset", related_id) -> Dataset
```

数据库只能约束第一条路径。第二条路径可能包含无效 ID、悬空关系或与第一条路径不一致的多 Dataset 关联。

### 3.4 DataAsset 当前状态

- 应用代码和 migration 中尚不存在 `DataAsset`；
- 尚不存在 DataAsset API、service、权限实现或前端页面；
- 当前 DataAsset v0.2 文档仍为 draft；
- 因此任何 DataAsset 能力都属于目标设计，不能描述成当前实现。

## 4. 调用面盘点

在 `django2/` 和 `vue_project/` 的 tracked 文件中，共发现 79 个包含 Dataset 语义的文件：

| 分类 | 文件数 | 主要职责 |
| --- | ---: | --- |
| Django migrations | 5 | 创建 Dataset、DataFile.dataset、DatasetAccession 及后续字段变更 |
| 后端测试 | 24 | 模型、导入、访问控制、Manifest、查询和兼容行为 |
| 管理命令 | 13 | Dataset 导入、Accession 映射、发布、校验和审计 |
| services | 10 | 数据概览、访问控制、Manifest、文件发现和 ingestion |
| API v1 | 5 | Dataset Manifest、文件元数据和 OpenAPI 契约 |
| 其他后端 | 4 | models、views、urls 等 |
| Vue 源码 | 6 | Accession 数据集页、数据概览筛选和文件详情 |
| Vue 测试 | 5 | 首页、搜索、数据概览和 Accession 页面契约 |
| 其他文档/模块 | 7 | 兼容说明及其他 Dataset 语义引用 |

该数量是代码调用面，不等于数据库记录数。

## 5. 关键行为审计

### 5.1 访问控制

`datafile_access_service.py` 同时读取：

- `DataFile.dataset_id`；
- `FileRelation(related_type="dataset")`。

访问策略采用最严格 Dataset 策略，并且：

- Dataset 未 released 时按 private 处理；
- public / lab_internal / private 映射为文件有效访问级别；
- Dataset 关系无效时 fail closed；
- `DataFile.access_level=inherited` 且没有 Dataset 策略时按 private 拒绝；
- DataFile 可使用显式访问级别脱离 Dataset，但这不是统一科研数据身份方案。

结论：DataAsset 切换必须先提供等价或更严格的授权决策，不能先删除 Dataset 再补权限。

### 5.2 外部 Manifest 与公开 API

当前存在：

```text
/gd/api/v1/datasets/{dataset}/manifest/
/gd/api/v1/datasets/{dataset}/manifest.tsv
```

Manifest 可按 Dataset code 或 BioProject accession 查找 public + released Dataset，并从两条文件关系路径收集 DataFile。这是已经进入 OpenAPI 和测试的外部契约。

迁移要求：

- 新 canonical API 以 DataAsset 为身份；
- 旧 Dataset 路径如需保留，只能作为有明确下线版本和删除门槛的迁移适配层；
- 适配层不得保存第二份数据，也不得形成无期限平行 API；
- 切换前必须确认真实外部消费者和调用量。

### 5.3 查询和前端

已验证的主要依赖包括：

- Accession 详情的 datasets 页签；
- Data Overview 的 Dataset 筛选、搜索、统计和可选列；
- DataFile 详情中的 Dataset 展示；
- 中英文 Dataset 文案；
- Dataset code、name、type、BioProject 和 run count 响应字段。

前端依赖不多，但字段契约与后端服务绑定较深，必须在 API 切换阶段同步迁移。

### 5.4 导入、发布与审计命令

当前命令覆盖：

- Dataset manifest 导入；
- Dataset-Accession manifest 导入；
- 批量数据导入；
- 外部 Dataset 发布；
- 文件关系和访问策略审计；
- PRJEB73710 特定关系校验。

这些命令不能简单保留为 Dataset 写入入口。DataAsset 切换后，活动写入必须集中到唯一 ingestion/service 路径；旧命令应迁移或退役。

## 6. 无 Accession、Annotation 数据的可行性

当前结构已经证明以下关系在数据库层面不是强制的：

- `Dataset.project` 可空；
- `Dataset.species` 可空；
- Dataset 与 Accession 通过可选中间表关联；
- `DataFile.dataset` 可空；
- DataFile 可通过显式访问级别独立存在。

因此，没有 Accession 或 Annotation 的数据在物理上能够保存，但当前缺少统一 DataAsset 身份、通用类型/Profile、稳定 Project 归属和一致的权限入口。

目标方案应要求普通正式数据使用：

```text
Project -> DataAsset -> AssetFileMembership -> DataFile
```

Species、Accession、Sample、Assembly 和 Annotation 均为可选上下文或专业扩展，不得成为通用入库前提。

## 7. Dataset 语义迁移建议

| 当前语义 | 目标归属 | 说明 |
| --- | --- | --- |
| dataset_code / name | DataAsset | 统一科研数据身份 |
| dataset_type | DataAsset data type + profile | 受控注册表，不固化为不断扩张的 choices |
| project | DataAsset.project | 目标业务必填；历史空值需映射 |
| version | DataAsset.version | 发布与不可变策略由子 ADR 定义 |
| visibility / status | DataAsset + 授权/发布服务 | 必须保持或收紧现有行为 |
| description | DataAsset | 通用描述 |
| bioproject_accession | 外部标识或专业上下文 | 不应成为所有课题组必填字段 |
| species | 可选领域关联或 metadata | 不进入通用必填核心 |
| DatasetAccession | 显式 DataAsset 上下文关系 | 具体表和角色由子 ADR 决定 |
| DataFile.dataset | AssetFileMembership | 真实外键显式中间表 |
| FileRelation(dataset) | 迁移并退役该语义 | 不扩展为 DataAsset 正式关系 |
| Dataset Manifest | DataAsset Manifest 或独立 Collection/Release | 需生产语义和消费者审计后决定 |

## 8. 生产只读审计 Gate

在编写回填或切换 migration 前，必须在获得生产只读授权后输出以下指标和明细：

1. Dataset 总数，按 status、visibility、dataset_type 分组；
2. project/species/bioproject_accession 为空的 Dataset 数量；
3. DatasetAccession 数量、无 Accession 或多 Accession 的 Dataset；
4. `DataFile.dataset` 为空和非空数量；
5. `FileRelation.related_type="dataset"` 数量及无效 related_id；
6. 两条 Dataset 文件关系一致、缺失、冲突和一文件多 Dataset 的明细；
7. Dataset code、BioProject、Project 和版本组合的重复或歧义；
8. Dataset 作为 Collection、Release 或 Manifest 发布单元的真实案例；
9. Dataset API 和 Manifest 的真实调用方、调用量和兼容窗口；
10. 每条待迁移记录的 DataAsset 映射结果、人工处理原因和权限对比结果。

生产审计只读执行，不修改数据；输出必须脱敏且不得包含服务器原始路径、token 或受保护数据。

## 9. 实施 Gate 与状态

| Gate | 状态 | 说明 |
| --- | --- | --- |
| 仓库代码调用面审计 | 已完成 | 当前报告 |
| DataAsset 稳定架构 ADR | 已完成 | `docs/adr/ADR-001-dataasset-unified-identity.md` |
| 通用科研数据仓库总体设计 | 已完成 | `docs/architecture/GeneData_通用科研数据仓库总体设计.md` |
| Dataset T0 生产只读审计 | 已完成，证据在仓库外受控保存 | 用户提供的报告显示 289 个 Dataset、4500 个 DataFile，文件均无 Dataset 归属；该结果不是仓库内置数据快照 |
| DataFile T1 归属审计 | 已完成，证据在仓库外受控保存 | 4500 个文件中 390 个唯一类型候选、397 个需语义规则、3713 个无 Dataset 候选；无无效关系 |
| 最小 DataAsset schema/constraint ADR | 已批准 | `docs/adr/ADR-002-dataasset-minimum-schema.md` |
| 最小权限与发布边界 | 已批准 | 已并入 ADR-002，必须保持 fail-closed |
| Collection/Release/Manifest 语义决策 | 第一阶段边界已批准 | ADR-002 暂不增加 Collection/Release 表，Manifest 为生成视图 |
| DataAsset T3 新增结构 | 开发完成，生产未部署 | 三个模型、migration `0026`、注册表及最小 service 已通过 470 项 `files` 测试；未执行生产 migration |
| Dataset -> DataAsset 映射 dry-run 工具 | 未开始 | T4 单独实施，不执行回填 |
| API/frontend 实施 | 未开始 | T3 明确排除，必须后续单独批准 |

## 10. 建议的下一实施任务

T0、T1 报告已经核对，生产审计只生成了脱敏 TSV，没有执行回填或生产变更。ADR-002 已批准最小
schema、权限、发布和 Manifest 边界；T3 新增结构已完成开发验证，但 migration `0026` 尚未在生产执行，
没有 DataAsset 生产记录。下一任务是 T4 只读 dry-run 映射和回填准备，不直接回填或切换。

T1 候选匹配结果不能直接升级为迁移事实。尤其不能把 annotation 文件自动挂到 WGS 资产，也不能只按
Accession 合并 raw reads 或 transcriptome。
