---
title: GeneData 通用科研数据仓库总体设计
status: active
owner: 徐杨珂
last_reviewed: 2026-11-19
supersedes: GeneData DataAsset 通用科研数据仓库整体设计方案 v0.2
---

# GeneData 通用科研数据仓库总体设计

## 1. 文档定位

本文是 GeneData 数据仓库的 active 总体设计，负责说明稳定目标、对象边界、扩展方式、迁移顺序和实施门禁。

本文不表示目标 model、migration、API、权限、前端或生产数据迁移已经完成。当前实现以代码、migration、测试和 CI 为准；具体表字段、约束和接口必须由后续子 ADR 与分阶段任务批准。

相关依据：

- `AGENTS.md`：仓库级开发与安全边界；
- `docs/adr/ADR-001-dataasset-unified-identity.md`：DataAsset 唯一身份决策；
- `docs/adr/ADR-002-dataasset-minimum-schema.md`：T3 最小模型、文件成员与发布边界；
- `docs/architecture/GeneData_DataAsset_T3新增结构实施方案.md`：已完成的 T3 开发范围与生产边界；
- `docs/audits/GeneData_Dataset到DataAsset实施前审计_20261118.md`：当前 Dataset 调用面证据；
- `docs/ACTIVE_DOCUMENTS.md`：活动文档索引。

本文同时吸收 2026-11-18 至 2026-11-19 的 T0、T1、T4 生产只读审计结论和生产文件清单核对结果。
审计 TSV 与生产文件清单保存在仓库外，不纳入 Git；本文只记录经人工核对后的统计结论和设计影响，
不把生产数据导出作为仓库内事实来源。

## 2. 建设目标

GeneData 面向跨物种、跨组学、跨课题组的长期科研数据管理，不围绕单一生物学层级或文件格式建立核心模型。

目标能力：

1. 基因组、注释、测序、变异、表达矩阵、显微图像、普通表格和其他科研数据使用同一资产身份；
2. 新增普通数据类型时主要增加配置，不修改核心身份模型和通用 API；
3. 统一管理文件、checksum、版本、权限、发布状态和审计信息；
4. 保存分析输入、输出、软件/流程版本、参数、执行状态和日志；
5. 支持从结果追溯输入、参考数据和分析过程；
6. 没有 Species、Accession、Assembly 或 Annotation 的课题组仍能完整使用仓库；
7. Dataset 最终退役，不形成两套科研数据身份。

非目标：

- 第一阶段不建设完整工作流调度平台；
- 第一阶段不建设复杂网页 Schema 编辑器；
- 不复制 openBIS 的完整层级和存储体系；
- 不把所有专业字段塞入无约束 JSON；
- 不在一个任务中同时完成 model、migration、API、Vue 和生产切换。

## 3. 当前状态与目标状态

### 3.1 当前已验证状态

- 当前存在 `Project`、`Dataset`、`DatasetAccession`、`DataFile`、`FileRelation`、`Assembly`、`Annotation` 等模型；
- 当前已存在 `DataAsset`、`AssetFileMembership`、`DataAssetAccession` 及 migration `0026`，但尚未部署生产，也没有生产 DataAsset 记录；
- `DataFile` 是当前正式物理文件实体；
- `Dataset` 同时承担身份、类型、版本、发布、可见性、文件分组、Accession 和 Manifest 语义；
- Dataset 文件关系同时存在 `DataFile.dataset` 外键和 `FileRelation(dataset)` 两条路径；
- 当前代码调用面审计和 T0、T1 生产只读审计已完成；T4 dry-run 已在生产独立临时目录只读运行并导出
  脱敏报告，未执行 migration、回填或线上服务切换；
- 部分 Dataset API 已进入 OpenAPI、测试和前端契约。

### 3.2 目标结构

```text
Project
  └── DataAsset                         科研数据统一身份
        ├── AssetFileMembership ── DataFile
        ├── 可选研究对象关联 ───── Species / Accession / Sample
        ├── 可选领域扩展 ───────── Assembly / Annotation / ...
        ├── 语义关系 ───────────── 其他 DataAsset
        └── AnalysisRun 输入或输出

AnalysisRun
  ├── 输入 DataAsset / DataFile 快照
  └── 输出 DataAsset / DataFile 快照
```

四个维度必须分开：

| 维度 | 回答的问题 | 目标事实来源 |
| --- | --- | --- |
| 资产类型 | 这是什么数据 | `DataAsset.data_type_key + profile_key` |
| 专业上下文 | 这份数据描述谁、来自谁或针对谁 | 显式上下文关系与专业实体 |
| 文件组成 | 哪些真实文件共同构成该资产 | `AssetFileMembership` |
| 产生过程 | 数据如何由输入产生 | `AnalysisRun` 输入/输出关系 |

不得用文件扩展名代替数据类型，不得用 `RNA-Seq`、`Hi-C`、`WGS` 等实验策略代替
DataType/Profile，也不得把 Accession、Assembly 或 Annotation 字段复制进 metadata 形成第二份事实来源。

唯一事实来源：

