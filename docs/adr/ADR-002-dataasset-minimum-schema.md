---
title: ADR-002 DataAsset 最小 Schema、文件成员与发布边界
status: active
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes: null
---

# ADR-002：DataAsset 最小 Schema、文件成员与发布边界

## 状态

Accepted，2026-11-18。

本 ADR 是已批准的 T2 设计成果，只定义第一阶段目标结构和约束，不表示 model、migration、API、权限、前端、
回填或生产切换已经实现。

## 背景与生产证据

ADR-001 已批准 `DataAsset` 最终取代 `Dataset`，并要求使用真实外键成员关系连接 `DataFile`。

T0 与 T1 生产只读审计进一步确认：

- 现有 289 个 Dataset 均没有通过 `DataFile.dataset` 或 `FileRelation(dataset)` 关联文件；
- 共有 4500 个 DataFile、8820 条可解析 FileRelation；
- 文件涉及 623 个 Accession，只有 130 个 Accession 存在 Dataset 候选；
- 390 个 genome/genome_index 文件具有唯一 WGS Dataset 候选；
- 397 个文件存在 Dataset 上下文，但需要新的语义规则，其中 390 个是 annotation 文件；
- 3713 个文件没有任何 Dataset 候选；
- 2 个 HiFi reads 文件各自关联两个 Accession，需要保留共享文件可能性；
- 517 个 Annotation 对象中，483 个各有 annotation、GFF3 和 Tabix 三个文件，34 个只有 annotation
  文件；
- 1084 个 Assembly 对象参与现有文件关系。

因此，第一阶段不能只把 Dataset 改名为 DataAsset，也不能假设每个 DataFile 都能通过 Dataset 找到
资产。最小结构必须同时支持 Dataset 转换、专业实体分组和完全没有 Accession 的新数据。

## 决策范围

本 ADR 批准以下目标结构：

1. `DataAsset`；
2. `AssetFileMembership`；
3. `DataAssetAccession`；
4. 版本控制的 DataType/Profile/Schema 注册表契约；
5. 最小权限、发布和 Manifest 边界；
6. 对应的最小数据库约束和渐进迁移边界。

本 ADR 不批准：

- Project 成员、课题组共享和逐用户授权的最终物理模型；
- AnalysisRun、AssetRelation 或数据血缘表；
- DataAsset 与 Assembly、Annotation、Sample 的最终专业扩展表；
- API、serializer、Vue 页面和旧 `/datasets/` 兼容窗口；
- 生产回填规则、批次和切换日期。

这些内容必须由后续 ADR 或独立实施任务决定。

## 1. DataAsset

### 1.1 职责

`DataAsset` 是科研数据的唯一通用身份。它保存所有数据类型共同需要的身份、类型、版本、状态、可见性
和扩展 metadata，不保存文件物理属性、专业实体全部字段、权限成员列表或分析执行记录。

目标数据库表名为 `data_asset`，第一阶段继续放在现有 `files` Django app 中，不为同一能力新建平行
app 或 service。

### 1.2 最小字段

| 字段 | 目标类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `id` | BigAutoField | 是 | 内部主键 |
| `asset_code` | CharField(100) | 是 | 全局唯一，创建后不可修改 |
| `name` | CharField(255) | 否 | 展示名称，不作为身份键 |
| `project` | ForeignKey(Project, PROTECT) | 是 | 正式目标非空；公共参考数据使用明确 Project |
| `data_type_key` | CharField(100) | 是 | 注册表键，不使用不断扩张的 Django choices |
| `profile_key` | CharField(100) | 是 | 注册表中该数据类型下的 Profile 键 |
| `schema_version` | CharField(50) | 是 | 创建或发布时采用的 schema 版本 |
| `schema_digest` | CharField(64) | 是 | 对应 schema 内容的 SHA-256 |
| `version` | CharField(100) | 否 | 科研数据版本；空值不参与身份唯一性 |
| `status` | CharField(50) | 是 | 第一阶段沿用 draft/submitted/approved/released/archived |
| `visibility` | CharField(50) | 是 | 第一阶段沿用 private/lab_internal/public |
| `metadata` | JSONField | 是 | 默认空对象，必须通过指定 schema 校验 |
| `description` | TextField | 否 | 通用说明，不保存专业结构化字段 |
| `created_by` | ForeignKey(User, SET_NULL) | 否 | 历史迁移可为空，新建服务记录操作者 |
| `created_at` | DateTimeField | 是 | 自动记录 |
| `updated_at` | DateTimeField | 是 | 自动记录 |
| `published_at` | DateTimeField | 否 | 发布流程设置，不由普通更新接口直接写入 |

