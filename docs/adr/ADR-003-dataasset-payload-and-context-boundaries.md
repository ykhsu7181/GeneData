---
title: ADR-003 DataAsset 核心载荷与专业上下文边界
status: active
owner: 徐杨珂
last_reviewed: 2026-11-19
supersedes: null
amends: ADR-002 sections 4 and 7
---

# ADR-003：DataAsset 核心载荷与专业上下文边界

## 状态

Accepted，2026-11-19。

截至 2026-11-19，实施顺序第 1 步已在开发分支完成：新增三张显式上下文关系表、migration `0027` 和
模型测试；尚未部署生产。Registry v2、创建 service、T4 重构、生产审计、回填和切换仍未实施。

本文定义下一阶段拟采用的稳定架构边界，不表示相关 Registry、service、model、migration、API、前端、
生产部署或数据回填已经完成。批准本 ADR 只允许按本文顺序进入开发环境实施；生产 schema、回填和切换仍需
独立审批。

本 ADR 修订 ADR-002 的 Registry 契约和 Dataset 映射边界，不改写 ADR-002 的历史正文。两者发生
冲突时，以本 ADR 对核心载荷、Profile 契约、上下文和 metadata-only Dataset 的决策为准。

## 1. 背景

ADR-001 已确定 `DataAsset` 是目标唯一科研数据身份，ADR-002 已批准 T3 最小模型：

- `DataAsset`；
- `AssetFileMembership`；
- `DataAssetAccession`。

T3 已完成开发验证，但 migration `0026` 尚未部署生产。当前唯一创建 service 仍允许
`file_memberships=()`，静态 Registry 也只声明允许的文件角色，没有声明 core/auxiliary 分类、角色基数或
专业上下文规则。当前 Registry 的 DataType key 是 `genome`、`microscopy`、`tabular`，且
`schema_digest` 只覆盖 metadata JSON Schema，没有覆盖文件与上下文规则。

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

通过 canonical creation service 创建 DataAsset 时必须同时满足：

1. 至少包含一个 `DataFile`；
2. 每种文件角色均满足 Profile 声明的 core/auxiliary 分类和 `min/max` 基数；
3. 至少一个 core 角色的 `min` 大于或等于 1，且实际核心成员满足该要求；
4. Project、状态、可见性、schema version/digest 和 metadata 完整有效；
5. 专业上下文满足 Profile 声明的类型与基数；
6. 每个核心成员均引用已经持久化的 `DataFile`。

文件上传或导入过程可在创建 DataAsset 前使用受控临时状态，但不得通过建立无文件 DataAsset 来充当上传会话。
创建阶段不把存储访问和发布检查混入数据库事务；物理文件存在性、checksum、current 状态和文件发布状态由
未来的 DataAsset 发布流程强制校验。直接 ORM 写入在数据库结构上仍可能暂时产生无成员资产，但不属于受支持的
业务写入路径，API、命令和回填工具不得采用该方式。

动态 Profile 规则无法完全由普通数据库 constraint 表达，因此采用以下边界：

- 数据库负责真实外键、重复关系、非法顺序等结构不变量；
- Registry 与唯一创建 service 负责 Profile、核心文件数量、文件角色和 context 基数；
- 本阶段提取唯一的 Profile 契约校验入口，由创建 service 使用；未来发布 service 必须复用该入口并增加
  物理文件、checksum 和发布状态检查；
- API、命令和回填工具不得绕开唯一 service 形成第二套写入规则。

### 2.2 Profile 增加核心文件与上下文契约

每个可创建正式资产的 Profile 至少声明：

```yaml
file_role_rules:
  genome_fasta: {class: core, min: 1, max: 1}
  fasta_index: {class: auxiliary, min: 0, max: 1}
context_rules: {}
```

字段语义：

- `file_role_rules`：以 file role 为 key，统一声明 `class`、`min` 和 `max`；
- `class`：只允许 `core` 或 `auxiliary`；
- `min/max`：该角色成员数的最小和最大值，`max: null` 表示不设上限；
- `context_rules`：允许或要求的显式上下文类型、最小数量和最大数量。

Registry 加载时必须拒绝空 file role、未知 class、负数或布尔型基数、`max < min`、没有任何
`class=core && min>=1` 的可创建 Profile、未知 context 类型和非法 context 基数。

`AssetFileMembership.is_primary` 只表示同一 file role 中的代表文件，不决定文件是否属于核心载荷。
core/auxiliary 完全由 Profile 的 `file_role_rules` 决定。这样既能表达恰好一个 FASTA，也能表达成对 R1/R2、
多 lane FASTQ、多个核心图像和可选索引，而不增加后端类型分支。

现有字段名 `schema_digest` 保持不变，但从 Registry v2 开始，其规范含义扩展为完整 Profile 契约的
SHA-256，而不再只计算 metadata JSON Schema。规范化 digest 至少覆盖：

- `data_type_key`、`profile_key` 和 `schema_version`；
- metadata JSON Schema；
- `file_role_rules`；
- `context_rules`。

上述任一规则变化都必须提升 `schema_version` 并产生新 digest。已经被 DataAsset 使用的 Profile 版本不得
原地改写或复用旧 digest。由于 migration `0026` 尚未部署生产且生产不存在 DataAsset，本次可在进入生产前
一次性校正 digest 语义，不增加 `profile_digest` 字段，也不保留旧 digest fallback。

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

三个新增关系模型遵循同一最小结构：