| 概念 | 目标事实来源 |
| --- | --- |
| 科研数据 code、名称、类型、版本、状态、可见性 | DataAsset |
| 物理路径、大小、格式、checksum、内容版本 | DataFile |
| 项目归属和默认权限入口 | Project 与授权服务 |
| 文件在资产中的角色、顺序和 primary | AssetFileMembership |
| 软件、参数、执行状态、输入输出 | AnalysisRun 及显式参与关系 |
| Assembly、Annotation 等专业字段 | 对应领域扩展实体 |
| 人工或导入的科研语义关系 | AssetRelation，带证据类型 |

### 3.3 当前生产数据画像

生产只读审计和文件清单当前显示：

| 对象或文件 | 已核对数量 | 设计含义 |
| --- | ---: | --- |
| 现有 Dataset | 289 | 130 genome、130 transcriptome、29 hic；均不能直接假定为 289 个真实资产 |
| DataFile 记录 | 4500 | 当前均未形成可直接迁移的 Dataset 文件成员关系 |
| Dataset 唯一文件候选 | 390 | 只表示规则匹配候选，不等于已批准归属 |
| 生产文件清单条目 | 2852 | 与 4500 条 DataFile 记录必须进一步核对存在性、重复与历史记录 |
| FASTA / FAI | 607 / 607 | 应从 Assembly 与真实文件出发识别 reference genome 候选 |
| GFF | 517 | 应作为独立 annotation 资产候选，不作为 genome 资产的普通附属文件 |
| BED | 760 | 需按内容与角色识别 genomic region set 或辅助索引/展示文件 |
| tar.gz | 358 | 归档格式不是数据类型；其中 transcriptome 96、TE 151、codon 111 需检查包内内容 |
| 明确 FASTQ/FQ/BAM/CRAM/Hi-C/cool/mcool 文件 | 0 | 当前不能为 130 transcriptome 和 29 hic 元数据壳创建正式资产 |

T1 文件角色还表明当前真实数据至少包括：参考基因组、基因组注释、JBrowse 派生文件、
非编码 RNA 区域、着丝粒、转座元件、core blocks、密码子结果、少量 raw-read 角色及
transcriptome 归档。角色名称是迁移线索，不自动等于目标 Profile。

### 3.4 159 条 metadata-only Dataset 的处理决策

130 条 transcriptome 和 29 条 Hi-C Dataset 当前没有可确认的本地核心文件，只保存了描述、
Accession 或 ENA/SRA 外部映射。它们是外部数据可用性和实验描述，不是本地科研数据资产。

迁移时必须输出：

```text
mapping_status = excluded_not_asset
reason = metadata_only_external_reference
```

处理规则：

1. 不为这 159 条记录新建空壳 DataAsset；
2. 不为它们专门增加 transcriptome 或 hic Profile；
3. 外部 study、sample、experiment、run、library strategy、下载地址和 MD5 继续由
   `AccessionExternalMapping` 承载；
4. Dataset 的名称和 description 在退役前保留为迁移证据，必要的信息应归并到专业实体或外部映射，
   不复制到无文件 DataAsset；
5. 将来真实 FASTQ、矩阵或组装结果下载并校验后，再根据实际 payload 创建对应 DataAsset，记录来源和
   外部 run 标识。

`library_strategy` 是 ENA/SRA 的实验策略术语，例如 RNA-Seq、Hi-C、WGS；它属于外部来源或
`assay_type` metadata，不是 `data_type_key + profile_key` 的替代品。

## 4. 核心对象边界

### 4.1 Project

- 组织 DataAsset 和 AnalysisRun；
- 提供默认权限边界；
- 普通正式 DataAsset 目标上必须归属一个 Project；
- 公共参考数据使用明确的公共参考 Project，不以空值表示共享；
- 历史回填期可暂时允许空值，但正式创建服务从第一版就必须要求 Project。

### 4.2 DataAsset

DataAsset 是唯一科研数据身份，最终取代 Dataset。

必须表达的概念包括：

- 唯一、不可变的 asset code；
- 名称和 Project；
- data type、profile 与 schema version；
- 版本、状态和可见性；
- 受 Schema 校验的 metadata；
- 创建者、创建时间和发布时间。

DataAsset 不保存：

- 物理路径、文件大小和 checksum；
- Assembly、Annotation 等专业字段；
- AnalysisRun 的软件、参数和日志；
- 项目成员授权规则本身。

正式 DataAsset 不是描述卡片或外部链接容器。目标创建与发布不变量是：

1. 至少包含一个 `DataFile`；
2. 每个文件角色满足 Profile 声明的 core/auxiliary 分类和逐角色 `min/max`；
3. 至少一个 core 角色的 `min` 大于或等于 1，且实际成员满足该要求；
4. Project、状态和权限完整；
5. metadata、文件规则和 context 通过固定 schema version/digest 契约校验；
6. 发布前核心文件存在且 checksum 已验证。

当前 canonical creation service 已拒绝无核心文件或不满足 context 规则的正式创建，并复用 Registry v2
唯一契约校验入口；直接 ORM 仍可用于 migration、测试或事务内暂态对象，但不是受支持的业务写入路径。
发布前的物理存在性、checksum 和文件发布状态校验仍属于后续发布 service，不能从创建校验推断为已完成。