### 1.3 目标约束与索引

数据库目标至少包括：

- `asset_code` 唯一；
- `asset_code`、`data_type_key`、`profile_key`、`schema_version` 和 `schema_digest` 不允许空字符串；
- `project` 最终非空并使用 `PROTECT`；
- `metadata` 默认 `{}`，不得使用共享可变默认值；
- 索引 `(project, status)`、`(project, data_type_key)` 和 `(visibility, status)`；
- 不建立依赖名称、描述或任意 JSON 内容的身份唯一约束。

`asset_code` 不可变、发布状态转换、released/archived 禁止硬删除和 public 可见性条件，由创建/发布
service 与权限 ADR 共同实现并测试。第一阶段不引入数据库 trigger。

### 1.4 Metadata 边界

`metadata` 只能保存注册表声明的扩展属性，例如实验条件、单位或外部标识。以下内容不得放入
`metadata`：

- `file_path`、checksum、文件大小等 DataFile 事实；
- Project、DataFile、Accession 等核心关系 ID；
- 用户、课题组和授权列表；
- Assembly、Annotation 的整套专业字段副本；
- 软件、参数、日志和 AnalysisRun 执行事实；
- 无 schema、无版本的临时键值堆积。

高频查询字段如果经真实使用证明需要成为核心字段，应通过独立 ADR 和 migration 提升，不能在多处重复
保存。

## 2. AssetFileMembership

### 2.1 职责

`AssetFileMembership` 是 DataAsset 与 DataFile 之间唯一正式成员关系，目标表名为
`asset_file_membership`。它不取代 DataFile，不承担血缘，也不使用 `FileRelation` 字符串多态关系。

一个 DataFile 可以属于多个 DataAsset，以支持共享参考文件和 T1 发现的多 Accession HiFi reads；同一
DataAsset 内同一 DataFile 只能出现一次。

### 2.2 最小字段

| 字段 | 目标类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `id` | BigAutoField | 是 | 内部主键 |
| `asset` | ForeignKey(DataAsset, CASCADE) | 是 | 删除仅允许发生在未发布草稿 |
| `data_file` | ForeignKey(DataFile, PROTECT) | 是 | 资产成员存在时不得删除物理文件事实 |
| `file_role` | CharField(100) | 是 | 注册表控制的角色键 |
| `position` | PositiveIntegerField | 是 | 默认 0，同角色内稳定排序 |
| `is_primary` | BooleanField | 是 | 默认 false |
| `created_by` | ForeignKey(User, SET_NULL) | 否 | 记录创建操作者 |
| `created_at` | DateTimeField | 是 | 自动记录 |

不在成员表复制文件名、路径、大小、格式、checksum、访问级别或发布状态。

### 2.3 约束

数据库目标至少包括：

- 唯一 `(asset, data_file)`；
- 唯一 `(asset, file_role, position)`；
- 条件唯一 `(asset, file_role)` where `is_primary=true`；
- `position >= 0`；
- `file_role` 不允许空字符串；
- 索引 `(asset, file_role, position)` 和 `(data_file, asset)`。

同一文件在同一资产中承担多个业务角色的需求尚无生产证据，第一阶段不通过重复成员行支持。如果后续
出现真实案例，应评审角色集合或独立角色表，而不是放宽重复约束。

## 3. DataAssetAccession

### 3.1 职责

`DataAssetAccession` 替代 DatasetAccession 的资产上下文语义，目标表名为
`data_asset_accession`。DataAsset 可以没有 Accession，也可以具有多个 Accession。

第一阶段只实现生产证据明确需要的 Accession 上下文关系。Assembly、Annotation、Sample 等专业扩展
继续使用自身现有事实，并在独立 ADR 中决定真实外键扩展；不得先建立通用字符串上下文表。

### 3.2 最小字段与约束

