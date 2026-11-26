---
title: GeneData ADR-005 第一阶段：新核心基础实施方案
status: active
owner: 徐杨珂
last_reviewed: 2026-11-26
supersedes: null
---

# GeneData ADR-005 第一阶段：新核心基础实施方案

## 1. 文档状态与依据

本文把已批准的 [ADR-005](../adr/ADR-005-dataasset-context-identifiers-and-project-authorization.md) 第一阶段拆成可评审、可测试、可独立提交的实施 Gate。本文于 2026-11-26 正式批准为 `active`，是阶段一实施依据；批准本文不表示相关 model、migration、service、生产部署或真实数据验收已经完成。

权威依据按以下顺序执行：

1. 仓库根目录 `AGENTS.md`；
2. `docs/ACTIVE_DOCUMENTS.md` 中的 active 决策；
3. ADR-004 的空库启用边界；
4. ADR-005 的目标结构、授权规则和四阶段边界；
5. 当前代码、migration、测试和 CI 所证明的实现事实。

本文只规划 ADR-005 阶段一，不改变阶段二至阶段四的职责。

## 2. 四阶段边界复审结论

ADR-005 当前四阶段划分可以执行，依赖方向和完成标准清楚：

| 阶段 | 负责内容 | 明确不负责 | 完成判断 |
| --- | --- | --- | --- |
| 一：新核心基础 | Registry、状态机、ProjectMembership、通用上下文、通用关系、外部标识和唯一写入 service | 不切换旧 API、页面、JBrowse、导入和文件授权；不删旧表 | 新结构与 service 在开发环境和目标 MySQL 通过结构、规则、状态和并发测试 |
| 二：权限与保留能力切换 | 新 DataAsset/DataFile 授权路径，以及 JBrowse、索引、导入和查询切换 | 不做破坏性删表 | 已切换能力不再读取旧关系或 fallback，旧表仍保留 |
| 三：旧结构退出与空库验收 | 清除旧入口、逐项审批删除、空 MySQL migration、最小后端流程 | 不把多个破坏性删除合成一次操作 | 最终 schema、model 和调用一致，G5/G6 证据完整 |
| 四：API 与前端建设 | 面向用户的新 API、页面和管理流程 | 不顺带沿用未批准的 Token 方案 | API/前端只使用新仓身份、关系和授权路径 |

复审确认的关键边界：

- 阶段一只建立可独立验证的新核心，不把“代码已经存在”描述为业务已经切换；
- 阶段二先切换调用和授权，阶段三才逐项删除，避免边切换边删表；
- 阶段三中的每个破坏性 migration 仍需单独审批、备份和回滚边界；
- 阶段四开始前另行决定机器访问、服务账号、scope 和 Token，不进入本方案；
- 前端目标在阶段四实现，但阶段一的字段、状态和错误语义必须保持可形成稳定 API，避免后续重新改模型。

因此不建议再合并四个阶段，也不建议把阶段一拆回多个对外汇报阶段。阶段一内部使用四个 Gate 控制风险即可。

## 3. 当前实现基线

### 3.1 已实现且可复用

当前开发代码已经包含：

- `DataAsset`、`AssetFileMembership` 和 `DataFile`；
- `DataAsset` 的 `draft/submitted/approved/released/archived` 状态字段，但尚无完整状态转换 service；
- Git 管理的 `data_asset_registry/registry.json`；
- `data_asset_registry_service.py` 中的 Profile 加载、JSON Schema 校验、基数校验和 SHA-256 digest；
- `data_asset_service.py` 中的原子化资产创建；
- migration `0026` 和 `0027` 建立的 DataAsset 基础及四张固定专业关系表；
- DataAsset model、Registry、创建 service 和旧访问 service 的单元测试；
- CI 使用 MySQL 8.0 执行 Django 检查、migration 漂移检查和 `files` 测试。

阶段一必须扩展这些所有者实现，不创建 `*_v2`、`*_new` 或平行 Registry/service。

### 3.2 尚未实现

当前代码尚未证明以下能力：

- `ProjectMembership` 和基于真实用户的项目角色；
- Project 创建者自动成为 owner，以及并发条件下最后 owner 保护；
- `ContextEntity` 及其 Profile、状态转换和公开字段契约；
- `DataAssetRelation`、`AssetContextLink`、`ContextRelation`；
- `ExternalIdentifier`、Namespace Registry 和规范化策略；
- Relation Registry；
- DataAsset 的提交、批准、退回、发布和归档 service；
- 防环、跨 Project 引用、冻结和并发状态转换；
- 能持久保存审批、发布、归档、成员变更及原因的审计结构。