当前最小字段、状态机、索引和数据库约束以 ADR-002 与 migration `0026` 为准；后续扩展必须通过
独立 ADR 或批准任务，不得在实现中顺带扩大。

T2 已批准决策见 `docs/adr/ADR-002-dataasset-minimum-schema.md`。T3 已完成 model、migration 和最小 service
的开发验证，但不表示 migration 已部署生产，也不表示 API、前端、回填或生产切换已经完成。

### 4.3 DataFile

继续复用 DataFile 作为唯一物理文件实体：

- 一个 DataFile 对应一个具体文件内容；
- 内容改变时创建新 DataFile，不覆盖历史 checksum；
- 原始 `file_path` 不返回普通前端和外部客户端；
- 下载、Range、预览和外部工具访问均重新授权；
- 历史执行记录冻结 DataFile、checksum、内容版本和文件大小快照。

不得创建 AssetFile、FileObject 或其他平行物理文件模型。

### 4.4 AssetFileMembership

DataAsset 与 DataFile 使用显式真实外键成员关系，不使用 `FileRelation(related_type="data_asset")`。

成员关系至少需要：

- DataAsset 外键；
- DataFile 外键；
- 受控 file role；
- 非负顺序；
- primary 标记；
- 必要的描述和生命周期信息。

必须通过数据库约束阻止重复、悬空关系和非法顺序。当前 T3 已使用 `primary_slot` 在 MySQL 中落实
“同资产、同角色最多一个 primary”等 ADR-002 约束。

成员关系表达资产组成，不表达血缘。文件按生命周期分为：

| 类别 | 例子 | 管理方式 |
| --- | --- | --- |
| 核心 payload | FASTA、FASTQ、GFF、表达矩阵、contact matrix、主结果表、原始图像 | 作为 primary/core role；决定资产能否成立 |
| 配套成员 | FAI、GZI、Tabix、README、metadata、thumbnail、服务端展示派生物 | 作为 auxiliary/support role；不能单独使资产成立 |
| 独立科研结果 | 可独立版本化、引用、授权或复用的分析结果 | 建立独立 DataAsset，并通过 AnalysisRun 关联 |

判断原则：具有独立发布、版本、权限或复用价值的数据建立独立 DataAsset；与主体同生命周期且可重建的文件
作为成员文件。文件是否位于同一压缩包、目录或扩展名相同，不能决定资产边界。

### 4.5 专业实体和研究对象

Species、Accession、Sample、Assembly 和 Annotation 均为可选上下文或领域扩展，不是 DataAsset 的必填上级。

- Assembly 保存组装方法、测序技术、N50、contig 等专业字段；
- Annotation 保存注释数据库、版本、Assembly 关系等专业字段；
- Accession/Sample 保存材料和外部登录信息；
- DataAsset 保存这些对象共同需要的通用身份、状态和可见性。

高频稳定关系使用真实外键或显式中间表，不新增 GenericForeignKey 或字符串多态核心关系。

目标上下文采用少量固定显式关系，不按每个科研数据类型增表：

- `DataAssetAccession`：关联材料或外部登录上下文，当前已实现；
- `DataAssetSample`：关联一个或多个实验样本，开发已实现，生产未部署；
- `DataAssetAssembly`：关联准确组装，开发已实现，生产未部署；
- `DataAssetAnnotation`：关联准确注释版本，开发已实现，生产未部署。

API 可以把这些关系组合成统一 `contexts` 视图，但数据库仍使用真实外键和显式中间表。禁止新增
`context_type + context_id` 或 `GenericForeignKey` 通用多态关系。

上下文只关联最精确对象，其他层级通过专业实体关系推导：

- reference genome 关联 Assembly，再由 Assembly 推导 Accession；
- genome annotation 关联 Annotation，再由 Annotation 推导 Assembly 和 Accession；
- raw read set 通常关联一个或多个 Sample，必要时附带 Accession；
- expression matrix 通常关联多个 Sample；
- 普通表格和图像可仅归属 Project，也可按 Profile 关联 Sample、Assembly 或 Annotation。

这样所有 DataAsset 共享同一通用身份和检索入口，但 annotation、assembly、table、matrix、image
不会混成一个 metadata JSON：它们由 `data_type/profile`、显式 context、file role 三个维度共同区分。

### 4.6 AnalysisRun 与血缘

真实派生以 AnalysisRun 为事实来源：

```text
输入 DataAsset/DataFile -> AnalysisRun -> 输出 DataAsset/DataFile
```

最低不变量：

- 明确 input/output、role 和必要顺序；
- 保存 workflow/software/container 版本；
- 保存参数快照和摘要；
- 保存 PENDING/RUNNING/SUCCESS/FAILED/CANCELLED 等状态；
- 保存开始、结束、日志和错误；
- 保存执行时 DataFile checksum/content version 快照；
- 历史 Run 不因资产后续换文件而变化；
- 所有上下游节点逐节点授权。

