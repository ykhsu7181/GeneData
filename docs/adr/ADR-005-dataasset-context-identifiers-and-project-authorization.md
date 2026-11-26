---
title: ADR-005 DataAsset 通用上下文、外部标识与 Project 授权边界
status: active
owner: 徐杨珂
last_reviewed: 2026-11-26
supersedes: null
amends:
  - ADR-001 section 3
  - ADR-002 section 3 and related acceptance criteria
  - ADR-003 sections 2.3, 2.4, 4 and 5
---

# ADR-005：DataAsset 通用上下文、外部标识与 Project 授权边界

## 状态

Accepted，2026-11-26。

本文批准新仓目标结构、授权边界和旧结构退出前置条件，不表示相关 model、migration、service、API、前端、删除 migration、生产部署或真实数据验收已经完成。实施仍须按第 6 节拆分为独立阶段，并分别评审、测试和验收。

## 1. 背景

ADR-001 至 ADR-003 已形成并在开发环境实现部分 DataAsset 基础：

- `DataAsset` 是目标科研数据统一身份；
- `DataFile` 是物理文件事实来源；
- `AssetFileMembership` 表达资产文件组成；
- Profile 约束 metadata、核心/辅助文件角色和上下文数量；
- 当前开发代码包含 `DataAssetAccession`、`DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` 四张显式关系表。

ADR-004 随后决定新仓从空业务库开始，不迁移旧生产数据库中的科研业务记录和关系。G4 代码审计进一步确认：

1. 当前主要 API、页面、文件权限、JBrowse 和导入链仍依赖 `Dataset` 或 `FileRelation`；
2. DataAsset 模型和最小 service 已存在，但尚未接入正式业务入口；
3. `Project.owner` 只是字符串，没有项目成员、角色和真实用户授权关系；
4. 四张专业关系表和固定 `context_rules` 会让新增上下文种类继续要求后端改表或改分支；
5. 当前 `DataFile` 与 `DataAsset` 同时包含发布或可见性相关字段，目标事实来源尚未收敛；
6. 直接删除 Accession、Sample、Assembly、Annotation 会使科研事实退化为名称、描述或无约束 JSON。

因此，新仓需要在删除旧结构前决定：哪些对象是资产、哪些是上下文、外部编号如何保存、资产之间如何关联、文件权限从哪里继承，以及 Project 如何成为真实授权边界。

## 2. 决策目标与本次范围

### 2.1 决策目标

本 ADR 需要同时满足：

- 以科研文件数据资产为核心，不转向 openBIS 式万能 object；
- 核心表数量稳定，不因 genome、Hi-C、图像、表格或新实验技术持续增加表；
- 资产、文件、科研上下文、外部标识和真实血缘分别表达；
- 关键关系可以查询、反向追踪、授权和校验，不全部藏入 metadata；
- 增加普通数据类型或上下文类型时，原则上只增加版本化 Profile 和关系规则，不修改 Django model；
- 现有旧模型只能在替代结构、调用切换和测试完成后通过正向 migration 退出；
- 权限默认安全失败，跨 Project 引用不能取得目标 Project 的管理权。

### 2.2 本 ADR 决定的内容

- DataAsset、Project、DataFile 和 AssetFileMembership 的职责；
- `ProjectMembership` 与真实登录用户的第一阶段权限；
- `ContextEntity`；
- `ExternalIdentifier` 和受控 namespace；
- `DataAssetRelation`、`AssetContextLink`、`ContextRelation`；
- Relation Registry、Namespace Registry、资产 Profile 与上下文 Profile 的职责；
- 旧专业实体的目标归属和退出门槛。

### 2.3 本 ADR 暂不决定的内容

- DataAccessToken、服务账号、API scope 和机器凭证；
- Profile 由特权普通用户在线创建、审批和发布的管理界面；
- 私有或内部资产的跨 Project 共享；
- 对象级自定义 ACL；
- AnalysisRun/ProcessingRun 的真实血缘模型；
- API URL、serializer 和前端页面布局。

这些内容不得通过临时字段、自由 metadata、平行模型或长期兼容层提前实现。

## 3. 决策

### 3.1 保留固定的资产、文件和上下文核心

新仓稳定核心为：

```text
Project
├── ProjectMembership
├── ExternalIdentifier
├── owned DataAsset
│   ├── AssetFileMembership ── DataFile
│   ├── DataAssetRelation ───── DataAsset
│   ├── AssetContextLink ────── ContextEntity
│   └── ExternalIdentifier
└── ContextEntity
    ├── ContextRelation ─────── ContextEntity
    └── ExternalIdentifier
```

各自只承担一种职责：

- `Project`：资产和上下文的所有权、成员及治理边界；
- `DataAsset`：可独立发现、授权、版本化和使用的科研数据；
- `DataFile`：物理文件的唯一事实来源；
- `AssetFileMembership`：资产由哪些文件组成以及每个文件的角色；
- `ContextEntity`：资产描述谁、来自谁或在什么研究背景下产生；
- `ExternalIdentifier`：外部命名空间给 Project、资产或上下文分配的标识；
- `DataAssetRelation`：资产之间稳定的参考或版本关系；
- `AssetContextLink`：资产与科研上下文的关系；
- `ContextRelation`：科研上下文之间的关系；
- 独立运行模型：真实输入文件、处理过程和输出文件血缘，不由上述关系代替。