### 3.3 当前遗留但阶段一不删除

以下仍是当前实现的一部分，阶段一不删除、不回填、不双写：

- `Dataset`、`DatasetAccession`、`FileRelation`；
- `DataAssetAccession`、`DataAssetSample`、`DataAssetAssembly`、`DataAssetAnnotation`；
- 旧 `Accession`、`Sample`、`Assembly`、`Annotation`；
- 依赖上述结构的 API、页面、JBrowse、索引、导入、查询和权限代码；
- `Project.owner` 字符串；
- 当前 `DataFile` 的访问及发布字段。

这些结构在阶段一仍可服务旧入口，但不得成为新核心 service 的写入目标。新旧结构之间不建立同步、fallback 或自动转换。

## 4. 阶段一目标与非目标

### 4.1 目标

阶段一完成后应具备一个尚未接入正式业务入口、但可以从 service 层完整验证的新仓核心：

1. Project 由真实用户成员和角色管理；
2. 资产、上下文、外部编号和三类关系使用真实外键表达；
3. Profile、Relation 和 Namespace 规则均版本化并可校验历史 digest；
4. Draft 可以不完整，但不能包含非法字段、关系、编号或越权写入；
5. 提交、批准和发布按不同强度重新校验；
6. 状态转换、基数、防环、最后 owner 和发布在并发条件下保持不变量；
7. 所有写入通过唯一 service，不允许调用者直接拼接规则；
8. 通过开发环境测试和 CI 的 MySQL 8.0 验证。

### 4.2 非目标

阶段一明确不实施：

- 新 API、serializer、URL、前端页面和动态表单；
- 旧 API、JBrowse、导入、索引或查询切换；
- 文件内容下载和逐文件授权重构；
- Token、服务账号、机器访问或对象级 ACL；
- 私有或内部资产的跨 Project 共享；
- Profile 在线创建、审批和发布后台；
- AnalysisRun/ProcessingRun 血缘；
- 旧数据迁移、历史关系修复或生产回填；
- 任何旧 model、字段、路由或 migration 的删除；
- 生产部署、生产 migration 或真实数据验收。

## 5. 总体实施原则

### 5.1 只保留一个新核心写入路径

- `data_asset_registry_service.py` 继续作为注册规则的唯一加载和校验边界；
- `data_asset_service.py` 继续作为 DataAsset 写入和状态转换的所有者；
- Project、Context、ExternalIdentifier 和关系只有在职责独立且代码规模需要时才新增有明确边界的 service；
- model 的 `save()`、signal、serializer 或 management command 不复制业务校验；
- 测试和以后 API 只调用 service，不把 service 规则再写一遍。

### 5.2 新结构与旧入口隔离

阶段一允许数据库中同时存在旧表和新增表，但只允许以下过渡形态：

- 旧业务入口继续使用旧结构；
- 阶段一测试通过新 service 创建全新的测试记录；
- 新 service 不写 `Dataset`、`FileRelation` 或四张固定专业关系表；
- 旧 service 不写 `ContextEntity`、三类新关系或 `ExternalIdentifier`；
- 不提供“读新失败就读旧”或“同时写两边”的兼容逻辑。

这不是长期双事实来源，而是尚未切换入口的隔离开发阶段。阶段二负责切换，阶段三负责退出旧结构。

### 5.3 数据库约束与 service 约束分工

数据库负责：

- 真实外键和删除策略；
- 非空、固定选择值和恰好一个目标外键；
- 直接重复、自关联和可由单行或唯一键保证的不变量；
- `(project, user)`、外部编号、关系等唯一性。

service 负责：

- Registry/Profile 兼容；
- 角色和状态权限；
- 基数、防环、跨 Project 规则和 Profile family；
- 分层完整性校验；
- 需要事务、锁或重试的并发不变量；
- 审计记录与状态变更原子提交。

## 6. Gate A：注册规则与状态机

### 6.1 实施范围

在现有 Registry 所有者实现上增加三类注册内容：

1. **资产 Profile**：继续定义资产 metadata、文件角色，并增加允许的资产关系、上下文关系和公开契约；
2. **Context Profile**：定义 `subject`、`sample`、`experiment` 的 metadata、公开字段和允许的上下文关系；
3. **Relation Registry 与 Namespace Registry**：定义稳定关系语义、方向、安全上限、跨 Project 策略，以及外部编号格式和规范化策略。