第一阶段采用一张还是两张参与关系表，由 AnalysisRun 子 ADR 决定。

### 4.7 AssetRelation

AssetRelation 只表达 `annotates`、`uses_reference`、`part_of`、`version_of`、`supersedes` 等科研语义或历史推断。

- 真实派生优先由 AnalysisRun 计算；
- 人工、导入或推断关系必须保存 evidence type；
- 方向语义由受控 relation type 定义；
- 不允许形成第二份可任意编辑的派生事实。

四类关系不得混用：

| 关系 | 用途 | 不承担的语义 |
| --- | --- | --- |
| AssetFileMembership | 文件是资产的一部分 | 产生过程、版本替代 |
| Asset context | 资产针对哪个 Sample/Assembly/Annotation/Accession | 文件组成、派生过程 |
| AssetRelation | 版本、补充、参考、语义关联 | 真实分析执行 |
| AnalysisRun input/output | 输入如何产生输出 | 人工主题标签或业务归属 |

## 5. 数据分类、管理与上下文判别

借鉴 openBIS 的类型、属性定义和语义注释方法，但不复制其完整 Space/Collection/Object 层级。

目标配置层包括：

- DataType：数据大类；
- Profile：同一大类下的用途或结构；
- PropertyDefinition：字段类型、单位、词表和校验；
- Schema version/digest：冻结正式数据使用的规则版本；
- Semantic annotation：字段与外部标准含义的映射。

### 5.1 统一判别框架

每个 DataAsset 用四个彼此独立的维度描述，不能把所有信息堆进 `data_type` 或 metadata：

```text
一个科研数据资产
  = DataType/Profile       这是什么结构和用途的数据
  + Context                它描述、来源于或针对哪个科研对象
  + File Membership        哪些核心和辅助文件组成它
  + AnalysisRun            它由什么输入和过程产生
```

因此，所有 DataAsset 共享统一身份、权限、版本、文件入口和检索方式，但并不意味着所有上下文混在一起。

- 查询/API 层可以统一返回 `contexts`；
- 数据库层分别保存 `DataAssetAccession`、`DataAssetSample`、`DataAssetAssembly`、
  `DataAssetAnnotation` 等显式真实外键关系；
- Profile 声明允许或要求的 context 类型和基数；
- 不使用一个万能 context 表、`context_type + context_id`、GenericForeignKey 或任意 JSON 来伪造统一性。

### 5.2 当前数据应如何分类和管理

结合 T0、T1、T4 和生产文件清单，当前数据应按真实 payload 管理：

| 当前数据 | 资产分类 | 核心文件 | 辅助文件 | 最精确上下文 | 当前处理 |
| --- | --- | --- | --- | --- | --- |
| 参考基因组 | `sequence/reference_genome` | FASTA | FAI、GZI、refname aliases、JBrowse 配置 | Assembly | 建立独立 DataAsset 候选 |
| 基因组注释 | `feature/genome_annotation` | GFF/GTF | Tabix、展示索引、JBrowse 派生文件 | Annotation | 与参考基因组分成独立资产 |
| tRNA/rRNA/miRNA/centromere/TE/core blocks 等区域集 | `feature/genomic_region_set` | 具有科研语义的 BED/主结果 | 索引、README、展示派生文件 | Annotation 或 Assembly，按来源确定 | 按语义和生命周期分组，不能把所有 BED 合成一个资产 |
| 原始测序 reads | `sequence/raw_read_set` | FASTQ/FQ | manifest、校验文件、质控摘要 | Sample；Accession 可选 | 只有本地核心文件存在并校验后才建资产 |
| transcript assembly | `sequence/transcript_assembly` | transcript FASTA | 索引、说明文件 | Sample/Assembly，按生成语义确定 | 先检查 96 个 transcriptome 归档内容 |
| 表达结果 | `matrix/expression_matrix` | 表达矩阵 | 样本映射、列定义、质控报告 | 多个 Sample | 与 RNA-Seq 原始 reads 分开管理 |
| Hi-C 结果 | `matrix/contact_matrix` | contact matrix | index、normalization、QC | Sample/Assembly | 与 Hi-C 原始 reads 分开管理 |
| codon 结果 | `table/codon_usage_result` | 主结果表 | 日志、参数、README | Assembly/Annotation，可选 | 先检查 111 个归档的主结果和边界 |
| 普通科研表格 | `table/research_table` 或更明确 Profile | CSV/TSV/Parquet | schema、README | 可无专业 context，仅 Project | 使用通用表格能力，不新增业务表 |
| 显微及科研图像 | `image/microscopy_image_set` / `image/research_image_set` | 原始或标准化图像 | thumbnail、预览、采集说明 | Sample 可选 | 使用通用图像 Profile，不新增图像资产表 |
| 159 条 transcriptome/Hi-C 描述 | 非资产 | 无 | 无 | AccessionExternalMapping | 标记 `excluded_not_asset`，不创建空壳 DataAsset |

归档文件只是一种包装方式。`tar.gz` 中可能是序列、矩阵、表格或多个结果，必须检查包内主文件、
生成过程和生命周期后再决定资产分类，不能建立 `archive` DataType 来回避语义判断。