不建立新的平行文件模型，也不使用 `FileRelation` 承担这些新语义。

### 3.2 一个 DataAsset 只有一个 owning Project

现有 `DataAsset.project` 字段继续保留，其目标语义明确为唯一 owning Project，不因语义澄清而仅为改名新增 migration。

owning Project 负责资产的编辑、审核、发布和归档。其他 Project 使用资产不改变资产归属，也不取得管理权限。

第一阶段规则：

- `AssetContextLink` 的资产和上下文必须属于同一 Project；
- `ContextRelation` 两端必须属于同一 Project；
- `supersedes` 两端必须属于同一 Project；
- `uses_reference` 默认同 Project；
- `uses_reference` 可以指向其他 Project 中同时为 `released + public` 的目标 DataAsset；
- 跨 Project 引用创建和每次使用时都重新检查目标仍为 `released + public`；
- 跨 Project 引用不得暴露目标 Project 的成员、私有上下文、其他资产或管理操作；
- 第一阶段不支持跨 Project 使用私有或内部资产，也不增加 `AssetProjectGrant`。

出现明确、稳定的非公开跨 Project 共享需求后，再通过独立 ADR 设计通用授权结构，不采用多 Project 共同所有或复制资产规避授权。

### 3.3 采用 `ContextEntity`，不建立万能 object

正式名称采用 `ContextEntity`。它只承载可复用的科研上下文，首批允许的类型为：

- `subject`：研究对象、材料或个体；
- `sample`：从研究对象获得或制备的样本；
- `experiment`：产生数据时的实验背景。

第一阶段不把 Project、DataAsset、DataFile、用户、分析运行或任意业务对象塞入 `ContextEntity`。

`ContextEntity` 使用少量固定字段：

| 字段 | 含义 |
| --- | --- |
| `context_code` | 仓库内稳定且唯一的编号 |
| `project` | 唯一 owning Project 和授权边界 |
| `context_type_key` | `subject`、`sample`、`experiment` 等类型 key |
| `profile_key` | 约束该上下文 metadata 的 Profile |
| `schema_version` | Profile/Schema 版本 |
| `schema_digest` | 创建时采用的完整契约摘要 |
| `name` | 人可读名称 |
| `status` | `draft`、`active`、`archived` |
| `metadata` | 经对应 Profile 严格校验的类型属性 |
| `created_by`、时间字段 | 创建者和审计时间 |

物种、组织、处理条件、采样方式等上下文属性进入 Context Profile 约束的 metadata；组装统计等资产属性进入对应 DataAsset Profile 约束的 metadata。类型特有字段不持续增加到核心表。这里的 metadata 是经过 Profile 严格定义、校验和版本固化的专业事实，不是自由 JSON，也不得与其他活动模型重复保存同一事实。

ContextEntity 第一阶段状态只采用 `draft -> active -> archived`：draft 允许缺少 Profile 必填属性但始终拒绝未知字段、非法关系和越权；active 必须通过完整 Schema 和关系校验，才可供 submitted、approved 或 released 的 DataAsset 使用；archived 只保留历史读取，不得建立新关系。被 submitted、approved 或 released 资产引用的 ContextEntity 不能普通归档，身份含义发生变化时应建立新的 ContextEntity，而不是覆盖历史事实。Context 的激活、归档和重要属性修改必须经过唯一 service 并记录审计。

新增上下文类型通常只增加 Profile 和关系规则。只有同时存在跨类型长期复用、数据库级唯一约束、独立生命周期或复杂行为，并且 Profile、真实关系表和 service 均无法安全满足时，才通过新的 ADR 评审是否提升为专门实体。专业事实不能因旧专业表退出而丢失，也不能为了兼容旧表形成第二份事实来源。

### 3.4 Profile 与 Registry 分层管理

资产 Profile 和上下文 Profile 是两类不同契约：

- 资产 Profile 定义 metadata、核心/辅助文件角色、文件数量、资产关系和上下文关系；
- 上下文 Profile 定义 metadata 和上下文之间的关系；
- 二者共用 JSON Schema 校验、版本、digest、弃用和替代机制；
- key 命名空间分离，不允许资产 Profile 与上下文 Profile 互换使用；
- Relation Registry 和 Namespace Registry 只保存声明式规则，不允许配置文件执行自定义代码。

第一阶段继续采用 Git 版本控制的注册表，不增加运行时 Profile 数据库、管理页面或动态代码执行。新增类型可以只修改注册表配置而不修改核心 model；由特权普通用户在线发布 Profile 的治理流程、审批、审计和管理界面另行设计。

Profile、Relation Registry 和 Namespace Registry 均采用稳定 key、条目级版本和条目 digest：