| 字段 | 目标类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `id` | BigAutoField | 是 | 内部主键 |
| `asset` | ForeignKey(DataAsset, CASCADE) | 是 | 资产上下文 |
| `accession` | ForeignKey(Accession, PROTECT) | 是 | 研究材料上下文 |
| `relation_role` | CharField(50) | 是 | primary/derived/reference |
| `source` | CharField(100) | 否 | 保留已存在的来源语义 |
| `created_at` | DateTimeField | 是 | 自动记录 |

约束：

- 唯一 `(asset, accession)`；
- 每个 asset 最多一个 `primary` Accession；
- 索引 `(accession, asset)`；
- 不要求每个 DataAsset 都具有 primary 或任何 Accession。

T1 的两个多 Accession HiFi reads 文件不能自动选择 primary。它们应进入人工核对清单；如果确认是共享
文件，可通过多个资产成员关系表达，不复制 DataFile。

## 4. DataType、Profile 与 Schema 注册表

第一阶段不新增 DataType、Profile、PropertyDefinition 数据库模型。注册表采用版本控制的 YAML/JSON，
由唯一加载与校验 service 提供：

- `data_type_key`；
- `profile_key`；
- metadata JSON Schema；
- 允许的 file role；
- 字段单位、词表和语义注释；
- schema version 和 SHA-256 digest；
- deprecated 状态和替代项。

正式 DataAsset 保存实际使用的 key、version 和 digest。注册表文件进入代码评审和 CI；新增普通数据
类型只增加注册表条目和针对性测试，不修改 DataAsset model、核心 API 分支或前端硬编码枚举。

注册表的文件目录、加载缓存和 JSON Schema 库由后续原型任务决定，但只能有一个活动加载入口。

## 5. 最小权限与发布边界

第一阶段不新增第二套 ACL 或把权限列表写入 metadata。有效访问决策必须由唯一授权 service 计算，并
同时考虑 Project、DataAsset 和 DataFile：

1. 无法解析 Project、资产状态或文件状态时拒绝；
2. Project 成员资格只能提供进入项目的基础资格，不能绕过资产或文件限制；
3. DataAsset 的 visibility/status 不能放宽 DataFile 自身的 access_level/publication_status；
4. 每次返回文件、Manifest、上下游或批量结果时逐文件重新授权；
5. public 资产只有在发布流程批准后才可公开，公开资产中的未发布或受限文件仍不可返回；
6. 拒绝结果不得泄露私有资产或文件是否存在、名称、类型和元数据；
7. Dataset 迁移必须逐资产、逐文件对比迁移前后的有效权限，任何放宽都阻止切换。

第一阶段沿用现有 status 和 visibility 值是为了无损迁移，不等于复用当前分散的权限实现。状态转换、
角色权限、Project 成员表和公开撤回规则由 T3 实施方案细化，但不得削弱上述 fail-closed 不变量。

## 6. Collection、Release 与 Manifest 决策

第一阶段不新增 Collection 或 Release 数据库实体。T0 中同一 BioProject 被 289 个 Dataset 共享，说明
BioProject 是项目/外部研究上下文，不是 289 组重复资产的唯一键；现有证据也不足以证明需要一个可独立
授权、独立版本化的多资产 Collection。

第一阶段采用以下边界：

- DataAsset 是可版本化、可发布的最小科研数据身份；
- Project 负责组织多个 DataAsset；
- Manifest 是按授权和指定 schema 生成的 DataAsset/DataFile 投影视图，不拥有第二份数据；
- Manifest 必须携带生成时间、schema version、资产和文件稳定 ID、checksum，并逐文件授权；
- 需要冻结多资产发布快照时，必须先提供真实消费者、不可变性、版本和撤回需求，再通过独立 ADR 引入
  Release；
- 不得为了保留 Dataset 名称而建立无明确职责的 Collection 包装层。

此决策减少第一阶段表和 service 数量，但不阻止以后在真实需求出现时新增职责单一的 Release。

## 7. T1 到 T2 的映射边界

### 7.1 可以进入 dry-run 的规则