### 5.3 固定少量核心实体

科研类型增加时不增加核心业务表。长期稳定结构为：

| 稳定实体 | 职责 | 是否随科研类型增加 |
| --- | --- | --- |
| Project | 项目与默认权限边界 | 否 |
| DataAsset | 所有科研数据的统一身份 | 否 |
| DataFile | 唯一物理文件事实 | 否 |
| AssetFileMembership | 资产的核心/辅助文件组成 | 否 |
| AnalysisRun | 输入、处理过程和输出血缘 | 否；目标实体，尚未实现 |
| 专业实体 | Sample、Accession、Assembly、Annotation 等稳定科研对象 | 仅在出现真正独立且长期稳定的专业事实时评审，不按文件类型增加 |
| Profile/词表 | 类型规则、文件角色、context 规则和 metadata schema | 可由注册表扩展，不增加资产表 |

关系必须各司其职：

```text
Project
  └── DataAsset ── AssetFileMembership ── DataFile
        ├── DataAssetAssembly ───────────── Assembly
        ├── DataAssetAnnotation ─────────── Annotation
        ├── DataAssetSample ─────────────── Sample
        ├── DataAssetAccession ──────────── Accession
        └── AnalysisRun input/output ────── 其他 DataAsset/DataFile
```

增加新科研类型通常只需要：增加或调整 Profile、受控词表、文件角色及通用显示配置。只有出现新的、
不能由现有实体表达且具有独立生命周期、强约束和高复用价值的专业事实，才评审是否增加专业实体；
不能因为出现一种新文件格式、新实验技术或新课题组就增加表。

### 5.4 如何区分 annotation、assembly、table 和 image

区分不依赖单个字段，而由 Profile、最精确 context 和核心文件角色共同决定：

| 资产 | DataType/Profile | 必要或典型 context | 核心文件角色 | 可推导关系 |
| --- | --- | --- | --- | --- |
| 参考基因组 | `sequence/reference_genome` | 恰好一个 Assembly | `genome_fasta` | Assembly → Accession |
| 基因组注释 | `feature/genome_annotation` | 恰好一个 Annotation | `annotation_gff` | Annotation → Assembly → Accession |
| 普通表格 | `table/research_table` | 可为空，也可关联 Sample/Assembly/Annotation | `primary_table` | 只推导已明确关联的专业对象 |
| 表达矩阵 | `matrix/expression_matrix` | 一个或多个 Sample | `expression_matrix` | Sample → Accession（如现有专业关系支持） |
| 显微图像 | `image/microscopy_image_set` | 零个或多个 Sample | `primary_image` | Sample → Accession（如适用） |
| 普通科研图像 | `image/research_image_set` | context 可选 | `primary_image` | 不强行绑定生物学层级 |

例如，一份 GFF 不因为与某个 FASTA 位于同一目录就成为 reference genome 的辅助文件。它具有独立版本、
发布和复用价值，应成为 `feature/genome_annotation` DataAsset，并关联准确的 Annotation；FASTA 则是
`sequence/reference_genome` DataAsset 的核心文件，并关联准确的 Assembly。二者可通过专业实体链路或未来
AssetRelation/AnalysisRun 表达关系，而不是合并成一个无法区分的“大资产”。

普通表格和图像也不需要伪造 Annotation 或 Assembly 上下文。它们可以只归属 Project；确实针对某个
Sample、Assembly 或 Annotation 时才建立对应显式关系。这样没有 Accession、Annotation 的其他课题组
仍能正常使用仓库，同时专业数据仍保持精确语义。

### 5.5 少量稳定 DataType

DataType 表示 payload 的结构大类，必须保持少而稳定。Profile 表示同一结构下的用途、核心文件角色、
上下文规则和 metadata schema。建议起始分类如下：

| DataType | Profile 示例 | 典型核心 payload |
| --- | --- | --- |
| `sequence` | `reference_genome` | FASTA |
| `sequence` | `raw_read_set` | FASTQ/FQ |
| `sequence` | `transcript_assembly` | transcript FASTA |
| `feature` | `genome_annotation` | GFF/GTF |
| `feature` | `genomic_region_set` | BED/VCF-like feature set |
| `feature` | `variant_set` | VCF/BCF |
| `table` | `research_table` | CSV/TSV/Parquet |
| `table` | `codon_usage_result` | 主结果表 |
| `table` | `qc_report` | 结构化质量报告 |
| `matrix` | `expression_matrix` | 表达矩阵 |
| `matrix` | `contact_matrix` | cool/mcool/hic 或标准矩阵 |
| `matrix` | `genotype_matrix` | 基因型矩阵 |
| `image` | `microscopy_image_set` | 原始或标准化图像 |
| `image` | `research_image_set` | 普通科研图像集合 |

该表是目标初始词汇，不是要求一次性全部注册。新增 Profile 前必须有真实 payload、明确复用场景和
可验证规则；不得只为迁移某批历史 description 创建 Profile。

`RNA-Seq`、`Hi-C`、`WGS` 属于 assay/library strategy。相同 assay 可以产生不同结构的资产：

