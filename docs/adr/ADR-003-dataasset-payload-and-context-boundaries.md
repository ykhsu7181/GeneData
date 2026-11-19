---
title: ADR-003 DataAsset 核心载荷与专业上下文边界
status: draft
owner: 徐杨珂
last_reviewed: 2026-11-19
supersedes: null
---

# ADR-003：DataAsset 核心载荷与专业上下文边界

## 状态

Proposed，等待批准。

本文定义下一阶段拟采用的稳定架构边界，不表示相关 Registry、service、model、migration、API、前端、
生产部署或数据回填已经完成。批准本 ADR 只允许按本文顺序进入开发环境实施；生产 schema、回填和切换仍需
独立审批。

## 1. 背景

ADR-001 已确定 `DataAsset` 是目标唯一科研数据身份，ADR-002 已批准 T3 最小模型：

- `DataAsset`；
- `AssetFileMembership`；
- `DataAssetAccession`。

T3 已完成开发验证，但 migration `0026` 尚未部署生产。当前唯一创建 service 仍允许
`file_memberships=()`，静态 Registry 也只声明允许的文件角色，没有声明核心文件角色、最小核心文件数或
专业上下文规则。

T0、T1、T4 生产只读审计和生产文件清单核对进一步表明：

- 289 条 Dataset 不能机械迁移为 289 个 DataAsset；
- 130 条 transcriptome 和 29 条 Hi-C Dataset 没有可确认的本地核心文件，本质上是描述和外部数据映射；
- 607 个 FASTA、517 个 GFF、760 个 BED 及 358 个归档需要按真实 payload 和专业语义重新识别；
- genome、annotation、region set、raw reads、matrix、table 和 image 需要共享统一资产身份，但必须保留
  清晰的专业上下文和文件角色；
- 使用一个万能 context 表或 metadata JSON 会削弱外键、授权、查询和数据完整性。

因此，在重构 T4 和开始任何回填前，需要固定“什么才是 DataAsset”以及“上下文如何表达”。

## 2. 决策

### 2.1 正式 DataAsset 必须具有真实核心载荷

DataAsset 表示受 GeneData 管理、可授权、可版本化、可发布和可追溯的真实科研数据，不是 description、
外部链接或预登记占位符。

通过正式创建 service 创建 DataAsset 时必须同时满足：

1. 至少包含一个 `DataFile`；
2. 至少包含 Profile 声明数量的 primary/core 文件；
3. 每个成员的 file role 均被 Profile 允许；
4. Project、状态、可见性、schema version/digest 和 metadata 完整有效；
5. 专业上下文满足 Profile 声明的类型与基数；
6. 发布时重新校验核心文件存在性、checksum 和文件发布状态。

文件上传或导入过程可在创建 DataAsset 前使用受控临时状态，但不得通过建立无文件 DataAsset 来充当上传会话。

动态 Profile 规则无法完全由普通数据库 constraint 表达，因此采用以下边界：

- 数据库负责真实外键、重复关系、非法顺序和单一 primary 等结构不变量；
- Registry 与唯一创建 service 负责 Profile、核心文件数量、文件角色和 context 基数；
- 发布入口必须再次执行相同校验；
- API、命令和回填工具不得绕开唯一 service 形成第二套写入规则。

### 2.2 Profile 增加核心文件与上下文契约

每个可创建正式资产的 Profile 至少声明：

```yaml
allowed_file_roles: []
primary_file_roles: []
minimum_primary_files: 1
context_rules: {}
```

字段语义：

- `allowed_file_roles`：允许成为资产成员的文件角色；
- `primary_file_roles`：能够证明核心 payload 存在的角色；
- `minimum_primary_files`：正式资产所需的最小核心文件数，必须大于或等于 1；
- `context_rules`：允许或要求的显式上下文类型、最小数量、最大数量和 primary 规则。

Registry 加载时必须拒绝未知 context 类型、空 primary role、primary role 不属于 allowed roles、非法基数和
无法满足的规则。已使用的 schema version/digest 不得原地改写。

### 2.3 上下文在查询层统一，在数据库层显式分离

所有 DataAsset 可以在 API 或 service 层组合为统一 `contexts` 视图，但数据库不建立万能 context 表，
也不使用 `GenericForeignKey`、`context_type + context_id` 或任意 metadata JSON 保存核心关系。

稳定上下文关系集合为：

| 关系 | 目标对象 | 状态 |
| --- | --- | --- |
| `DataAssetAccession` | Accession | 当前已实现 |
| `DataAssetSample` | Sample | 目标新增 |
| `DataAssetAssembly` | Assembly | 目标新增 |
| `DataAssetAnnotation` | Annotation | 目标新增 |

