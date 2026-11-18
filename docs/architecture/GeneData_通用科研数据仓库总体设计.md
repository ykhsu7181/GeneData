---
title: GeneData 通用科研数据仓库总体设计
status: active
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes: GeneData DataAsset 通用科研数据仓库整体设计方案 v0.2
---

# GeneData 通用科研数据仓库总体设计

## 1. 文档定位

本文是 GeneData 数据仓库的 active 总体设计，负责说明稳定目标、对象边界、扩展方式、迁移顺序和实施门禁。

本文不表示目标 model、migration、API、权限、前端或生产数据迁移已经完成。当前实现以代码、migration、测试和 CI 为准；具体表字段、约束和接口必须由后续子 ADR 与分阶段任务批准。

相关依据：

- `AGENTS.md`：仓库级开发与安全边界；
- `docs/adr/ADR-001-dataasset-unified-identity.md`：DataAsset 唯一身份决策；
- `docs/audits/GeneData_Dataset到DataAsset实施前审计_20261118.md`：当前 Dataset 调用面证据；
- `docs/ACTIVE_DOCUMENTS.md`：活动文档索引。

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
- 当前不存在 DataAsset 应用模型和 migration；
- `DataFile` 是当前正式物理文件实体；
- `Dataset` 同时承担身份、类型、版本、发布、可见性、文件分组、Accession 和 Manifest 语义；
- Dataset 文件关系同时存在 `DataFile.dataset` 外键和 `FileRelation(dataset)` 两条路径；
- 当前代码调用面审计已完成，生产数据只读审计尚未执行；
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

完整字段、状态机、索引和数据库约束由最小 schema ADR 决定。

T2 已批准决策见 `docs/adr/ADR-002-dataasset-minimum-schema.md`。该 ADR 是后续实施依据，但不表示
model、migration、API、权限、前端、回填或生产切换已经完成。

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

必须通过数据库约束阻止重复、悬空关系和非法顺序。最终模型名称及“同角色最多一个 primary”等约束由子 ADR 确认。

### 4.5 专业实体和研究对象

Species、Accession、Sample、Assembly 和 Annotation 均为可选上下文或领域扩展，不是 DataAsset 的必填上级。

- Assembly 保存组装方法、测序技术、N50、contig 等专业字段；
- Annotation 保存注释数据库、版本、Assembly 关系等专业字段；
- Accession/Sample 保存材料和外部登录信息；
- DataAsset 保存这些对象共同需要的通用身份、状态和可见性。

高频稳定关系使用真实外键或显式中间表，不新增 GenericForeignKey 或字符串多态核心关系。

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

## 5. 类型与 Metadata 扩展

借鉴 openBIS 的类型、属性定义和语义注释方法，但不复制其完整 Space/Collection/Object 层级。

目标配置层包括：

- DataType：数据大类；
- Profile：同一大类下的用途或结构；
- PropertyDefinition：字段类型、单位、词表和校验；
- Schema version/digest：冻结正式数据使用的规则版本；
- Semantic annotation：字段与外部标准含义的映射。

第一阶段原则：

- 注册表使用版本控制的 YAML/JSON；
- 启动或 CI 校验 code 唯一性、引用完整性和 Schema 合法性；
- 正式 DataAsset 保存 schema version/digest；
- metadata 只能保存 Schema 允许的扩展字段；
- 高频过滤和强约束字段保留为数据库列；
- 暂不建设网页编辑器和复杂注册表数据库。

新增普通数据类型应通过注册表扩展，而不是修改核心 Model choices、增加专用 API 路由或复制前端页面。

## 6. 入库、权限和版本

### 6.1 通用入库

目标最小流程：

```text
选择 Project
  -> 选择 DataType/Profile
  -> 校验 metadata 与 schema version
  -> 创建 DataAsset
  -> 登记 DataFile 和 checksum
  -> 创建文件成员关系
  -> 可选关联 Accession/Assembly/Annotation
  -> 输出审计结果
```

当前 `import_data_batch`、现有 manifest importer 和文件写入服务应作为迁移调查对象；不得复制一套 DataAsset 专用写入逻辑。DataAsset 写入必须最终收敛到唯一 service，并支持 dry-run、有限批次、幂等、审计和失败重试。

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

### 8.2 固定阶段

1. 仓库调用面审计——已完成；
2. 生产数据只读审计——T0、T1 已完成，证据在仓库外受控保存；
3. 最小 schema、权限和 Collection/Release 边界 ADR——已合并为 ADR-002 并批准；
4. 新增结构和测试，不切换活动读写；
5. Dataset -> DataAsset dry-run 映射；
6. 分批、幂等回填；
7. 核对记录、关系、权限和 checksum；
8. 一次性切换活动读写；
9. 生产验收和回滚观察期；
10. 删除 Dataset 活动引用和兼容层；
11. 通过新 migration 删除旧表；
12. CI 增加防回流检查。

切换前 Dataset 是活动事实来源；切换后 DataAsset 是活动事实来源。允许受控影子回填和对比，不允许无期限双写。

### 8.3 删除门槛

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

1. 生产 Dataset T0 只读审计方案与脱敏输出；
2. DataAsset 最小 schema/constraint ADR——已批准；
3. 版本控制 Masterdata/Profile/Schema Registry 原型；
4. T3 最小 DataAsset、文件成员和授权 service 实施方案；
5. 最小 DataAsset + 文件成员后端和测试；
6. IR64、显微图像、普通表格三个试点；
7. API、Vue 与外部工具切换；
8. Dataset 分阶段回填、切换和退役。

每个阶段必须有独立范围、验收、回滚和完成证据，不自动开始下一阶段。

## 10. 通用性验收标准

- 无 Accession/Annotation 的数据能够用 Project + DataAsset + DataFile 完整入库；
- 新普通类型不修改核心身份 Model；
- DataFile 始终是唯一物理文件身份；
- Dataset 与 DataAsset 不长期并存为活动事实来源；
- 专业实体不重复保存活动通用身份；
- 分析过程可按输入、运行和输出追溯；
- 文件和血缘节点逐节点授权；
- 发布、回填、迁移和生产验收具有可重复证据；
- 不新增 GenomeFile 依赖、字符串多态核心关系或无期限兼容层。

## 11. 未决事项

以下事项不是已实现或已批准的物理结构：

- DataAsset 完整字段、表名、索引、constraint 和状态机；
- AssetFileMembership 最终名称与 primary 约束；
- Project 成员、共享和公开发布权限；
- Collection、Release 和 Manifest 是否独立建模；
- AnalysisRun 与 AssetRelation 的最终表结构；
- Assembly/Annotation 扩展关系和迁移顺序；
- 旧 Dataset API 下线日期和生产维护窗口。