- Hi-C 原始 reads：`sequence/raw_read_set`；
- Hi-C contact matrix：`matrix/contact_matrix`；
- RNA-Seq 原始 reads：`sequence/raw_read_set`；
- RNA-Seq 表达结果：`matrix/expression_matrix`；
- transcript assembly：`sequence/transcript_assembly`。

### 5.6 Profile 最小契约

每个 Profile 至少声明：

```yaml
data_type_key: sequence
profile_key: reference_genome
schema_version: 1
file_role_rules:
  genome_fasta: {class: core, min: 1, max: 1}
  fasta_index: {class: auxiliary, min: 0, max: 1}
context_rules:
  assembly: {min: 1, max: 1}
metadata_schema: {...}
```

含义：

- `file_role_rules`：以角色为 key，统一声明 core/auxiliary 和逐角色 `min/max`；
- `context_rules`：允许或要求的上下文类型和基数；
- `metadata_schema`：仅保存该 Profile 特有且不属于专业实体事实的扩展字段。

成员关系的 `is_primary` 只表示同一角色中的代表文件，不决定文件是否为核心载荷。角色的 core/auxiliary
性质和数量要求只由 `file_role_rules` 决定，从而能够配置成对 reads、多 lane 文件、多个核心图像和可选索引。

参考规则：

| Profile | 最精确上下文规则 |
| --- | --- |
| `sequence/reference_genome` | 恰好一个 Assembly |
| `feature/genome_annotation` | 恰好一个 Annotation |
| `sequence/raw_read_set` | 一个或多个 Sample；Accession 可选 |
| `matrix/expression_matrix` | 一个或多个 Sample |
| `table/research_table` | context 可选 |
| `image/microscopy_image_set` | 零个或多个 Sample |

### 5.7 Metadata 边界

metadata 适合保存 Profile 专有、低频、可版本化的扩展属性，例如 assay type、测序布局、表格列定义、
图像采集参数。以下内容不得复制进 metadata：

- Project、权限、状态、版本等 DataAsset 核心字段；
- 路径、大小、checksum 等 DataFile 事实；
- Accession、Sample、Assembly、Annotation 的稳定标识和专业字段；
- AnalysisRun 的软件、参数、日志和执行状态。

Schema 默认禁止未声明字段。需要高频过滤、唯一性或数据库强约束的字段，应进入经批准的核心列或专业实体，
而不是继续扩大 JSON。

### 5.8 注册表治理与管理员

第一阶段原则：

- 注册表使用版本控制的 YAML/JSON；
- 启动或 CI 校验 code 唯一性、引用完整性和 Schema 合法性；
- 正式 DataAsset 保存 schema version/digest；
- metadata 只能保存 Schema 允许的扩展字段；
- 高频过滤和强约束字段保留为数据库列；
- 暂不建设网页编辑器和复杂注册表数据库。

新增普通数据类型应通过注册表扩展，而不是修改核心 Model choices、增加专用 API 路由或复制前端页面。

目标上借鉴 openBIS 的“固定实体类型 + 动态 master data”治理方式：授权的普通用户可获得
`Registry Steward` 业务权限，用于创建、评审、启用和弃用 Profile、PropertyDefinition 与受控词表；
该角色不等于 Django superuser，也不天然获得生产运维或所有数据访问权。

生命周期固定为：

```text
draft -> active -> deprecated -> retired
```

已被 DataAsset 使用的 Profile/schema version 不得物理删除；只能停止新建并保留历史解析。只有从未使用的
draft 可以硬删除。普通新增和弃用不应要求修改后端核心模型，但新增专用查看器、解析器或处理器仍可能需要代码。

当前实现仍是版本控制的静态 `registry.json`，增加条目需要代码评审和部署；运行时 Registry Steward
管理属于后续目标，不能描述成现有能力。

## 6. 入库、权限和版本

### 6.1 通用入库

目标最小流程：

```text
选择 Project
  -> 选择 DataType/Profile
  -> 校验 metadata 与 schema version
  -> 登记 DataFile 和 checksum
  -> 校验文件角色的 core/auxiliary 与逐角色 min/max
  -> 关联最精确的 Sample/Assembly/Annotation/Accession 上下文
  -> 在同一事务中创建 DataAsset 和文件成员关系
  -> 输出审计结果
```

当前 `import_data_batch`、现有 manifest importer 和文件写入服务应作为迁移调查对象；不得复制一套 DataAsset 专用写入逻辑。DataAsset 写入必须最终收敛到唯一 service，并支持 dry-run、有限批次、幂等、审计和失败重试。

外部元数据发现和本地资产入库是两个流程：发现 ENA/SRA 记录时只更新专业实体或
`AccessionExternalMapping`；只有核心文件实际进入受控存储并完成校验，才创建 DataAsset。

### 6.2 权限

- 默认 private，无法解析继承策略时 fail closed；
- Project 提供默认边界，DataAsset 表达资产级状态与可见性；
- DataFile 可有更严格策略，不得通过父对象放宽；
- 搜索、详情、Manifest、下载和血缘逐节点授权；
- 不得泄露私有对象的存在性、名称、路径和 checksum；
- 完整成员、共享和公开发布规则由权限子 ADR 决定。