这四张关系表是固定专业上下文集合，不按 DataType、Profile、文件格式、实验技术或课题组继续增表。

三个新增关系模型遵循同一最小约束：

- 两端使用真实外键；资产删除时关系行 `CASCADE`，专业对象使用 `PROTECT`；
- `(asset, target)` 唯一；
- 保存受控 role、`is_primary` 和 MySQL 可执行的 nullable `primary_slot`；
- 每个资产在同一 context 类型中最多一个 primary；
- 不复制目标专业实体的名称、编号或专业字段；
- 创建者和创建时间只用于审计，不形成第二份业务事实。

具体字段长度、索引名称和 role 初始词汇在实施方案中确定，但不得改变上述语义边界。

### 2.4 只关联最精确上下文，其他层级通过专业关系推导

目标规则：

| Profile | 直接上下文 | 不重复保存的可推导上下文 |
| --- | --- | --- |
| `sequence/reference_genome` | 恰好一个 Assembly | Assembly 对应的 Accession |
| `feature/genome_annotation` | 恰好一个 Annotation | Annotation 对应的 Assembly 和 Accession |
| `sequence/raw_read_set` | 一个或多个 Sample；Accession 可选 | Sample 已有的专业关系 |
| `matrix/expression_matrix` | 一个或多个 Sample | Sample 已有的专业关系 |
| `matrix/contact_matrix` | Sample 和/或 Assembly，按 Profile 版本固定 | 已明确专业关系可推导的对象 |
| `table/research_table` | 可无专业 context | 不强行绑定生物学层级 |
| `image/microscopy_image_set` | 零个或多个 Sample | Sample 已有的专业关系 |
| `image/research_image_set` | context 可选 | 不强行绑定生物学层级 |

例如，annotation DataAsset 直接关联准确 `Annotation`，不再同时复制其 Assembly 和 Accession 关系；
reference genome DataAsset 直接关联准确 `Assembly`。如果专业实体链路存在冲突，迁移必须阻断并进入人工复核，
不得通过重复写入多个 context 掩盖冲突。

### 2.5 DataType、Profile、assay 和 context 分离

- DataType 表示稳定的 payload 结构大类，例如 sequence、feature、matrix、table、image；
- Profile 表示同一大类中的用途、核心角色、metadata schema 和 context 规则；
- RNA-Seq、Hi-C、WGS 等属于 assay/library strategy；
- Sample、Assembly、Annotation、Accession 属于专业 context；
- FASTA、GFF、FASTQ、BED、cool 等属于文件格式或文件角色。

同一 assay 可以产生多个资产：Hi-C 原始 reads 是 `sequence/raw_read_set`，contact matrix 是
`matrix/contact_matrix`。不得创建按 assay 命名的核心表，也不得只根据扩展名或目录决定资产类型。

### 2.6 核心文件、辅助文件和独立结果分离

- 能决定资产成立的主数据是核心文件，例如 FASTA、FASTQ、GFF、表达矩阵、contact matrix、主结果表或
  原始图像；
- 与主体同生命周期且通常可重建的 FAI、Tabix、thumbnail、README、metadata 和展示派生物是辅助成员；
- 具有独立版本、发布、权限、引用或复用价值的分析结果建立独立 DataAsset；
- 派生过程由未来 `AnalysisRun` 表达，`AssetFileMembership` 和 `FileRelation` 均不承担血缘。

### 2.7 metadata-only Dataset 不迁移为 DataAsset

当前 130 条 transcriptome 和 29 条 Hi-C metadata-only Dataset 在 T4 映射中必须输出：

```text
mapping_status = excluded_not_asset
reason = metadata_only_external_reference
```

处理边界：

- 不创建空壳 DataAsset；
- 不为这批历史描述专门创建 Profile；
- study、sample、experiment、run、library strategy、下载地址和 MD5 继续由
  `AccessionExternalMapping` 等专业来源承载；
- Dataset 名称和 description 在退役前作为迁移证据保留，必要信息归并到明确的专业事实来源；
- 将来核心文件进入受控存储并完成校验后，再按真实 payload 创建 DataAsset，并保存外部来源标识。

## 3. 实施顺序

批准后按独立提交实施：

1. 扩展现有 Registry 和测试，增加核心文件与 context 契约；
2. 修改现有唯一创建 service 和发布前校验，拒绝无核心载荷或不符合 Profile 的正式资产；
3. 新增 `DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` 及一个新增 migration，补充模型和
   service 测试；