- key 表示稳定身份，不能在同一 key 下重新定义不兼容的核心语义；不兼容变化必须使用新 key；
- 每个条目具有显式版本和对规范化完整契约计算的 SHA-256 digest；确定性序列化方法由实现方案固定并测试；
- 已被记录引用的条目版本和完整历史规则文件不可原地修改或物理删除，只能弃用并发布新版本；
- 弃用只禁止新记录选用，不影响历史记录解释；
- Git revision 或发布包用于保留完整规则内容，digest 只验证内容身份，不能替代规则文件；
- 历史版本用于解释创建时契约，但不能绕过当前有效的授权、文件阻断和安全上限。

Relation Registry 只定义跨 Profile 的稳定语义与安全上限；具体 source/target Profile、关系基数和必需性仍由 source Profile 定义。Namespace 的格式和规范化策略必须来自受测试的声明式策略白名单，不允许配置文件执行任意代码。

### 3.5 三类关系使用 Relation Registry 与 source Profile 两层约束

Relation Registry 定义所有 Profile 共享的稳定语义和安全上限：

- relation key；
- source/target 大类；
- 方向；
- 是否禁止自关联；
- 是否必须防止间接循环；
- 跨 Project 安全策略；
- 是否要求相同或兼容 Profile family；
- 是否允许版本分支；
- 全局 incoming/outgoing 上限（如存在）。

Registry 规则不能被具体 Profile 放宽。source Profile 再决定该关系是否适用于自己、允许的目标 Profile family，以及最小/最大基数。

#### DataAssetRelation

字段至少包括：

- `source_asset`；
- `target_asset`；
- `relation_type`；
- `relation_rule_version`；
- `relation_rule_digest`；
- `created_by`、`created_at`。

首批关系：

```yaml
uses_reference:
  source_kind: data_asset
  target_kind: data_asset
  directed: true
  self_link: forbidden
  acyclic: true
  cross_project_policy: public_released_only

supersedes:
  source_kind: data_asset
  target_kind: data_asset
  directed: true
  self_link: forbidden
  acyclic: true
  cross_project_policy: same_project
  same_profile_family: true
  outgoing_max: 1
  incoming_max: 1
```

`supersedes` 方向固定为“新资产指向旧资产”，第一阶段不允许一个旧版本拥有多个相互冲突的后继版本。`derived_from` 不属于第一阶段 DataAssetRelation；真实派生必须由运行模型记录输入、输出、参数、软件版本、状态和日志。

资产 Profile 示例：

```yaml
outgoing_relations:
  uses_reference:
    allowed_target_profiles:
      - sequence/reference_genome
    min: 1
    max: 1
```

#### AssetContextLink

字段至少包括：

- `asset`；
- `context`；
- `relation_type`；
- `relation_rule_version`；
- `relation_rule_digest`；
- `position`；
- `created_by`、`created_at`。

首批关系类型：

- `source_sample`；
- `about_subject`；
- `produced_by_experiment`。

关系由 DataAsset Profile 声明允许的目标 Context Profile 和基数。保证 `(asset, context, relation_type)` 唯一，资产和上下文必须属于同一 Project。

#### ContextRelation

字段至少包括：

- `source_context`；
- `target_context`；
- `relation_type`；
- `relation_rule_version`；
- `relation_rule_digest`；
- `created_by`、`created_at`。

首批关系类型：

- Sample `collected_from` Subject；
- Sample `used_in` Experiment。

关系由 source Context Profile 声明允许的目标 Context Profile 和基数。`collected_from` 的最大数量不全局写死，以支持混合样本；具体 Sample Profile 决定 `0..1`、`1..1` 或 `1..n`。禁止自关联，并保证 `(source_context, target_context, relation_type)` 唯一，两端必须属于同一 Project。

三类关系均保存创建时采用的 Relation Registry 条目版本和 digest。联合校验所用的 Profile 契约从 source DataAsset 或 source ContextEntity 已固化的 `profile_key + schema_version + schema_digest` 还原，不在关系行复制第二份 Profile 契约。Draft 中切换 Profile 必须在同一事务中重新校验已有文件、metadata 和关系；submitted 之后不得原地切换 Profile。

数据库负责真实外键、自关联禁止和重复关系等结构不变量。唯一关系 service 负责 Registry/Profile 契约、方向、基数、跨 Project 授权、Profile family 兼容和防环。涉及基数、最后后继或防环检查时必须使用事务、适当行锁或串行化策略，并补充并发测试。

### 3.6 ExternalIdentifier 使用受控 namespace，不设置 external primary

GeneData 内部的 `project_code`、`asset_code` 和 `context_code` 始终是对象稳定主身份，不依赖任何外部编号。

`ExternalIdentifier` 保存：

| 字段 | 含义 |
| --- | --- |
| `namespace_key` | 受控 Namespace Registry key |
| `namespace_version` | 创建时采用的 Namespace 条目版本 |
| `namespace_digest` | 创建时采用的 Namespace 完整契约摘要 |
| `normalized_value` | 按 namespace 规则规范化后的唯一比较值 |
| `display_value` | 保留用于展示的原始或规范格式值 |
| `project` | 可空真实外键 |
| `asset` | 可空真实外键 |
| `context` | 可空真实外键 |
| `created_by`、时间字段 | 审计信息 |