### 6.3 版本与不可变性

- DataAsset 发布后的可变字段范围必须受控；
- 重大科研内容变化创建新版本或新资产；
- DataFile 内容变化创建新 DataFile；
- 历史 Run 始终引用原文件快照；
- `version_of`、`supersedes` 与发布状态不得代替真实运行血缘。

## 7. API、前端和外部工具边界

目标 API 围绕 Project、DataAsset、DataFile、AnalysisRun 和受控注册表组织，但具体 URL 尚未批准。

- 当前 Dataset API 在切换前仍是活动契约；
- 新 canonical API 必须先具备授权、过滤、分页、错误契约和测试；
- 旧 `/datasets/` 路径只能作为有明确版本、调用方、期限和删除门槛的迁移适配层；
- 适配层不得保存数据或形成旧写入链路；
- Vue 根据 Profile/Schema 渲染通用字段，专业页面只呈现专业扩展；
- 外部工具使用 ID、授权内容接口和 Manifest，不接收服务器路径；
- 当前未实现通用批次选择解析和不可变批次模型，不得把候选方案描述成现有能力。

## 8. Dataset 迁移与退役

### 8.1 语义映射

| 当前 Dataset 语义 | 目标归属 |
| --- | --- |
| code / name / version / description | DataAsset |
| dataset_type | DataType + Profile |
| project | DataAsset.project |
| visibility / status | DataAsset + 授权/发布服务 |
| species / BioProject | 可选上下文、外部标识或 metadata |
| DatasetAccession | 显式 DataAsset 上下文关系 |
| DataFile.dataset | AssetFileMembership |
| FileRelation(dataset) | 核对后迁移并退役该语义 |
| Dataset Manifest | DataAsset Manifest 或独立 Collection/Release 决策 |

迁移不是 `289 Dataset -> 289 DataAsset`。候选识别必须从“专业实体 + 真实 DataFile + 已核对文件关系”出发：

| 当前证据 | 目标候选 | 处理要求 |
| --- | --- | --- |
| Assembly + FASTA + FAI | `sequence/reference_genome` | FASTA 为核心，FAI 为辅助；以 Assembly 为上下文 |
| Annotation + GFF/GTF + 索引 | `feature/genome_annotation` | 独立于 genome 资产；以 Annotation 为上下文 |
| 有明确科研语义的 BED 集 | `feature/genomic_region_set` | 按内容与用途分组，不能仅按扩展名合并 |
| 真实 FASTQ 集 | `sequence/raw_read_set` | 按 Sample、library/run 和配对关系分组 |
| 表达矩阵 | `matrix/expression_matrix` | 关联多个 Sample，并保留列/样本映射 |
| Hi-C matrix | `matrix/contact_matrix` | 不与 Hi-C 原始 reads 合并为一个资产 |
| codon 主结果表 | `table/codon_usage_result` | 先检查归档内容和独立版本价值 |
| transcriptome 归档 | 待内容审计 | 可能是 raw reads、transcript assembly、matrix 或普通结果，不能按 tar.gz 分类 |
| metadata-only Dataset | 非资产 | 标记 `excluded_not_asset`，保留外部映射 |

607 个 FASTA、517 个 GFF 和 760 个 BED 说明真实资产数量不能由 130 个 legacy genome Dataset 决定；
同一 Accession 下的 genome、annotation、region set、raw reads 和 matrix 必须是可区分、可独立版本化的资产。

### 8.2 T4 dry-run 的目标输出

当前 T4 工具已在开发环境重构为只读候选审计，不写数据库，也不再以 Dataset 壳作为候选驱动。它输出：

1. `assets`：由已批准 Profile 覆盖的专业实体和显式文件关系生成的资产候选；
2. `memberships`：核心/辅助文件角色、顺序和 primary；
3. `contexts`：Accession、Sample、Assembly、Annotation 显式关联；
4. `exclusions`：159 条 metadata-only 等不应创建资产的记录和原因；
5. `conflicts`：多上下文、归属歧义、未批准 Profile、缺失物理文件和角色冲突；
6. `permissions`：迁移前后权限对比，任何放宽均阻断；
7. `checksums`：文件存在性、checksum 和发布状态核对。

必须额外核对：4500 条 DataFile 与 2852 条物理文件清单的差异、两个多 Accession 上下文冲突、
96 个 transcriptome 归档、111 个 codon 归档、JBrowse 派生文件及 checksum 缺失。无法确定的记录进入人工
复核，不允许回填程序猜测。

### 8.3 固定阶段