建议保持 Git 管理的声明式 JSON 文件，并按职责拆分为同一目录中的明确文件，例如：

```text
django2/files/data_asset_registry/
├── asset_profiles.json
├── context_profiles.json
├── relation_registry.json
└── namespace_registry.json
```

是否从当前 `registry.json` 改名或拆分，实施时只能通过一次受测试的替换完成；不得同时保留两个可被运行时加载的资产 Profile 来源。

### 6.2 固定规则

- 所有 key 使用稳定的小写 key；不兼容语义必须使用新 key；
- 每个条目包含显式版本、弃用状态和替代项；
- digest 对规范化后的完整条目计算 SHA-256；
- 规范化序列化固定为 UTF-8、JSON key 排序和稳定分隔符，并以测试锁定；
- 已被记录使用的同 key/版本不得换 digest；
- 配置只能选择实现中经过测试的规范化策略，不允许执行动态 Python 或表达式；
- 资产 Profile 和 Context Profile 的 key 空间和加载方法分离；
- Relation Registry 只能收紧全局安全规则，source Profile 不能放宽；
- Context 的 `public_metadata_fields` 默认空，并且只能引用 Schema 中已声明字段。

当前实现中的固定 `DATA_TYPE_KEYS` 和旧 `CONTEXT_TYPES` 必须在 Gate A 退出：

- `data_type_key` 只校验稳定 key 格式，并从已加载的资产 Profile 得出可用类型，不能继续由 Python 固定枚举限制；
- `context_type_key` 从 Context Profile 得出，首批仅注册 `subject`、`sample`、`experiment`，以后新增批准类型不修改 Django model 或 Python 类型分支；
- 关系类型从 Relation Registry 得出，不在 service 中重复维护第二份允许列表；
- 固定状态机、目标大类和受测试的规范化策略白名单仍可由代码实现，因为它们属于安全边界，不属于可任意扩展的数据类型。

首批关系和类型严格限于 ADR-005 已批准内容：

- Context 类型：`subject`、`sample`、`experiment`；
- DataAssetRelation：`uses_reference`、`supersedes`；
- AssetContextLink：`source_sample`、`about_subject`、`produced_by_experiment`；
- ContextRelation：`collected_from`、`used_in`；
- 不增加 `derived_from`、自定义关系脚本或任意 object 类型。

### 6.3 当前版本与历史版本解析

Registry 必须同时支持“新记录选择当前版本”和“历史记录按原契约解释”，不能继续只按 `(data_type_key, profile_key)` 保存一个条目：

- 资产 Profile 的历史身份采用 `(data_type_key, profile_key, schema_version, schema_digest)`；
- Context Profile 的历史身份采用 `(context_type_key, profile_key, schema_version, schema_digest)`；
- Relation 和 Namespace 历史身份采用 `(key, version, digest)`；
- 同一个 key 可以保留多个历史版本，但同一 key/version 只能对应一个 digest；
- 每类 Registry 具有唯一的当前版本指针；弃用版本不能再作为新记录默认值；
- `resolve_current_*()` 只供创建新记录；
- `resolve_exact_*(key, version, digest)` 只按持久化身份解析历史契约，digest 不匹配时安全失败；
- 运行时加载包必须同时包含当前指针和全部仍被记录引用的历史条目；Git revision 或发布包继续作为完整内容的留存证据。

现有 `registry.json` 中已经出现的 Profile 定义和 `2.0.0` 契约不得原地改写。移除 metadata 中的外部编号、旧 `assembly/sample/annotation` 固定上下文规则时，必须发布新的 Profile 主版本，并保留旧版本供已有开发记录解释。文件拆分后只能有一个运行时加载入口，旧 `registry.json` 不得继续作为第二个活动来源。

拆分文件和升级加载器时，旧 `2.0.0` 完整契约的 canonical 内容与已计算 digest 必须保持不变，并使用固定 digest fixture 测试；不能因为文件位置、外层目录结构或新增当前版本指针而改变历史条目的内容身份。

### 6.4 状态机契约

Gate A 先用纯规则和测试固定状态路径，实际数据库转换由 Gate D 完成：

```text
DataAsset: draft -> submitted -> approved -> released -> archived
                         |           |
                         +-> draft <-+

ContextEntity: draft -> active -> archived
```

