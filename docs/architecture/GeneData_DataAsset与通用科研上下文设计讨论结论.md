---
title: GeneData DataAsset 与通用科研上下文设计讨论结论
status: draft
owner: 徐杨珂
last_reviewed: 2026-11-26
supersedes: null
---

# GeneData DataAsset 与通用科研上下文设计讨论结论

## 1. 文档定位

本文整理从“新库新模型是否可以删除 Accession、Assembly 等专业实体并重新清洗”到“`ContextEntity` 应保存什么、字段是否固定、能否通用”的讨论结论。

本文是 ADR-005 的设计输入，不是实施指令。当前代码中已经存在 `DataAssetAccession`、`DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` 等模型和 migration；在 ADR-005 批准替代方案前，不删除模型、不修改历史 migration，也不把本文提出的 `ContextEntity` 描述成已经实现。

ADR-004 已经确定新仓从空业务库开始，不迁移旧生产环境的科研业务记录和关系。因此可以重新评估旧专业实体是否适合新仓，但“无需迁移旧数据”不等于“可以不经设计直接删除现有代码”。

## 2. 已确定的总体方向

### 2.1 GeneData 的核心定位

GeneData 不是以科研记录或科研对象为中心的 ELN，也不复制 openBIS 或 Kadi4Mat 的完整对象体系。它以可发现、可理解、可授权和可使用的科研文件数据资产为中心，主要回答：

1. 我需要的是什么数据；
2. 数据由哪些文件组成；
3. 数据描述什么对象、来自什么对象；
4. 数据依赖哪些参考数据；
5. 数据能否被下载、分析工具或浏览器使用；
6. 数据如何追溯到输入、处理过程和输出。

openBIS 的 object 思路可以作为“科研上下文”的参考，但不应让科研对象替代 `DataAsset` 成为 GeneData 的主导航和统一数据身份。

### 2.2 稳定的核心边界

- `DataAsset`：可独立发现、授权和使用的一份科研数据资产。
- `DataFile`：物理文件的唯一事实来源。
- `AssetFileMembership`：说明一个 `DataAsset` 由哪些 `DataFile` 组成，以及每个文件在资产中的角色。
- `Project`：权限、治理和组织边界，不属于普通科研上下文。
- Profile：定义某类资产或上下文允许的 metadata、核心文件、辅助文件和关系规则。
- 新数据类型原则上通过配置扩展，不因每个科研类型新增核心表或后端类型分支。

`AssetFileMembership` 只回答“资产由哪些文件组成”。历史 `FileRelation` 混合了文件归属、业务对象和专业上下文语义，不再扩展为新仓核心关系，也不承担数据血缘。

## 3. 专业实体不能整体照搬，也不能不加判断地全部删除

新仓是空业务库，因此不需要把旧 Accession、Sample、Assembly、Annotation 记录原样迁入。但是，这些名称背后表达的科研事实仍然存在：

- 数据来自哪个样本；
- 注释使用哪个参考基因组；
- 某份数据对应哪个外部数据库编号；
- 一次实验、一个研究对象和多份数据之间是什么关系。

如果只删除专业实体而没有替代结构，这些事实最终会散落到名称、描述和无约束 JSON 中，难以查询、校验、授权和供工具插件使用。因此应先区分“数据资产”“科研上下文”和“外部标识”，再决定旧模型如何退出。

### 3.1 旧概念在新仓中的建议归属

| 旧概念 | 新仓中的建议归属 | 理由 |
| --- | --- | --- |
| Assembly | 有参考序列等核心文件时成为 `DataAsset` | 它本身是可下载、可浏览、可复用的数据 |
| Annotation | 有 GFF/GTF 等核心文件时成为 `DataAsset` | 它本身是可使用的数据，并依赖参考基因组资产 |
| Sample | `ContextEntity` | 通常说明数据来自什么样本，本身不等于一组文件资产 |
| Subject/材料 | `ContextEntity` | 说明样本或数据所对应的研究对象 |
| Experiment | `ContextEntity` | 说明数据产生时的实验背景，不替代真实运行血缘 |
| Accession | `ExternalIdentifier`，而不是数据类型 | 它是外部系统给资产或上下文分配的编号 |

部分历史专业实体可以转化为 `DataAsset`，但判断标准不是旧表名，而是它是否拥有能让资产成立的核心文件和明确用途。只有描述、标题或编号而没有核心文件的记录，不能为了保留旧结构而创建空资产。

## 4. 三类关系分别解决什么问题

### 4.1 资产与资产的关系

`DataAssetRelation` 表达稳定的数据依赖，例如：

- 基因组注释 `uses_reference` 参考基因组；
- 新版本资产 `supersedes` 旧版本资产。

资产派生不能只用一条 `derived_from` 关系代替；真实派生必须通过分析运行记录保存输入文件、输出文件、参数、软件版本、状态和日志。