| 来源 | T2 候选规则 | 当前状态 |
| --- | --- | --- |
| 289 个 Dataset | 每个 Dataset 生成一个同 code 的 DataAsset 候选 | 仅设计，未回填 |
| DatasetAccession | 生成 DataAssetAccession 候选 | 仅设计，未回填 |
| 390 个 genome/genome_index 文件 | 挂到相同 Accession 的唯一 WGS 资产候选 | T1 唯一候选，仍需 dry-run 核对 |
| 517 个 Annotation | 原则上一条 Annotation release 对应一个 annotation DataAsset 候选 | 分组规则待独立映射任务验证 |
| 无 Dataset 的 genome 文件 | 原则上按 Assembly 形成 genome DataAsset 候选 | 需处理同 Accession 多 Assembly 和默认版本 |

### 7.2 不得自动决定的规则

- 390 个 annotation 文件不得直接挂到 WGS、RNA-seq 或 Hi-C Dataset 转换资产；
- TEs、centromere、codon、coreBlocks、miRNA、rRNA 和 tRNA 是独立资产还是 genome 资产成员，需按
  独立版本、发布和复用需求决定；
- raw reads 不得只按 Accession 合并，需核对 Sample、实验、平台、run 和共享文件语义；
- transcriptome 不得只按 Accession 合并，需保留组织、处理、重复和表达矩阵语义；
- 两个多 Accession HiFi reads 文件不得自动复制或强制选择一个归属；
- `FileRelation` 现有关系可作为迁移证据，但不能直接转换为通用资产关系类型。

`unique_type_candidate` 只表示候选唯一，不等于已批准回填事实。

## 8. 渐进实施边界

后续实现必须拆分为独立任务：

1. 批准本 ADR；
2. 完成注册表最小原型和验证测试；
3. 形成 T3 model/migration/授权 service 实施方案并单独批准；
4. 新增 DataAsset、DataAssetAccession、AssetFileMembership model 和 migration；
5. 初始 migration 可为历史回填暂时允许 `project` 或 schema 字段为空，但新建 service 从第一版即拒绝
   不完整正式资产；
6. 编写只读映射 dry-run，输出候选、冲突、权限对比和人工处理原因；
7. 分批幂等回填并核对，不切换活动读写；
8. 单独批准并执行读写切换；
9. 在生产数据完整后通过新 migration 收紧非空和其他目标约束；
10. 观察期结束后退役 Dataset 活动引用和兼容层。

不得在 schema migration 中执行大规模回填，不得在此阶段新增双写或 `FileRelation(data_asset)`。

## 9. 验收标准

本 ADR 获批前只算设计草案。批准标准：

- 能表达无 Accession、无 Annotation 的 Project + DataAsset + DataFile；
- 新数据类型不修改核心 DataAsset model；
- DataFile 保持唯一物理文件事实；
- 一个文件可安全属于多个资产；
- 现有 DatasetAccession 和 T1 多 Accession 情形均可表达；
- 不新增 GenericForeignKey、字符串多态核心关系或第二个文件模型；
- 权限只收紧不放宽，Manifest 不形成第二份事实来源；
- 第一阶段不在缺少真实证据时增加 Collection/Release 表；
- 目标约束、迁移期临时放宽和最终收紧有明确边界；
- 未把权限、血缘和 Collection/Release 未决事项偷偷固化进最小 schema；
- 后续实现可以用独立 migration、测试、dry-run 和回滚逐步完成。

## 10. 被否决的方案

### 把所有扩展字段直接加到 DataAsset

否决。会使每增加一种科研数据都修改核心表，并复制专业实体事实。

### 第一阶段建立完整动态类型数据库

否决。当前没有多人在线编辑类型定义、数据库级类型权限或运行时租户定制证据。先使用版本控制注册表更
简单、可审计、可删除。

### 使用 GenericForeignKey 或 related_type + related_id

否决。无法提供真实外键和数据库完整性，并会复制 FileRelation 的已知债务。

### 每个专业实体立即新增一张 DataAsset 中间表

否决。T1 只证明 Accession 关系是第一阶段必要结构。其他扩展按真实查询、权限和迁移需求单独批准，
避免一次性堆积模型。

### 一个 DataFile 只能属于一个 DataAsset

否决。共享参考文件和 T1 多 Accession HiFi reads 已证明需要多资产成员能力。

## 相关文档

- `AGENTS.md`
- `docs/ACTIVE_DOCUMENTS.md`
- `docs/adr/ADR-001-dataasset-unified-identity.md`
- `docs/architecture/GeneData_通用科研数据仓库总体设计.md`
- `docs/audits/GeneData_Dataset到DataAsset实施前审计_20261118.md`