必须明确每个动作的允许来源状态、操作者角色、校验强度、冻结范围和失败后状态。未知动作和跳级转换默认拒绝。

### 6.5 验证与完成标准

- Registry 未知字段、重复 key/版本、无效 Schema、非法规则和未知策略均安全失败；
- 完整契约变化必然改变 digest，输入 key 顺序变化不改变 digest；
- 资产 Profile 与 Context Profile 不可互换；
- source Profile 无法放宽 Relation Registry 的自关联、防环或跨项目上限；
- Namespace 规范化和格式校验有正反用例及碰撞用例；
- 当前版本选择、精确历史解析、未知版本和 digest 冲突测试通过；
- 旧 Profile 的历史解析测试继续通过，新建记录不会继续选用已弃用版本；
- 新增资产或 Context 类型只增加 Registry 条目和测试数据，不修改 model 或 Python 类型枚举；
- 不产生 model、migration、API 或前端变化。

Gate A 应形成独立提交。

## 7. Gate B：Project 用户权限基础

### 7.1 模型

新增 `ProjectMembership`：

| 字段 | 约束 |
| --- | --- |
| `project` | `Project` 真实外键；成员行可随一个经过批准的 Project 物理删除而 `CASCADE`，但阶段一 Project service 不提供物理删除 |
| `user` | `AUTH_USER_MODEL` 真实外键，使用 `PROTECT`，避免静默丢失成员和审计事实 |
| `role` | `owner/manager/contributor/viewer` |
| `created_by` | 可空用户外键，`SET_NULL` |
| `created_at/updated_at` | 审计时间 |

数据库保证 `(project, user)` 唯一、角色非空且属于批准集合。阶段一采用以下删除策略：

- 用户通过 Django `is_active=False` 停用；阶段一不新定义 Project 生命周期状态，也不物理删除 Project；
- 新核心 service 不提供 Project 或用户物理删除入口；Project 后续停用/归档语义如有需要另行评审；
- Project 被 DataAsset、ContextEntity、ExternalIdentifier 或审计记录引用时由 `PROTECT` 阻止删除；
- 用户被 ProjectMembership、创建者、审批者或审计记录引用时由 `PROTECT` 阻止删除；
- ProjectMembership 可以由唯一 Project service 删除，但对应审计事件保留 Project 和目标用户；
- 实施前搜索现有 Project/User 删除调用；如发现必须保留的物理删除业务，停止 Gate B 并单独评审，不降低上述保护。

### 7.2 唯一 Project service

新增或扩展一个明确的 Project 领域 service，提供：

- 创建 Project，并在同一事务中把创建者登记为 owner；
- 添加成员；
- 修改角色；
- 移除成员；
- 查询当前用户角色及动作权限；
- 锁定 Project 和 owner 成员集合，拒绝删除或降级最后一个 owner。

现有 `Project.objects.create()` 的旧调用本阶段不全量改造，因为它们属于旧入口；新核心测试和后续新入口必须调用 Project service。`Project.owner` 字符串不参与任何新权限判断。

### 7.3 并发要求

- 两个事务同时降级或移除 owner 时，最终至少保留一个 owner；
- 重复添加同一用户返回稳定冲突，不产生重复行；
- 角色修改和成员删除使用事务及适当行锁；
- service 不依赖 SQLite 的串行假象，必须在 CI 的 MySQL 8.0 验证。

### 7.4 验证与完成标准

- model 和 migration 只新增表、索引与约束；
- Project 创建和 owner 创建原子完成；
- manager 不能授予、降级或移除 owner；
- owner、manager、contributor、viewer 的写操作权限矩阵通过；
- 最后 owner 的普通及并发删除/降级测试通过；
- 旧 `Project.owner` 仍存在但不被新 service 读取；
- 不切换旧 API 或旧命令。

Gate B 的 model/migration/service/tests 作为一个可审查能力独立提交；若迁移与 service diff 过大，可拆成“新增结构”和“service/测试”两个连续小提交，但不得合并 Gate C。

## 8. Gate C：通用上下文、关系与外部标识

### 8.1 新增模型

新增以下稳定结构：

- `ContextEntity`；
- `DataAssetRelation`；
- `AssetContextLink`；
- `ContextRelation`；
- `ExternalIdentifier`。

同时为现有 `DataFile` 增加 ADR-005 已批准的物理可用状态字段；这不是新的文件模型，也不在阶段一切换文件读取授权。