- 两端使用真实外键；资产删除时关系行 `CASCADE`，专业对象使用 `PROTECT`；
- `(asset, target)` 唯一；
- 保存 `created_by` 和 `created_at` 作为审计信息；
- 不复制目标专业实体的名称、编号或专业字段；
- Profile 通过 `context_rules` 决定每种 context 的最小和最大数量。

第一版不增加通用 role、`is_primary` 或 `primary_slot`：reference genome 与 annotation Profile 已通过最大数量
为 1 表达唯一上下文；多个 Sample 默认是平等研究对象。未来只有出现明确、跨 Profile 可复用的业务语义并经
独立评审后，才允许增加关系角色。现有 `DataAssetAccession` 的 `relation_role + primary_slot` 保持不变，
但不作为其他上下文关系的复制模板。

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

Registry v2 采用稳定结构大类 `sequence`、`feature`、`matrix`、`table`、`image`，在生产出现 DataAsset
之前一次性替换当前原型 key：

| 当前原型 key | Registry v2 |
| --- | --- |
| `genome/reference_genome` | `sequence/reference_genome` |
| `microscopy/image_set` | `image/microscopy_image_set` |
| `tabular/research_table` | `table/research_table` |

Registry、T4、测试和开发样例必须在同一个实施阶段同步更新。不得保留双 key、alias、fallback 或自动转换层；
如果发现生产已存在 DataAsset，立即停止该步骤并重新评审迁移方案。

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

本节明确修订 ADR-002 第 7.1 节“每个 Dataset 生成一个同 code 的 DataAsset 候选”的旧映射假设：
metadata-only Dataset 直接进入 exclusion，不生成资产候选、文件成员或上下文写入候选。其他 Dataset 也必须
先满足本 ADR 的核心载荷与 context 规则，不能仅因 legacy Dataset 存在就生成 DataAsset。

## 3. 实施顺序

批准后按独立提交实施：

1. 新增 `DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` 及一个只创建空表和约束的 migration，
   补充模型测试，不改变现有 Registry 或活动读写；
2. 在一个原子提交中将 Registry 升级为 v2、切换稳定 DataType key、采用 `file_role_rules`、修正完整 digest、
   提取 canonical validator、修改创建 service，并完成 T4 对新 key/role 的最小必要适配和相关测试；
3. 独立重构 T4 dry-run，由专业实体、真实 DataFile 和已核对关系生成候选，并增加 `contexts`、
   `exclusions`、`conflicts`、物理存在性、checksum 和权限对比输出；
4. 运行受影响模块完整测试，确认每个提交均可独立运行和回退；
5. 在开发和脱敏样本验证通过后，重新生成生产只读审计包。

每一步独立提交。不得在同一任务中夹带 API、Vue、运行时 Registry UI、AnalysisRun、生产 migration、
生产回填或 Dataset 切换。

## 4. 验收标准

至少验证：

1. canonical creation service 拒绝无文件和只有辅助文件的资产；直接 ORM 能力不被描述成正式写入接口；
2. 每个 Profile 的 file role `class/min/max` 和 context 基数生效；
3. 无 Accession 的表格或图像仍可通过 Project 和允许的 Profile 创建；
4. reference genome 只能直接关联符合规则的 Assembly；
5. genome annotation 只能直接关联符合规则的 Annotation；
6. 一个资产可关联多个平等 Sample，同一 Sample 不重复，不引入无真实语义的 primary；
7. 不允许 GenericForeignKey 或字符串多态 context；
8. 159 条 metadata-only Dataset 全部进入 exclusion，不产生 DataAsset 或 membership；
9. GFF 不被自动并入 reference genome 资产；
10. 未知或冲突上下文进入阻断/人工复核，不由回填工具猜测；
11. Dataset 当前读写、API 和权限行为在切换前保持不变；
12. migration 只新增结构，不查询或回填生产数据；
13. 完整 Profile 契约任一规则变化都会改变 digest，且必须提升 schema version；
14. Registry v2、T4 和测试不再使用 `genome`、`microscopy`、`tabular` 旧 key，也不存在 alias/fallback；
15. paired reads、多个同角色核心图像和可选辅助索引均可只通过 `file_role_rules` 表达。

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

### 6.4 允许通过正式业务入口先创建空资产，之后再补文件

否决为正式创建路径。它会把描述、上传会话和真实科研数据混为一谈，并使 metadata-only 历史记录再次成为
空壳资产。文件准备应使用独立临时流程，成功后通过 canonical creation service 原子创建正式 DataAsset。
数据库和 ORM 仍可支持测试、迁移或事务内部的暂态对象，但不得成为 API、命令或回填的业务契约。

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

- 增加三张字段精简的固定专业上下文关系表和对应测试；
- 动态 Profile 角色基数和 context 规则需要唯一校验入口，并由创建 service 与未来发布 service 复用，无法完全依赖数据库
  constraint；
- Registry v2 会一次性替换尚未进入生产的原型 DataType key 和 digest 语义；
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
   不是按科研类型增表；第一版不增加通用 role、`is_primary` 或 `primary_slot`；
5. Profile 通过单一 `file_role_rules` 负责 core/auxiliary 与逐角色 `min/max`，并负责 context 基数；现有
   `schema_digest` 覆盖完整 Profile 契约；
6. Registry v2 使用 `sequence/feature/matrix/table/image` 稳定大类并清理旧原型 key，不提供兼容层；
7. 本 ADR 修订 ADR-002 的 Registry 和 Dataset 候选映射边界，159 条 metadata-only Dataset 直接排除；
8. 下一阶段只在开发环境按独立提交实施，不自动授权生产部署、回填、API/前端或 Dataset 切换。