每条记录必须且只能关联一个 Project、一个 DataAsset 或一个 ContextEntity。禁止 `GenericForeignKey`，也禁止 `related_type + related_id` 字符串多态关系。

数据库和唯一 service 至少保证：

- `project`、`asset`、`context` 恰好一个非空；
- `(namespace_key, normalized_value)` 全局唯一；
- namespace、`display_value` 和 `normalized_value` 非空；
- namespace 允许关联当前目标类型；
- namespace 的大小写、格式和规范化规则得到执行；
- 三个目标外键使用 `PROTECT`，对象删除前必须显式处理其外部编号，不能静默级联丢失标识事实。

Namespace Registry 至少声明：

- namespace key 和名称；
- 本地标识正则或校验规则；
- 大小写和规范化规则；
- resolver URL 模板；
- 允许的目标 kind，以及必要时允许的 Context/Profile family；
- 弃用和替代信息；
- 条目版本、digest 和历史定义位置。

影响身份等价性的核心规范化语义在同一 namespace key 下冻结。不兼容修改必须先进行碰撞审计，并通过独立决策采用新 key 或受控迁移；不能把 `namespace_version` 加入唯一键形成彼此隔离的唯一空间，也不能静默重写历史 `normalized_value`。

第一阶段不增加 `is_primary`、`primary_slot` 或 `is_preferred`。如果界面以后确实需要优先展示某个外部编号，再根据真实场景独立增加“preferred display identifier”，不能让外部编号取代内部稳定身份。

示例归属：

| 外部编号 | GeneData 目标 |
| --- | --- |
| BioProject | `Project` |
| BioSample | `sample` ContextEntity |
| Assembly accession | Reference Genome DataAsset |
| SRA Run | Raw Reads DataAsset |
| DOI | 仅在 DOI 确实标识单一 DataAsset 时关联该资产；否则等待相应目标实体设计，不强行登记 |

如果旧 `Accession` 实际表达的是材料、品系或研究对象，其对象事实在新仓重新登记为 `subject` ContextEntity，编号部分登记为 ExternalIdentifier；不把旧表原样复制进新仓。

### 3.7 Assembly 和 Annotation 作为资产，Sample 作为上下文

新仓按实际职责处理旧专业实体：

| 旧实体 | 新仓目标 |
| --- | --- |
| `Assembly` | 有参考序列核心文件时使用 Reference Genome `DataAsset` 表达；组装统计进入资产 metadata |
| `Annotation` | 有 GFF/GTF 等核心文件时使用 Annotation `DataAsset` 表达；通过 `uses_reference` 指向参考基因组资产 |
| `Sample` | 使用 `sample` ContextEntity 表达 |
| `Accession` | 对象事实进入适当 ContextEntity，外部编号进入 ExternalIdentifier |

因此，目标 schema 不保留 `DataAssetAccession`、`DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` 四张固定专业关系表，也不把旧 Accession、Sample、Assembly、Annotation 作为新仓活动事实来源。

目标退出候选及替代结构为：

| 退出候选 | 目标替代 |
| --- | --- |
| `DataAssetAccession`、`DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation` | `ExternalIdentifier`、`AssetContextLink`、`DataAssetRelation` |
| `Accession`、`AccessionExternalMapping` | `ContextEntity` 中的对象事实和 `ExternalIdentifier` 中的外部编号 |
| `Sample` | `sample` ContextEntity |
| `Assembly` | Reference Genome DataAsset |
| `Annotation` | Annotation DataAsset |

该清单只批准目标职责，不授权立即删表。每个候选都必须在 G5 删除附录中列出当前调用者、替代模型、API/前端与 JBrowse/索引影响、测试、正向 migration 和回滚边界；替代模型、唯一 service、权限和全部调用完成切换后，才能逐项审批删除。历史 migration 永久保留。

`AnnotationFeatureIndex` 和 `AnnotationFeature` 不因本 ADR 自动删除。`AnnotationFeatureIndex` 的目标来源是 Annotation DataAsset 及其明确的核心 DataFile，不再以旧 Annotation 表作为事实来源；具体字段和 migration 在对应实施任务中单独评审。

### 3.8 ProjectMembership 与第一阶段用户权限

新增 `ProjectMembership`，至少包含：

- `project` 真实外键；
- `user` 真实外键；
- `role`：`owner`、`manager`、`contributor`、`viewer`；
- `created_by`、`created_at`、`updated_at`。

保证 `(project, user)` 唯一。Project 创建者必须通过唯一 service 同时成为 owner；移除最后一个 owner 必须被 service 拒绝并在事务中锁定相关成员记录。现有 `Project.owner` 字符串不能继续作为授权依据，待调用切换后由正向 migration 删除。

第一阶段权限矩阵：