字段和含义严格遵循 ADR-005，不增加 GenericForeignKey、`related_type + related_id` 或自由关系 JSON。

### 8.2 关键数据库约束

`ContextEntity`：

- `context_code` 全局唯一且非空；
- 真实 `project` 和 `created_by`；
- 保存 `context_type_key/profile_key/schema_version/schema_digest`；
- 状态只允许 `draft/active/archived`；
- metadata 默认空对象。

三类关系：

- 保存 source/target 真实外键、relation type、创建时规则 version/digest 和创建人；
- 禁止直接自关联；
- 各自的 source/target/type 组合唯一；
- `AssetContextLink` 额外保存非负 `position`，并约束同一资产、关系类型和位置不重复；
- 跨 Project、间接防环和动态基数由 Gate D service 保证。

`ExternalIdentifier`：

- `project/asset/context` 三个真实外键使用 `PROTECT`；
- CheckConstraint 保证三个目标恰好一个非空；
- `(namespace_key, normalized_value)` 全局唯一，不把 version 加入唯一键；
- 保存 namespace version/digest、display value、创建人和时间；
- 第一阶段没有 primary、preferred 或顺序字段。

`DataFile.availability_status`：

- 取值固定为 `available/quarantined/blocked/missing`；
- 默认 `blocked`，避免未经物理检查的旧记录或新记录自动获得可用状态；
- `available` 只能由唯一文件完整性操作在确认受控路径、物理存在、记录大小和 SHA-256 后设置；
- `quarantined/blocked/missing` 只能拒绝提交、发布和文件访问，不能授予任何权限；
- 当前 `is_current/access_level/publication_status` 在阶段一继续存在，旧入口仍按旧逻辑工作；阶段二接入新物理状态，阶段三再按删除附录处理重复授权/发布字段；
- 阶段一不把 T4 审计命令的临时报表状态直接当作持久化事实来源，也不自动扫描生产文件。

该完整性操作由新增的、职责单一的 `datafile_integrity_service.py` 所有；它复用现有受控路径解析能力，但不复用或扩展旧 Dataset/FileRelation 授权语义。它只允许按照状态机写入物理状态并返回稳定失败原因，不负责用户读取授权。

### 8.3 migration 边界

- 只创建新表、索引和约束；
- 对 `DataFile` 只新增带索引的 `availability_status`，默认安全失败为 `blocked`；
- 不迁移旧 Accession、Sample、Assembly 或 Annotation 数据；
- 不删除四张固定专业关系表；
- 不修改历史 migration `0026/0027`；
- migration 不读取 Registry 文件、网络或生产文件；
- migration 必须可在空 MySQL 从完整 migration 链执行。

### 8.4 验证与完成标准

- 每个真实外键的删除行为有测试；
- ExternalIdentifier 的零目标、双目标和三目标均被数据库拒绝；
- 外部编号跨 namespace version 仍保持唯一；
- 重复关系、直接自关联、重复 position 被数据库拒绝；
- 可从资产反查上下文、从上下文反查资产及上下文关系；
- MySQL 8.0 实际验证 CheckConstraint 和唯一约束行为；
- DataFile 默认 blocked，只有完整性校验成功才能转为 available；其他状态均阻止新核心提交和发布；
- model 与 `makemigrations --check --dry-run files` 一致；
- 不接入旧调用方。

Gate C 应形成独立提交。任何发现需要增加第四种通用关系、万能 object 或额外目标外键的需求，应停止并回到 ADR 评审。

## 9. Gate D：唯一业务 service 与生命周期

### 9.1 Gate D0：审计持久化结构

Gate D 编码前先实现并评审 `CoreAuditEvent`，它是阶段一生命周期审计的唯一事实来源，不扩展为运行血缘或通用日志平台。

字段至少包括：

| 字段 | 约束 |
| --- | --- |
| `project` | 必填 `Project` 外键，`PROTECT` |
| `actor` | 必填真实用户外键，`PROTECT` |
| `event_type` | 受控事件类型，不接受调用者自定义字符串 |
| `asset` | 可空 `DataAsset` 外键，`PROTECT` |
| `context` | 可空 `ContextEntity` 外键，`PROTECT` |
| `subject_user` | 可空用户外键，记录成员变更目标，`PROTECT` |
| `from_value/to_value` | 状态或角色变化前后的受控值 |
| `before_digest/after_digest` | 重要内容变化前后的规范化摘要，不保存整份敏感 metadata 快照 |
| `reason` | 退回、撤回批准、归档和高风险成员变更时必填 |
| `created_at` | 只增不改的事件时间 |