“注释使用哪个参考基因组”应由 Annotation DataAsset 指向 Reference Genome DataAsset，而不是把参考基因组名称塞进 annotation metadata。

### 4.2 资产与科研上下文的关系

`AssetContextLink` 表达资产描述谁、来自谁或针对谁，例如：

- 原始测序资产 `source_sample` Sample；
- 图像资产 `about_subject` Subject；

“数据来自哪个样本”由资产到 Sample 上下文的显式关系表达。

### 4.3 科研上下文之间的关系

`ContextRelation` 表达上下文之间的稳定关系，例如：

- Sample `collected_from` Subject；
- Sample `used_in` Experiment；
- Experiment `belongs_to` 某研究设计上下文。

关系类型、方向、基数和允许连接的两端类型必须由受版本控制的规则约束，不能让用户自由输入任意关系字符串。

## 5. ExternalIdentifier 的定位

Accession 不等于一种数据，也不等于 Sample、Assembly 等上下文本身。它是“某个外部命名空间中的标识”。建议使用统一的 `ExternalIdentifier` 表达：

- `namespace`：如 NCBI BioSample、SRA、ENA、GEO 或内部编号体系；
- `value`：外部编号；
- `url`：可选的外部访问地址；
- `is_primary`：是否为目标对象的主要外部编号；
- 明确关联一个 `DataAsset` 或一个 `ContextEntity`。

数据库设计必须避免新的 `related_type + related_id` 字符串多态关系，也不使用 `GenericForeignKey`。具体采用两张显式关系表、两个可空外键还是其他约束方案，需在 ADR-005 中确定并验证唯一性和删除行为。

## 6. 为什么不能把所有内容都放进 metadata

Profile 约束的 metadata 适合保存某类资产或上下文特有、可扩展但不需要成为独立对象的属性，例如测序平台、library layout、组织部位或实验条件。

以下内容不应只作为普通 metadata 字段保存：

- 需要独立身份、被多份资产复用的对象；
- 需要建立明确关系的样本、研究对象和实验；
- 需要唯一性、强约束或稳定检索的外部标识；
- 资产之间的参考依赖、版本替代和稳定业务关系；
- 输入文件、分析运行和输出文件形成的真实血缘。

全部放入 metadata 会造成同一概念出现多个字段名、对象名称变化后无法统一更新、关系难以反向查询、插件无法可靠判断数据是否可用等问题。

metadata 也不能完全自由填写。它应由带版本的 JSON Schema 或等价 Profile 规则校验，默认拒绝未声明字段；字段含义、类型、是否必填和受控词表由 Profile 明确。

## 7. ContextEntity 的职责与字段

`ContextEntity` 是通用科研上下文层，不是第二套 `DataAsset`，也不是 openBIS 式的万能 object。它只保存“资产描述谁、来自谁、在什么实验或研究背景下产生”等可复用科研对象。

### 7.1 建议固定的核心字段

以下字段适合作为候选稳定核心字段：

- `id`：内部主键；
- `context_code`：仓库内稳定、可展示的上下文编号；
- `project_id`：所属治理和权限边界；
- `context_type_key`：如 `sample`、`subject`、`experiment`；
- `profile_key`：约束该上下文 metadata 的 Profile；
- `schema_version`：创建或校验时采用的 schema 版本；
- `schema_digest`：可选的 schema 内容摘要，用于审计；
- `name`：人可读名称；
- `status`：生命周期状态；
- `metadata`：经 Profile 校验的类型特有属性；
- `created_by`、`created_at`、`updated_at`：创建者和审计时间。

核心字段应保持少量、稳定，只保存所有上下文共有且需要数据库层直接保证的事实。物种、组织、处理条件、采样方法等类型特有字段进入受 Profile 约束的 metadata，不能不断添加到核心表。

### 7.2 如何做到跨数据类型通用

增加新的上下文类型时，原则上只需要：

1. 注册新的 `context_type_key`；
2. 发布对应的版本化 Profile/Schema；
3. 配置允许的 `AssetContextLink` 和 `ContextRelation` 类型；
4. 配置检索、展示和表单规则。

正常情况下不新增 Django model、数据库表或类型分支。只有某类对象确实需要数据库级唯一约束、独立生命周期、复杂行为并被多个模块长期复用时，才重新评审是否提升为专门实体；该提升必须通过新的 ADR，而不是边开发边加表。

## 8. 文件、上下文和血缘不能混在一起

建议结构如下：

```text
Project
├── DataAsset
│   ├── DataType + Profile + versioned metadata
│   ├── AssetFileMembership ── DataFile
│   ├── DataAssetRelation ───── DataAsset
│   ├── AssetContextLink ────── ContextEntity
│   └── ExternalIdentifier
├── ContextEntity
│   ├── Context Type + Profile + versioned metadata
│   ├── ContextRelation ─────── ContextEntity
│   └── ExternalIdentifier
└── 权限与审计
```

未来真实分析过程仍需单独表达为：