| 操作 | owner | manager | contributor | viewer | 匿名 |
| --- | --- | --- | --- | --- | --- |
| 查看 Project 基本信息 | 是 | 是 | 是 | 是 | 否 |
| 查看 `lab_internal` 资产 | 是 | 是 | 是 | 是 | 否 |
| 查看自己创建的 `private` 资产 | 是 | 是 | 是 | 是 | 否 |
| 查看他人创建的 `private` 资产 | 是 | 是 | 否 | 否 | 否 |
| 查看 `released + public` 资产 | 是 | 是 | 是 | 是 | 是 |
| 创建资产/上下文 | 是 | 是 | 是 | 否 | 否 |
| 编辑自己创建的 draft | 是 | 是 | 是 | 否 | 否 |
| 编辑他人 draft | 是 | 是 | 否 | 否 | 否 |
| 激活或归档 ContextEntity | 是 | 是 | 否 | 否 | 否 |
| 提交审核 | 是 | 是 | 是 | 否 | 否 |
| 批准或退回 | 是 | 是 | 否 | 否 | 否 |
| 发布或归档 | 是 | 否 | 否 | 否 | 否 |
| 管理非 owner 成员 | 是 | 是 | 否 | 否 | 否 |
| 授予、降级或移除 owner | 是 | 否 | 否 | 否 | 否 |

补充规则：

- contributor 不能批准内容；
- manager 和 owner 的批准、退回、自批准操作以及 owner 的发布、归档操作必须记录审计信息；第一阶段允许单 owner 启动场景，不强制双人审批；
- manager 不得授予、降级或移除 owner；
- 最后一个 owner 不可移除；
- 第一阶段不增加对象级 ACL。

DataAsset 可见性规则：

- `private`：创建者、owner 和 manager；创建者角色后来降为 viewer 时仍可读取自己创建的 private 资产，但不能继续编辑；
- `lab_internal`：owning Project 全体成员；
- `public`：只有 `released` 后才允许匿名读取；
- visibility 为 public 但尚未 released 时按 private 规则读取，不能提前公开；
- archived 不允许匿名读取，Project 内仍按其 private/lab_internal 规则读取；未明确授权时拒绝，归档不自动扩大访问权限。

#### DataAsset 状态转换与校验时机

第一阶段状态机固定为：

```text
draft --提交--> submitted
submitted --退回--> draft
submitted --批准--> approved
approved --撤回审批--> draft
approved --发布--> released
released --归档--> archived
```

禁止跳过中间状态。submitted 和 approved 的内容冻结；owner 或 manager 记录原因并退回/撤回至 draft 后才能修改，任何影响已批准内容的修改都必须先使审批失效。released 的核心文件、关键 metadata、Profile 和稳定关系不得原地覆盖，重大变更创建新的 DataAsset 版本并通过 `supersedes` 关联。第一阶段不支持 archived 原地恢复；需要重新发布时创建新版本。

采用“允许 Draft 不完整，不允许 Draft 不合法”的分层校验：

- 创建或编辑 draft 时立即检查已填写 metadata、Registry/Profile 存在性、关系类型和方向、最大基数、唯一性、自关联、防环、目标类型、外部编号格式和权限；允许暂缺必填 metadata、核心文件和最小数量关系；
- 提交时检查必填 metadata、核心文件及最小数量、必需上下文/关系、文件存在性和 checksum、文件可用状态及当前授权；失败时保持 draft；
- 批准时重新校验完整性和审批权限并记录审计；
- 发布时在事务内重新读取并校验全部文件、关系、跨 Project 目标、公开字段和权限，状态变化与审计记录一致提交，不依赖缓存或更早阶段的校验结果；
- 并发编辑、审批和发布必须使用适当行锁或乐观版本校验，不能让失效检查结果进入 released。

同 Project `uses_reference` 在 draft 编辑时可以暂时指向有权读取的 draft 目标，但 source 提交时目标必须至少为 approved，source 发布时目标必须为 released。跨 Project 目标从创建关系开始，在提交、批准、发布和实际使用时都必须为 `released + public`。

当存在 source 状态为 submitted、approved 或 released 的 `uses_reference` 依赖时，普通流程必须拒绝归档目标；跨 Project 目标还不得转为非 public。先退回或归档依赖资产、替换参考并重新审批后，才能处理目标。Draft 中失效的引用可以删除或替换，但不能提交。紧急安全或合规事件可通过 DataFile 的全局阻断状态立即拒绝文件访问并保留关系和审计证据；本 ADR 不新增含义不明的“特别授权人员”角色。

### 3.9 Context Profile 明确公开字段，默认不公开 metadata

ContextEntity 第一阶段不单独设置 visibility，完整上下文读取需要 owning Project 成员权限。

Context Profile 可以声明最小公开字段：

```yaml
public_metadata_fields:
  - scientific_name
  - tissue
```

规则：

- 默认空列表；
- 只有 Schema 中存在且明确列出的字段可以随 `released + public` 资产返回；
- `context_code`、内部描述、创建者、审计字段、未声明 metadata 和其他关联资产默认不公开；
- 公开资产不能使同一 ContextEntity 的全部 metadata 或其他关系自动公开；
- public metadata 校验和序列化必须复用同一 Profile 契约。