数据库保证 `asset/context/subject_user` 恰好一个非空。成员删除后不保留对 `ProjectMembership` 行的外键，而是保留 Project 和目标用户；因此成员行可删除，审计事实仍存在。事件类型与目标种类、允许的 from/to 值和 reason 必填规则由受测试的审计 service 固定。

`CoreAuditEvent` 不使用 GenericForeignKey、`related_type + related_id`、任意 payload JSON 或自由对象类型字符串。领域 service 只能追加事件，不能更新或普通删除；状态或成员变化与审计事件在同一事务中提交。该模型和约束作为 Gate D0 的 additive migration 独立提交。

`event_type`、目标种类及 `from_value/to_value` 的允许组合同时使用数据库 CheckConstraint 能表达的结构约束和 service 规则校验；不能只依赖 Django `choices`。

### 9.2 service 职责

在前三个 Gate 的结构上实现唯一写入路径：

- Project 成员和动作权限检查；
- Context 创建、编辑、激活和归档；
- ExternalIdentifier 创建和显式移除；
- 三类关系创建、替换和移除；
- DataAsset draft 创建和编辑；
- DataAsset 提交、退回、批准、撤回批准、发布和归档；
- 关系、编号、Profile 和文件成员的分层校验；
- 状态、审计和相关写入在同一事务中提交。

现有 `create_data_asset()` 必须被重构为新 service 的 draft 创建入口，删除其对四张固定专业关系表的写入参数。不得保留一个“旧参数版本”和一个“新参数版本”长期并行；旧测试同步改为新结构，新业务调用者仍未接入。

### 9.3 Draft 与完整性校验

创建和编辑 draft 时：

- 允许缺少必填 metadata、核心文件和最小数量关系；
- 拒绝未知字段、未知 Profile、非法类型、错误方向、重复、自关联、成环、超过最大基数、非法编号和越权；
- 切换 Profile 必须在同一事务中重新校验已有 metadata、文件和关系。

提交时：

- 检查完整 metadata、核心文件、最小关系和 active Context；
- 检查文件记录存在、checksum 和可用状态；
- 同 Project `uses_reference` 目标至少 approved；
- 跨 Project 目标必须 `released + public`；
- 失败时资产保持 draft。

批准和发布时：

- 重新加载并锁定资产及相关关键记录；
- 重新检查完整性、角色、关系、跨 Project 目标和文件状态；
- 发布要求同 Project 参考目标 released；
- 状态变化和审计记录原子提交；
- 不依赖先前校验结果或缓存授权。

其中“可用”明确要求 `DataFile.availability_status == available`，不能用旧 `publication_status` 代替物理完整性事实。

### 9.4 关系安全

- `AssetContextLink` 和 `ContextRelation` 始终同 Project；
- `supersedes` 始终同 Project、同 Profile family、无环且无分支；
- `uses_reference` 默认同 Project，跨 Project 仅允许公开且已发布目标；
- 防环和基数检查使用事务、行锁或经过证明的串行化策略；
- 被 submitted、approved 或 released 资产引用的 Context/参考资产不能普通归档；
- released 资产不原地修改关键内容，archived 不原地恢复。

### 9.5 读授权边界

Gate D 只实现执行写动作所需的 Project 角色判断和 service 级对象检查。面向 API/JBrowse/文件内容的统一读取授权仍属于阶段二。

阶段一可以测试 ADR-005 权限矩阵中的创建、编辑、激活、提交、批准、发布、归档和成员管理动作，但不得把旧 `data_asset_access_service.py` 描述成已经完成的新仓读取授权。

### 9.6 审计事件范围

首批事件类型固定覆盖：

- 成员添加、角色变更和成员移除；
- Context 创建、重要内容修改、激活和归档；
- DataAsset 创建、重要内容修改、提交、退回、批准、撤回批准、发布和归档；

Draft 中 ExternalIdentifier 和关系的普通增删由各关系行的创建审计字段记录；它们引起的 DataAsset 或 Context 重要契约变化，以对应主体的“重要内容修改”事件和前后 digest 记录。阶段一不为审计再建立一套平行关系快照。

文件内容访问审计、Token 审计、分析运行日志和完整 metadata 历史不进入 `CoreAuditEvent`，分别留给后续授权、Token 和血缘决策。