4. 重构 T4 dry-run，由专业实体、真实 DataFile 和已核对关系生成资产候选；
5. T4 增加 `contexts`、`exclusions`、`conflicts`、物理存在性、checksum 和权限对比输出；
6. 在开发和脱敏样本完成验证后，重新生成生产只读审计包。

每一步独立提交。不得在同一任务中夹带 API、Vue、运行时 Registry UI、AnalysisRun、生产 migration、
生产回填或 Dataset 切换。

## 4. 验收标准

至少验证：

1. 无文件和只有辅助文件的资产创建被拒绝；
2. 每个 Profile 的最小核心文件数、允许角色和 context 基数生效；
3. 无 Accession 的表格或图像仍可通过 Project 和允许的 Profile 创建；
4. reference genome 只能直接关联符合规则的 Assembly；
5. genome annotation 只能直接关联符合规则的 Annotation；
6. 一个资产可关联多个 Sample，但同一 Sample 不重复且最多一个 primary；
7. 不允许 GenericForeignKey 或字符串多态 context；
8. 159 条 metadata-only Dataset 全部进入 exclusion，不产生 DataAsset 或 membership；
9. GFF 不被自动并入 reference genome 资产；
10. 未知或冲突上下文进入阻断/人工复核，不由回填工具猜测；
11. Dataset 当前读写、API 和权限行为在切换前保持不变；
12. migration 只新增结构，不查询或回填生产数据。

## 5. 明确不做

本 ADR 不批准：

- 建立每种科研类型对应的业务表；
- 建立万能 context 表或 metadata-only DataAsset；
- 修改 `FileRelation` 承担 DataAsset、context 或血缘语义；
- 建立 AnalysisRun、AssetRelation、Collection 或 Release；
- 开发 DataAsset API、前端页面或管理员 Registry UI；
- 部署 migration、安装生产依赖、回填生产数据或切换线上服务；
- 删除 Dataset、DatasetAccession、DataFile.dataset 或现有兼容路径。

## 6. 备选方案与否决理由

### 6.1 一个通用 context 表

否决。它需要字符串类型或多个可空外键，容易形成悬空关系、复杂约束和不可预测授权，且无法利用明确的
数据库外键与 ORM 关系。

### 6.2 把 context 全部放入 metadata JSON

否决。稳定专业关系将失去引用完整性、反向查询、删除保护和唯一事实来源。

### 6.3 按数据类型增加专用资产表

否决。科研类型增加会持续增加 model、migration、API 和维护成本，与通用仓库定位冲突。

### 6.4 允许先创建空资产，之后再补文件

否决为正式创建路径。它会把描述、上传会话和真实科研数据混为一谈，并使 metadata-only 历史记录再次成为
空壳资产。文件准备应使用独立临时流程，成功后原子创建正式 DataAsset。

### 6.5 把 genome、annotation 和区域结果合成一个大资产

否决。三者具有不同版本、发布、复用、权限和专业上下文，合并后无法清晰表达变化和关系。

## 7. 后果

正面影响：

- 核心模型保持少而稳定，新增普通科研类型主要扩展 Profile；
- annotation、assembly、table、matrix 和 image 可以明确区分；
- 数据库保持真实外键和可验证约束；
- metadata-only 外部记录不会污染资产身份；
- T4 和后续回填拥有明确、可审计的阻断规则。

成本与限制：

- 增加三张固定专业上下文关系表和对应测试；
- 动态 Profile 规则需要 service 与发布入口重复校验，无法完全依赖数据库 constraint；
- 现有 T4 候选逻辑需要重构，生产只读审计必须重跑；
- 新增完全不同的长期专业对象时仍需架构评审，但不会因普通数据类型或文件格式增加表。

## 8. 回滚与生产边界

ADR 批准本身不改变运行行为。开发阶段若尚未部署生产，可回退新增 Registry/service/model 代码和未发布的
migration；不得修改已执行历史 migration。

若新增 migration 未来进入生产，即使新表为空，也必须通过受审反向 migration 或后续 migration 回滚，
不得手工删表。开始回填后必须使用独立备份、恢复验证、幂等批次和权限核对方案，本 ADR 的代码级回滚说明
不再充分。

## 9. 批准项

批准本 ADR 意味着接受：

1. 正式 DataAsset 必须具有 Profile 定义的真实核心文件；
2. metadata-only 外部描述不创建 DataAsset；
3. 使用四类固定显式上下文关系，不建立万能 context 表；
4. 新增 `DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` 三张关系表属于稳定上下文建设，
   不是按科研类型增表；
5. Profile 负责核心文件角色、最小数量和 context 基数；
6. 下一阶段只在开发环境按独立提交实施，不自动授权生产部署、回填、API/前端或 Dataset 切换。