### 3.10 DataFile 继续存在，但不再拥有独立资产发布生命周期

DataFile 继续保存：

- 稳定文件编号和文件名；
- 文件大小和校验值；
- 受控存储位置；
- 物理存在、完整性和 current 状态；
- 只会拒绝访问的物理可用状态 `available`、`quarantined`、`blocked`、`missing`。

DataFile 不保存或决定：

- Project 所有权；
- 科研数据类型和科研上下文；
- 文件在资产中的角色；
- 独立于 DataAsset 的业务发布状态。

目标权限规则：

- `DataAsset.status + DataAsset.visibility` 是资产发布和可见性的唯一事实来源；
- 文件必须在具体 DataAsset membership 下授权；
- DataFile 的物理可用状态只能拒绝访问，不能授予访问或表达 Project 范围；
- 当前 `DataFile.publication_status`、`published_at`、`published_by` 在调用切换后通过独立正向 migration 退出；
- 当前 `DataFile.access_level` 在权限重构后退出，不保留无法确定所属 Project 的 `internal/private` 语义；未来如需合规分类或对象级文件授权，必须通过独立 ADR 设计。

通过资产访问文件时，必须校验指定资产、membership 和 DataFile 物理可用状态。直接按 file code 访问时，必须先找到调用者可见的 membership；没有可见 membership 就拒绝，不能只根据 DataFile 放行，也不能泄露不可见资产信息。一个公开资产可以公开其获准成员文件内容，但响应不得暴露同一 DataFile 的私有资产关系或服务器绝对路径。

当前委托 Dataset 权限的 `datafile_access_service` 必须在删除 Dataset 前被唯一新授权路径替换。

### 3.11 DataAccessToken 延后设计

第一阶段只对经过 Django 认证的真实用户执行 ProjectMembership、DataAsset 和文件授权。

DataAccessToken、服务账号、API scope、机器访问和凭证审计由 G7 前的独立 ADR 设计。当前 `DataAccessToken` 的 scope、access tier 和 `created_by` 不视为新仓正式授权方案，也不得在本 ADR 中继续扩展。

G5 不验证 Token；G6 使用真实测试用户验证最小权限流程；新的机器文件访问接口必须等待 Token ADR 批准。旧 Token 和旧外部 API 的保留或删除根据 G4 调用面在对应切换阶段独立处理。

### 3.12 插件通过能力契约使用资产

JBrowse、分析工具和未来插件不得通过任意 metadata 字段或硬编码数据类型猜测资产是否可用。插件能力契约至少声明：

- 支持的资产 Profile；
- 必需的核心文件角色；
- 必需的资产关系或上下文关系；
- 必需的已校验 metadata；
- 所需用户权限和文件访问方式。

不在 metadata 中加入 `jbrowse_enabled` 等页面专用开关。插件生成且具有独立复用价值的长期结果可以形成新的 DataAsset；缓存、索引副本和临时配置不自动成为资产。

## 4. 明确不采用的方案

### 4.1 不保留每种专业对象一张 DataAsset 中间表

该方式外键清晰，但新增稳定上下文类型仍需新增 model、migration、service 分支和测试，不符合通用仓库扩展目标。

### 4.2 不把所有内容放入 DataAsset.metadata

metadata 适合类型属性，不适合可复用对象、外部唯一标识、稳定关系、权限边界和真实血缘。全部放入 JSON 会削弱反向查询、唯一性、插件判定和一致更新。

### 4.3 不使用 GenericForeignKey 或字符串多态关系

核心关系必须使用真实外键和数据库约束，不能使用 `target_type + target_id` 形成无法保证引用完整性的万能关系。

### 4.4 不把 ContextEntity 扩展成 openBIS 式万能 object

GeneData 的主身份仍是 DataAsset。ContextEntity 不接管文件、资产、Project、用户、权限或分析运行。

### 4.5 不使用多 Project 共同所有

每个 DataAsset 和 ContextEntity 只有一个 owning Project。跨 Project 使用不改变所有权；第一阶段只允许受控的公开参考资产引用。

### 4.6 不长期保留新旧双体系

ADR-005 批准后采用“新增替代结构、切换唯一 service、清除旧调用、正向删除”的单向过程，不建立长期双读、双写或旧关系 fallback。

## 5. 影响

### 5.1 正面影响

- 新数据类型和常见上下文类型不再要求持续增加核心表；
- 样本、研究对象、实验、外部编号和资产依赖可以明确查询；
- 公共参考基因组可被不同 Project 复用，不需要复制资产；
- Assembly/Annotation 的文件、版本、权限和工具能力统一进入 DataAsset；
- Project 权限从字符串 owner 升级为真实用户成员关系；
- 外部编号按其真实对象层级登记，不把 BioProject、BioSample 和 Assembly 混为同一资产编号；
- JBrowse 和分析工具可以依赖稳定能力契约，而不是猜测文件名或 metadata；
- 新仓空库可以删除不再承担目标职责的旧业务表。

### 5.2 代价与风险