### 9.7 并发测试

至少覆盖：

- 同一资产并发编辑与提交；
- 并发批准与内容撤回；
- 并发发布与参考目标归档/转私有；
- 并发创建可能成环的关系；
- 并发创建超出最大基数的关系；
- 并发为同一旧版本建立两个 `supersedes` 后继；
- 并发使用相同规范化外部编号；
- 并发移除最后 owner。

SQLite 可运行快速单元测试，但并发和约束收口以 CI 的 MySQL 8.0 结果为准。

### 9.8 完成标准

- 所有新核心写入都通过唯一 service；
- draft 分层校验、Context 生命周期和 DataAsset 状态机通过；
- 权限、跨 Project、基数、防环、冻结和归档保护通过；
- 状态变化与审计原子提交；
- 失败和并发冲突返回稳定的领域错误，不泄露内部路径或其他 Project 信息；
- 无 API、前端、JBrowse、旧命令或生产切换；
- 不存在写入旧专业关系的兼容分支。

Gate D 应独立提交，并在完成后进行阶段一整体评审。

## 10. 建议文件影响范围

最终路径以实施前调查为准，预计只涉及：

```text
django2/files/models.py
django2/files/migrations/<new_additive_migrations>.py
django2/files/data_asset_registry/*.json
django2/files/services/data_asset_registry_service.py
django2/files/services/data_asset_service.py
django2/files/services/datafile_integrity_service.py
django2/files/services/<bounded_project_context_relation_services>.py
django2/files/tests/unit/<new_or_updated_tests>.py
django2/files/tests/integration/<mysql_transaction_tests>.py
docs/architecture/GeneData_ADR005_阶段一新核心基础实施方案.md
docs/ACTIVE_DOCUMENTS.md                 # 仅在本方案评审为 active 时更新
```

不得修改：

- Vue 前端；
- 现有 API 路由和 serializer；
- JBrowse、旧导入、旧查询和旧文件授权；
- 已执行的历史 migration；
- 生产设置、生产数据库或生产文件；
- ADR-004 的历史证据和旧数据库备份。

## 11. 提交和评审顺序

推荐顺序如下：

1. **A：Registry 与状态契约**——配置、加载校验和测试；
2. **B：ProjectMembership**——新增模型/migration、Project service 和并发测试；
3. **C：通用模型与文件物理状态**——Context、三类关系、ExternalIdentifier、DataFile availability、additive migration 和约束测试；
4. **D0：审计基础**——`CoreAuditEvent`、additive migration、不可变写入和约束测试；
5. **D1：写入与生命周期 service**——分层校验、关系、状态、权限和审计原子提交；
6. **D2：并发收口**——事务测试和阶段回归。

这里的 A/B/C/D 是阶段一内部提交边界，不是新的项目大阶段。每个提交只暂存本 Gate 的文件，验证通过后再进入下一 Gate；不得使用全量暂存，也不得把无关工作区修改带入提交。

每个 Gate 完成后做一次针对性代码评审；D2 后再做阶段一整体评审和收口。若某 Gate 需要变更 ADR-005 已批准语义，先暂停实施并修订 ADR，不在代码中临时决定。

## 12. 测试与检查清单

每个 Gate 运行最小相关测试；阶段一收口至少运行：

```bash
cd django2
python manage.py check
python manage.py makemigrations --check --dry-run files
python manage.py test files --noinput
python manage.py check --deploy --fail-level ERROR --settings=filemanager.settings_production
```

并确认 CI 在隔离 MySQL 8.0 中通过。若本地没有 MySQL，可先完成快速测试，但必须标记“目标数据库未验收”，不能关闭相应 Gate。

阶段一不修改前端，因此不要求因本文单独运行前端测试；如果实施中意外影响前端契约，应停止并重新评审范围，而不是顺带修改前端。

## 13. 阶段一总体验收标准

只有同时满足以下条件，阶段一才能标记完成：