```text
输入 DataFile → AnalysisRun/ProcessingRun → 输出 DataFile
```

`FileRelation`、`AssetFileMembership`、`DataAssetRelation` 和上下文关系都不能代替真实运行记录。

## 9. 对插件和扩展能力的影响

JBrowse、分析工具和未来插件不能通过随意读取 metadata 字段猜测数据是否可用。插件应声明：

- 支持哪些 DataType/Profile；
- 需要哪些核心文件和文件角色；
- 需要哪些资产关系或上下文关系；
- 需要哪些经过 Schema 校验的 metadata；
- 用户需要什么权限。

系统根据这些规则判断某个 DataAsset 是否具备插件能力。不要在 metadata 中增加 `jbrowse_enabled` 一类与具体页面绑定的开关。插件产生的长期科研结果可以形成新的 DataAsset；临时缓存、索引副本和运行配置不自动成为资产。

## 10. 当前确定内容与尚未批准内容

### 10.1 已有 active 决策支持的稳定内容

- 新仓继续基于 GeneData 建设并从空业务库开始；
- 旧生产科研业务数据和关系不迁移，只能按新规则重新接收；
- `DataAsset` 是科研数据统一身份，`DataFile` 是物理文件事实来源；
- `AssetFileMembership` 表达资产文件组成；
- 新数据类型不能不断增加专用表和硬编码分支；
- 不建立长期双读、双写或旧关系 fallback；
- 不修改历史 migration，结构退出必须使用新的正向 migration。

### 10.2 本文形成但仍需 ADR-005 批准的候选结论

- 使用通用 `ContextEntity` 取代按 Sample、Assembly、Annotation 分别增加资产上下文中间表的扩展方式；
- Assembly 和 Annotation 在具备核心文件时主要作为 `DataAsset`；
- Sample、Subject、Experiment 主要作为 `ContextEntity`；
- Accession 统一收敛为 `ExternalIdentifier`；
- 使用 `AssetContextLink`、`ContextRelation` 和 `DataAssetRelation` 分离三类关系；
- 插件通过能力契约识别可用资产，而不是依赖任意 metadata 或硬编码类型。

在 ADR-005 批准前，不得据此删除 `DataAssetAccession`、`DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` 或相关 service、测试和 migration。

## 11. 接下来必须考虑和决定的事项

### 11.1 ADR-005 需要作出的模型决策

1. 最终名称使用 `ContextEntity` 还是 `ResearchContext`；
2. 资产 Profile 与上下文 Profile 是否共用同一注册表；
3. 首批上下文类型是否仅包含 Subject、Sample、Experiment；
4. `AssetContextLink`、`ContextRelation`、`DataAssetRelation` 的关系类型注册、方向和基数；
5. `ExternalIdentifier` 的显式外键结构、唯一约束和主标识规则；
6. Project 权限如何传递到上下文，是否允许跨 Project 关系；
7. metadata schema 的版本、摘要、升级和历史解释规则；
8. 哪些 metadata 字段需要进入搜索索引、筛选项和动态表单；
9. 插件能力契约的最小结构和判定位置；
10. `AnnotationFeature` 等现有功能以后关联 Annotation DataAsset、核心 DataFile 还是二者；
11. 当前专业模型和四张显式 DataAsset 上下文关系表的退出门槛；
12. API 和前端如何呈现资产、上下文、外部编号和关系，但本阶段不实施页面。

### 11.2 实施前需要完成的调查

- 形成 G4 调用矩阵：逐项列出 Dataset、FileRelation、Accession、Sample、Assembly、Annotation 及四张 DataAsset 上下文关系表被哪些 model、service、command、API、权限、测试和前端调用；
- 确认 active 文档之间的冲突，并在 ADR-005 批准时同步修订 ADR-003、重新定位说明和 `docs/ACTIVE_DOCUMENTS.md`；
- 明确哪些现有通用代码可在空库继续使用，哪些只服务旧迁移或旧业务；
- 使用空开发数据库验证最终 migration 链，不读取旧生产数据或旧文件；
- 先验证模型、约束、最小创建 service 和权限，再规划 API 与前端，避免同时跨层重写。

## 12. 建议执行顺序

1. 完成 ADR-004 的 G2/G3：旧数据库备份恢复验证、`manual_files` 清单和旧服务离线；
2. 完成 G4 正式代码审计矩阵；
3. 编写并评审 ADR-005，解决本文第 11 节的决策项；
4. ADR-005 批准后，独立实施新模型与 migration，并补充模型约束测试；
5. 再实施唯一创建 service、权限判断、Schema 校验和关系规则；
6. 在空开发数据库完成系统检查、migration 和测试；
7. 最小后端流程稳定后再设计 API、检索和前端交互；
8. 生产新库初始化和真实数据接收作为独立 Gate 审批，不由本设计文档自动授权。

以上顺序允许重新设计新仓，又避免在模型尚未批准时直接删除现有实现或形成第二套活动事实来源。