- 通用关系类型需要严格 Registry 和唯一 service，否则会退化成任意关系字符串；
- JSON Schema、Relation 和 Namespace 规则需要条目级版本、digest 和历史规则留存；已经被引用的版本不能原地修改；
- Namespace 规范化规则的不兼容变化可能产生跨版本唯一性碰撞，必须先审计再迁移或启用新 key；
- Project 授权、文件授权、跨 Project 引用和公开上下文字段需要安全测试；
- 防环、基数、最后 owner、提交和发布存在并发风险，需要事务、锁或版本校验及并发测试；
- 旧 JBrowse、API、页面和命令不能直接复用，必须分阶段切换；
- MySQL 对部分条件唯一和 CheckConstraint 的行为必须用目标版本实际验证；
- Token、非公开跨 Project 共享和真实分析运行血缘仍需后续独立决策。

## 6. 实施顺序与独立提交边界

本 ADR 只有在批准后才能进入本地开发实施，顺序为：

1. **注册规则与状态机**：固定 Namespace Registry、Relation Registry、首批资产/Context Profile、条目版本/digest、公开字段契约、DataAsset 状态转换和校验时机，不改现有业务入口；
2. **Project 用户权限**：新增 `ProjectMembership`、约束、唯一 Project service 和模型/并发测试；
3. **通用上下文与外部标识**：新增 `ContextEntity`、三类关系、`ExternalIdentifier` 及约束测试；
4. **唯一创建、关系和状态转换 service**：实现 Context、ExternalIdentifier、关系、DataAsset 分层校验、审批和发布；
5. **DataAsset/DataFile 授权收敛**：建立基于真实用户、ProjectMembership、资产 membership 和 DataFile 物理阻断状态的 fail-closed 权限；
6. **保留能力切换**：重构 JBrowse、索引、导入和查询，使其不再依赖 Dataset/FileRelation/旧专业实体；
7. **旧入口清除**：删除或停用旧命令、API 路由和前端入口，使应用在旧表不存在时仍可启动；
8. **删除附录与正向 migration**：先逐项完成退出候选的调用者、替代结构、测试和回滚清单，再按独立审批退出 `DataFile.dataset`、`DatasetAccession`、`FileRelation`、`Dataset`、四张固定专业关系表、经附录批准的旧专业实体和重复的 DataFile 权限/发布字段；
9. **G5 空库验证**：在新的空 MySQL 执行完整 migration 链、系统检查、最终表清单和测试；
10. **G6 最小后端流程**：从零创建用户、Project、成员、Profile、Context、DataAsset 和文件成员并验证授权；
11. **G7 API 与前端**：设计资产搜索、详情、文件成员、上下文、外部标识和管理流程；机器访问前另行批准 Token ADR。

每一步独立提交。不得把模型、权限、API、前端和破坏性 migration 合成一次跨层修改。

ADR-004 的 G2 隔离恢复和 G3 旧服务离线状态仍需单独完成；批准本文不代表生产部署、旧表删除或真实数据验收完成。

## 7. 验收标准

ADR-005 实施完成至少需要证明：

1. 新增资产或上下文 Profile 不需要增加核心 Django model 或类型分支；
2. Draft 可以缺少必填 metadata、核心文件和最小数量关系，但未声明字段、未知关系、错误方向、超出最大基数、重复、自关联、成环和越权始终被拒绝；
3. ContextEntity 只接受批准类型和版本化 Profile；draft/active/archived 转换、完整性、被活动资产引用时的归档保护和审计规则通过；
4. ExternalIdentifier 恰好关联一个 Project、DataAsset 或 ContextEntity；
5. namespace/value 被正确规范化，`(namespace_key, normalized_value)` 跨版本唯一，三个目标外键使用 `PROTECT`，第一阶段没有 external primary；
6. 所有核心关系使用真实外键，不存在新 GenericForeignKey 或字符串多态关系；
7. `AssetContextLink`、`ContextRelation` 和 `supersedes` 的跨 Project 写入均被拒绝；
8. 同 Project `uses_reference` 在 source 提交时目标至少 approved、发布时目标必须 released；跨 Project 目标始终为 `released + public`，并在创建、提交、批准、发布和使用时重新授权；
9. `uses_reference` 和 `supersedes` 无自关联和间接循环，`supersedes` 第一阶段无分支；
10. 三类关系和 ExternalIdentifier 均可定位到创建时采用的 Registry/Namespace 版本、digest 和完整历史规则；
11. 已被引用的规则版本不能原地修改；不兼容语义使用新 key，弃用不破坏历史可读性；
12. Project 创建者成为 owner，最后一个 owner 不能被并发移除；
13. owner、manager、contributor、viewer、匿名用户的项目基本信息、own private、other private、lab_internal、未 released 的 public 和 released/public 权限矩阵通过；
14. draft、submitted、approved、released、archived 只能按批准路径转换；approved 内容修改前必须审计撤回至 draft，released 不原地修改，archived 第一阶段不原地恢复；
15. 提交检查完整性，批准和发布重新检查；并发修改不能使不完整或失效资产进入 released；
16. 存在 submitted、approved 或 released 的 `uses_reference` 依赖时不能普通归档参考目标；跨 Project 目标还不能转为非 public；紧急物理阻断保留关系和审计证据；
17. 公开资产只返回 Context Profile 明确声明的公开字段；
18. 文件访问逐资产、逐 membership、逐 DataFile 物理状态授权，不泄露绝对路径或不可见关系；
19. DataFile 不使用无所属边界的 internal/private 授权，不再拥有独立业务发布状态，物理状态只能拒绝访问；
20. Reference Genome 与 Annotation 可以只通过 DataAsset、文件成员、资产关系和 ExternalIdentifier 表达；
21. Sample、Subject、Experiment 可以通过 ContextEntity 表达且支持反向查询；
22. JBrowse 通过 Annotation DataAsset、核心文件和 `uses_reference` 工作，不依赖旧 Annotation/FileRelation；
23. G5 删除附录逐项证明每个退出候选已有替代结构、调用切换、测试和回滚边界；`AnnotationFeatureIndex` 和 `AnnotationFeature` 未被本 ADR 误删；
24. 最终 model 和空库 schema 不含 Dataset、DatasetAccession、FileRelation、固定四张专业关系表及删除附录批准退出的旧专业实体；
25. 历史 migration 保留，完整 migration 链可从零执行；
26. API 和前端不存在长期双读、双写或旧关系 fallback；
27. Registry、互斥目标外键、ExternalIdentifier 唯一性和并发状态转换在目标 MySQL 真实验证；
28. 未把现有 DataAccessToken 描述为已完成的新仓授权方案。