1. Gate A 至 Gate D 均完成独立评审、提交和测试；
2. 新 Registry 条目具有版本、完整 digest 和历史解释路径；
3. Project 创建者成为 owner，最后 owner 在并发场景不能被移除或降级；
4. Context、三类关系和 ExternalIdentifier 的 model、真实外键和数据库约束通过；
5. ExternalIdentifier 恰好一个目标、跨版本唯一且无 external primary；
6. 关系方向、基数、自关联、防环、同 Project 和公开跨 Project 规则通过；
7. Context 与 DataAsset 生命周期、冻结、撤回和归档保护通过；
8. Draft 不完整可以保存，但 Draft 非法始终被拒绝；
9. 提交、批准和发布各自重新校验，失效结果不能并发进入 released；
10. 新核心写入只有一个 service 路径，并保存必要审计；
11. MySQL 8.0 的 CheckConstraint、唯一性和并发测试通过；
12. DataFile 具有默认安全失败的物理可用状态，只有 available 文件可以进入新核心提交和发布；
13. Dataset/FileRelation 仍明确标记为未切换的遗留入口；
14. 没有旧结构回填、双读、双写、fallback、删表、API/前端切换或生产部署；
15. 文档准确区分已实现、已验证和待阶段二切换。

### 13.1 ADR-005 验收项阶段映射

ADR-005 第 7 节是最终完成标准，不要求全部在阶段一关闭。按职责映射如下：

| ADR-005 验收项 | 负责阶段 | 阶段一边界 |
| --- | --- | --- |
| 1—7、9—12、14—15、20—21 | 阶段一 | 完成 Registry、模型、外键、关系、状态、owner、分层校验和 service 验证 |
| 8 | 阶段一 + 阶段二 | 阶段一验证关系创建及提交/批准/发布；阶段二在每次实际读取或插件使用时重新授权 |
| 13 | 阶段一 + 阶段二 | 阶段一验证成员管理和写动作；阶段二完成项目/资产读取可见性矩阵 |
| 16 | 阶段一 + 阶段二 | 阶段一验证引用目标的归档/转私有保护；阶段二验证紧急物理阻断实际拒绝文件访问 |
| 17 | 阶段一 + 阶段四 | 阶段一固定并校验公开字段契约；阶段四验证 API 只序列化声明字段 |
| 18—19 | 阶段二 + 阶段三 | 阶段二切换逐资产、membership、DataFile 物理状态授权；阶段三退出重复字段 |
| 22 | 阶段二 | JBrowse 切换并验证不依赖旧 Annotation/FileRelation |
| 23—25 | 阶段三 | 删除附录、逐项 migration、空库完整 migration 链 |
| 26 | 阶段二至四 | 每个已切换能力不得双读双写；阶段四完成 API/前端最终验证 |
| 27 | 各相关阶段 | 阶段一验证 Registry、互斥外键、唯一性和状态并发；后续阶段验证授权和调用切换并发 |
| 28 | 全过程边界 | 不把旧 Token 当作新仓正式授权；阶段四前另行批准 Token ADR |

## 14. 回滚与停止条件

### 14.1 回滚边界

- 阶段一 migration 只能是 additive；
- 在未接入业务入口且仅有测试数据时，可以按 Gate 逆序回滚新增 migration；
- Registry 变更通过 Git commit 回滚，但已被持久记录引用的版本不能从正式历史中物理消失；
- service 回滚不能留下已写入但无法解释的 version/digest；
- 本阶段不需要、也不允许以删除旧数据作为回滚手段。

### 14.2 必须停止并请求决策

出现以下任一情况时停止实施：

- 需要 GenericForeignKey、字符串多态关系或万能 object；
- 需要同时写新旧关系、增加 fallback 或形成第二套活动 Registry；
- 需要修改现有 API、前端、JBrowse、导入或生产环境才能让 Gate 通过；
- MySQL 无法保证已批准约束，且没有经过评审的等价方案；
- 发现 Project 或用户删除策略会破坏既有生产语义；
- `CoreAuditEvent` 的字段、约束或删除保护无法满足本方案却准备进入状态切换实现；
- 并发不变量只能依靠无锁的“先查询再写入”；
- 需要新增 ADR-005 未批准的关系、状态、跨 Project 授权或 Token 能力；
- 无法保护工作区已有修改或无法限定独立提交范围。

## 15. 本方案批准后的第一项工作

本方案评审通过后，先执行 Gate A，不立即改 model：

1. 复核 Registry 文件拆分和唯一加载入口；
2. 固定 canonical digest、首批 Context Profile、Relation Registry 和 Namespace Registry；
3. 补充 Registry 与状态契约测试；
4. 完成 Gate A 独立评审、提交和推送；
5. 再进入 ProjectMembership 的 model/migration 设计。

这样可以先把后续 model 和 service 依赖的规则固定下来，减少反复修改 migration 的风险。