1. 仓库调用面审计——已完成；
2. 生产数据只读审计——T0、T1 已完成，证据在仓库外受控保存；
3. 最小 schema、权限和 Collection/Release 边界 ADR——已合并为 ADR-002 并批准；
4. 新增结构和测试，不切换活动读写——T3 开发完成，migration `0026` 尚未部署生产；
5. Dataset -> DataAsset dry-run 映射——T4 生产只读运行已完成；结论表明原映射假设需要按本文修订；
6. 在开发环境调整 Profile 核心文件规则、上下文关系和 T4 候选算法——已完成开发验证；
7. 在生产独立临时目录重新只读 dry-run，并完成人工核对——尚未执行；
8. 分批、幂等回填；
9. 核对记录、关系、权限和 checksum；
10. 一次性切换活动读写；
11. 生产验收和回滚观察期；
12. 删除 Dataset 活动引用和兼容层；
13. 通过新 migration 删除旧表；
14. CI 增加防回流检查。

切换前 Dataset 是活动事实来源；切换后 DataAsset 是活动事实来源。允许受控影子回填和对比，不允许无期限双写。

### 8.4 删除门槛

删除 Dataset 前必须确认：

- 所有 Dataset 均已映射或进入人工处理清单；
- `DataFile.dataset` 和 `FileRelation(dataset)` 已迁移并一致；
- DatasetAccession、权限、Manifest、服务、命令、API 和 Vue 已切换；
- 外部消费者已迁移或受控兼容窗口已结束；
- dry-run、幂等、失败重试和权限对比证据完整；
- 备份、恢复验证、生产验收和回滚审批完成；
- 活动代码引用为 0，CI 防回流生效。

## 9. 下一阶段工作

按以下顺序单独评审和实施：

### 9.1 设计边界确认

以下结论是进入下一次编码前必须明确确认的设计边界；本文不自动批准新增 model、migration 或生产操作：

1. 正式 DataAsset 必须具有 Profile 定义的真实核心 payload；
2. 159 条 metadata-only Dataset 不迁移为 DataAsset；
3. DataType 保持少而稳定，assay/library strategy 与 DataType/Profile 分离；
4. 上下文采用 Accession、Sample、Assembly、Annotation 的显式关系；
5. Annotation GFF 是独立资产候选，不作为 reference genome 的普通成员；
6. 血缘由 AnalysisRun 表达，不扩展 FileRelation。

### 9.2 开发环境调整

按独立提交顺序实施：

1. 新增最小显式上下文关系及数据库约束，不改变现有 Registry 或活动读写；
2. 在一个原子提交中切换 Registry v2、`file_role_rules`、完整 digest、创建 service 和 T4 最小适配；
3. 独立重构 T4 dry-run，使候选由专业实体、真实文件和已核对关系驱动——已完成；
4. 增加 `excluded_not_asset`、context、物理存在性、checksum 和权限报告——已完成；archive inspection
   仍只作为需要人工复核的冲突，不在本阶段解包生产归档；
5. 在开发/脱敏样本上完成幂等、冲突、权限收紧和回滚测试。

本阶段不开发 API/前端，不运行生产 migration，不回填生产数据，不建立 AnalysisRun 或运行时 Registry UI。

### 9.3 生产只读复审与试点

开发验证通过后：

1. 生成干净、POSIX 路径、依赖完整的只读审计包；
2. 在生产独立临时目录复跑 T4，不切换线上 release；
3. 人工核对全部 blocked/review/exclusion、权限变化、物理缺失和 checksum 问题；
4. 先试点一个 reference genome、一个 genome annotation、一个 genomic region set；
5. transcriptome 归档完成包内审计后，再选择一个 raw-read、transcript assembly 或 matrix 试点；
6. 试点验收后才提交分批回填、API/前端切换和 Dataset 退役方案。

每个阶段必须有独立范围、验收、回滚和完成证据，不自动开始下一阶段。

## 10. 通用性验收标准

- 无 Accession/Annotation 的数据能够用 Project + DataAsset + DataFile 完整入库；
- 没有核心文件的 description 或外部链接不会创建空壳 DataAsset；
- 新普通类型不修改核心身份 Model；
- 删除或弃用 Profile 不删除历史解析能力，也不要求删除资产表；
- annotation、assembly、table、matrix、image 能通过 Profile、context 和 file role 明确区分；
- DataFile 始终是唯一物理文件身份；
- Dataset 与 DataAsset 不长期并存为活动事实来源；
- 专业实体不重复保存活动通用身份；
- 分析过程可按输入、运行和输出追溯；
- 文件和血缘节点逐节点授权；
- 发布、回填、迁移和生产验收具有可重复证据；
- 不新增 GenomeFile 依赖、字符串多态核心关系或无期限兼容层。

## 11. 未决事项

以下事项尚未完成或仍需独立决策：

- migration `0026`、`0027` 和 Registry v2 的生产部署与真实数据验收；
- 重构后 T4 的生产只读复审、报告核对和候选边界验收；
- DataAsset 发布 service 的物理文件存在性、checksum 和发布状态校验；
- 96 个 transcriptome 与 111 个 codon 归档的包内真实内容和资产边界；
- 4500 条 DataFile 与 2852 条物理文件清单差异的处置；
- Project 成员、共享和公开发布权限；
- Registry Steward 的授权模型和运行时 master-data 存储时机；
- Collection、Release 和 Manifest 是否在后续阶段独立建模；
- AnalysisRun 与 AssetRelation 的最终表结构；
- 旧 Dataset API 下线日期和生产维护窗口。