## 8. 后续独立决策

以下事项不阻塞本文核心模型评审，但不得描述为已实现：

- Profile 由特权普通用户在线创建、审批、发布和停用的治理流程与管理界面；
- DataAccessToken、服务账号、API scope、机器访问和凭证审计；
- 私有或内部 DataAsset 的跨 Project 授权；
- DataType/Profile 搜索索引和动态表单；
- 组织或课题组的多层级模型；
- 对象级自定义 ACL；
- AnalysisRun/ProcessingRun 的真实血缘模型；
- API URL、serializer 和前端页面布局；
- 旧数据库隔离恢复验证及旧服务停止时间。

## 9. 与现有决策的关系

- 延续 ADR-001 的 DataAsset 统一身份方向；
- 延续 ADR-002 的 DataAsset、AssetFileMembership 和最小创建服务原则；
- 本文替代 ADR-001 第 3 节固定专业实体作为可选扩展的目标表达，以及 ADR-002 第 3 节 `DataAssetAccession` 的目标关系方案；
- 保留 ADR-003 的真实核心载荷、Profile 文件规则和核心/辅助文件边界；
- 本文替代 ADR-003 中固定四类专业上下文关系和专业实体直接关联方案；
- 延续 ADR-004 的新仓空业务库、旧业务关系不迁移和正向删除 migration 原则；
- 使用 G4 代码审计和调用面处置清单作为退出顺序证据，不把审计清单本身当作删除授权。

本文批准时已同步修订仓库级 `AGENTS.md` 第 3.1 节：专业事实由受版本化 Profile 约束的 DataAsset、ContextEntity 或经独立 ADR 批准的专门实体承载，不得丢失或重复保存。旧 Assembly、Annotation、Sample、Accession 及固定关系表在调用切换和独立正向删除 migration 完成前仍是当前实现的一部分，但不再是新仓目标事实模型。

## 10. 批准记录与后续 Gate

2026-11-26 再次评审确认：owning Project、受控公共跨 Project `uses_reference`、ContextEntity、Registry/Profile 分层、ExternalIdentifier、ProjectMembership、状态转换、DataFile 权限收敛、专业实体退出目标和分阶段顺序形成闭环，批准本文为 active 决策。

批准时同步完成：

- 将本文 `status` 改为 `active`；
- 更新 `docs/ACTIVE_DOCUMENTS.md`；
- 修订仓库级 `AGENTS.md` 中 DataAsset 当前实现状态和固定专业实体规则；
- 在 ADR-001、ADR-002 增加被 ADR-005 修订的说明，不改写历史正文；
- 在 ADR-003 增加被 ADR-005 修订的说明，不改写历史正文；
- 修订重新定位说明中的固定专业实体和目标 schema 描述。

批准本文只允许进入第 6 节的分阶段本地实施，不授权跨阶段重写、破坏性生产操作或删除现有活动表。以下 Gate 仍未完成：

1. ADR-004 G2 隔离恢复和 G3 旧服务离线验收；
2. Registry、状态机、ProjectMembership、ContextEntity、关系和 ExternalIdentifier 的实施方案与代码；
3. DataAsset/DataFile 唯一授权路径及真实 MySQL 测试；
4. JBrowse、索引、API、前端和旧调用切换；
5. G5 删除附录和逐项正向删除 migration 审批；
6. G5 空库、G6 最小后端流程、G7 API/前端及独立 Token ADR；
7. 生产 migration、部署和真实数据验收。
