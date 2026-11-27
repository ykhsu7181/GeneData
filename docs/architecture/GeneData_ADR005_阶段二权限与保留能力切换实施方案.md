---
title: GeneData ADR-005 第二阶段：权限与保留能力切换实施方案
status: active
owner: 徐杨珂
last_reviewed: 2026-11-27
supersedes: null
---

# GeneData ADR-005 第二阶段：权限与保留能力切换实施方案

## 1. 文档状态与实施前提

本文把已批准的 [ADR-005](../adr/ADR-005-dataasset-context-identifiers-and-project-authorization.md) 第二阶段拆成可独立评审、测试、提交和回滚的 Gate。用户于 2026-11-27 明确要求重新核对当前 HEAD 的旧调用入口、形成处置矩阵并进入 Gate A，因此本文正式批准为 `active`。该批准只授权本文定义的本地分 Gate 实施，不授权生产部署、旧表删除或跨 Gate 重写。

阶段二的已验证输入为：

- 阶段一 Gate A 至 Gate D 已完成；
- commit `1de5530a3328b4248512a09b24241c41c87024a6` 已推送；
- 本地 MySQL 8.0 `files` 全量测试 560 项通过、1 项跳过；
- GitHub Actions `GeneData CI #46` 已对同一 commit 验证成功；
- `Dataset`、`FileRelation`、旧专业实体、旧 API 和前端仍存在，且尚未切换；
- 没有执行生产 migration、部署、旧数据迁移或真实数据验收。

权威依据按以下顺序执行：

1. 仓库根目录 `AGENTS.md`；
2. `docs/ACTIVE_DOCUMENTS.md` 中的 active 决策；
3. ADR-004 的新仓空业务库和旧系统离线边界；
4. ADR-005 的授权、文件、插件和四阶段边界；
5. 阶段一已验证代码、migration、测试与 CI；
6. G4 调用面审计记录的当前遗留依赖。

## 2. 阶段二要解决的问题

阶段一建立了新核心的写入和生命周期规则，但正式读取链路仍未切换：

- `data_asset_access_service.py` 仍以旧 DataAccessToken 和 DataFile 访问级别为主要判断，并继续委托旧 `datafile_access_service`；
- `datafile_access_service.py` 仍读取 `DataFile.dataset`、`FileRelation` 和 `Dataset` 的发布/可见性；
- JBrowse 仍以旧 `Assembly`、`Annotation` 和 `FileRelation` 选择 FASTA、GFF、索引和派生文件；
- `AnnotationFeatureIndex` 仍直接关联旧 `Annotation`；
- 当前导入批次、文件绑定和多类查询仍写入或读取 Accession、Sample、Assembly、Annotation、Dataset 和 FileRelation；
- 当前正式 API 和前端仍展示旧 Dataset/专业实体契约。

因此，阶段二不是再增加一套并行能力，而是让“需要长期保留的后端能力”开始只使用阶段一的新核心。

## 3. 目标与非目标

### 3.1 目标

阶段二完成后必须做到：

1. 新仓读取授权只由真实 Django 用户、匿名用户、ProjectMembership、DataAsset 状态/可见性、AssetFileMembership 和 DataFile 物理状态决定；
2. DataFile 的旧 `access_level`、`publication_status` 和 Dataset/FileRelation 不能为新仓访问授予权限；
3. 所有返回资产、上下文、关系和文件逐节点重新授权，不能只校验入口对象；
4. 直接按 file code 访问时必须先找到一条当前用户可见的资产 membership；
5. JBrowse、FASTA/注释索引及其构建命令从 Profile、文件角色和 `uses_reference` 解析输入；
6. 新仓批次导入通过阶段一唯一 service 创建 ContextEntity、DataAsset、ExternalIdentifier、关系和文件成员；
7. 新仓内部查询 service 只查询新核心并复用同一授权规则；
8. 每个已切换能力都不读取旧关系、不双读、不双写、不 fallback；
9. 在 MySQL 8.0 和 CI 中验证授权矩阵、并发、文件阻断、JBrowse、索引、导入和查询。

### 3.2 非目标

阶段二明确不实施：

- 新的正式 REST API、serializer、URL、普通用户页面或动态表单；
- 前端 Data Overview、详情页和管理页面重建；
- DataAccessToken、服务账号、机器 scope 或新的外部工具凭证；
- 私有或内部资产的跨 Project 授权；
- 对象级 ACL；
- AnalysisRun/ProcessingRun 血缘；
- 旧生产数据迁移、旧关系回填或 `manual_files` 整体扫描导入；
- 删除 Dataset、FileRelation、旧专业实体、旧字段或历史 migration；
- 生产 migration、部署或真实数据验收。

## 4. 阶段边界与唯一事实来源

### 4.1 新仓读取授权的唯一所有者

阶段二扩展现有 `data_asset_access_service.py`，使其成为新仓 DataAsset、ContextEntity、关系节点和成员文件读取授权的唯一领域边界。不得新增 `*_v2`、`new_access_service` 或在 view、serializer、JBrowse service、management command 中复制权限矩阵。

现有 `datafile_access_service.py` 分为两个清晰部分：

- 受控路径解析、允许根目录检查和物理文件定位能力继续复用；
- 基于 Dataset、FileRelation、DataFile.access_level/publication_status 和旧 Token 的授权逻辑只允许服务尚未切换的遗留入口，并明确标记为 legacy。

任何已经切换到新仓的能力都不得再次调用旧授权函数。阶段三删除最后调用者后，再单独审批删除旧授权代码和重复字段。

### 4.2 不把保留旧表误解为双读

阶段二允许旧表继续存在，是为了避免在调用切换和删除之间同时承担两类风险。允许的过渡状态是：

- 新仓 service、JBrowse/索引新路径和新仓导入/查询只读取新结构；
- 尚未处置的旧 API、页面和命令继续明确标记为 legacy；
- 同一个入口或同一个 service 不得“新结构没有结果就读取旧结构”；
- 不把新写入同步到旧 Dataset、FileRelation 或专业实体；
- 阶段三负责删除或停用剩余旧入口，并逐项审批删表。

### 4.3 阶段二可以新增的 schema 变化

阶段二原则上以 service 和调用切换为主。只有 JBrowse/AnnotationFeatureIndex 等保留能力缺少到 DataAsset 的真实外键时，才允许新增 additive migration：

- 在现有长期保留模型上增加明确的 DataAsset 外键、约束或索引；
- 为过渡期旧行保留旧外键，但新路径只能写新外键；
- 如同一表暂时允许旧目标或新目标，必须由 CheckConstraint 保证目标形状，不能使用 GenericForeignKey 或字符串多态关系；
- 不在本阶段删除旧外键、旧表或旧字段；
- 不执行旧数据回填。

## 5. 授权契约

### 5.1 DataAsset 可见性

授权必须执行 ADR-005 已批准矩阵：

| 资产状态与可见性 | 匿名 | Project viewer/contributor | manager/owner | 创建者 |
| --- | --- | --- | --- | --- |
| `released + public` | 可读 | 可读 | 可读 | 可读 |
| 未 released 的 `public` | 不可读 | 仅创建者 | 可读 | 可读 |
| `lab_internal` | 不可读 | 同 Project 可读 | 同 Project 可读 | 同 Project 可读 |
| `private` | 不可读 | 他人不可读 | 同 Project 可读 | 可读 |
| `archived` | 匿名不可读 | 按 private/lab_internal 规则 | 按 private/lab_internal 规则 | 按原规则 |

未知状态、未知 visibility、缺少 owning Project、无活动成员关系或无法确定授权时一律拒绝。

### 5.2 文件访问

文件访问按以下顺序安全失败：

1. 授权调用者读取指定 DataAsset；
2. 验证 DataFile 确实属于该资产的一条 AssetFileMembership；
3. 验证该文件角色是当前 Profile 声明的角色；
4. 验证 `DataFile.is_current=True`；
5. 验证 `availability_status=available`；
6. 使用既有受控路径解析检查文件位于允许根目录、真实存在且类型正确；
7. 只返回受控交付结果，不返回服务器绝对 `file_path`。

DataFile 的任何字段都只能进一步拒绝访问，不能绕过 DataAsset 授权。一个 DataFile 属于多个资产时，授权结果必须绑定到调用者明确选择或 service 确定的一条可见 membership，不得暴露其他不可见资产关系。

### 5.3 直接按 file code 访问

直接文件访问不能只查询 DataFile。service 必须：

- 找到该文件的所有 AssetFileMembership；
- 对每个 owning DataAsset 独立执行授权；
- 没有可见 membership 时返回统一的不存在/不可用结果；
- 多条可见 membership 的权限结果不一致时使用最严格结果，或要求调用者明确 asset_code；
- 响应中只包含获准 membership 所允许的信息。

### 5.4 Context、关系与跨 Project 引用

- 完整 ContextEntity 只允许 owning Project 成员读取；
- 匿名读取 `released + public` 资产时，只能获得 Context Profile 明确列入 `public_metadata_fields` 的字段；
- 不返回 context_code、内部描述、创建者、审计字段、未声明 metadata 或同一 Context 的其他资产关系；
- `uses_reference` 每次实际使用时重新确认跨 Project 目标仍为 `released + public`；
- JBrowse 和其他插件必须分别授权注释资产、参考资产及每一个成员文件，不能因为注释资产可见就自动放行参考资产全部内容。

### 5.5 稳定错误与防泄露

领域 service 可以记录稳定内部 reason code，但外部边界不得据此泄露私有对象是否存在。未授权、membership 不可见、文件阻断和对象不存在在公开入口统一映射为不暴露存在性的响应；日志不得包含 token、绝对路径或敏感 metadata。

## 6. 实施前 P0：只读调用面冻结

编码前先更新 G4 调用面处置矩阵，逐个运行入口标记：

| 处置 | 含义 |
| --- | --- |
| `switch-phase2` | 阶段二必须改为新核心，完成后不能读旧关系 |
| `legacy-until-phase3` | 阶段二不改语义，阶段三删除或停用 |
| `new-api-phase4` | 不在阶段二创建正式用户入口，阶段四复用已完成的 service |
| `archive-only` | 历史审计或迁移证据，只保留追溯，不进入新仓运行路径 |

P0 至少覆盖：文件下载/metadata、JBrowse、AnnotationFeature、FASTA/Tabix/参考名索引、Data Overview/查询、批次导入、外部 manifest/sequence、所有 management command、URL 和前端调用。未完成处置矩阵前不得开始 Gate A。

## 7. Gate A：新仓唯一读取授权

### 7.1 实施内容

- 重构现有 `data_asset_access_service.py`，输入只接受真实 Django user 或匿名调用者，不接受旧 DataAccessToken 作为新仓权限主体；
- 提供资产可见性、Context 公开投影、关系目标使用和资产成员文件授权；
- 提供可组合的授权 queryset/filter，避免先返回再在 view 中过滤；
- 所有检查默认拒绝，并返回稳定领域 reason code；
- 保留 `resolve_protected_datafile_path` 一类物理路径安全能力，但新授权 service 不调用旧 Dataset 权限函数；
- 搜索并禁止新仓 service/view/command 直接读取 `Project.owner` 字符串进行授权。

### 7.2 测试矩阵

至少覆盖：

- owner、manager、contributor、viewer、创建者、非成员和匿名用户；
- own private、other private、lab_internal、未 released public、released public 和 archived；
- 用户停用、成员删除、角色变化后的即时重新授权；
- Context 完整读取与公开字段投影；
- 同 Project 与跨 Project `uses_reference` 的每次使用检查；
- 不可见对象与不存在对象的外部错误等价；
- 查询列表中每个节点均经过授权，不发生对象存在性泄露。

### 7.3 完成标准

- 新授权 service 不导入 Dataset、FileRelation、旧专业实体或 DataAccessToken；
- 权限矩阵和逐节点授权测试通过；
- 旧 `data_asset_access_service` 的 Token/Dataset 组合语义已被替换，不保留新旧 fallback；
- 未修改正式 API 和前端；
- Gate A 独立评审、提交并推送。

### 7.4 2026-11-27 本地实施与评审记录

P0 已基于 commit `1de5530a3328b4248512a09b24241c41c87024a6` 形成活动处置矩阵。Gate A 已在本地完成以下范围：

- 原地重构 `data_asset_access_service.py`，移除对旧 `DataAccessToken`、`datafile_access_service`、Dataset/FileRelation 权限以及旧专业实体的依赖；
- 实现单资产可见性、可组合资产/Context queryset、完整 Context 读取、Profile 公开字段投影、关系两端实时授权和明确资产文件 membership 授权；
- 保持 API、URL、serializer、model、migration、management command、JBrowse、前端和生产配置不变；
- 14 项 Gate A 针对性测试通过，相关核心回归 72 项通过；
- 本地 MySQL 8.0 完整 `files` 套件 568 项通过、1 项跳过；
- `manage.py check` 通过，`makemigrations --check --dry-run files` 显示无变化，禁止旧依赖扫描无命中。

本地评审未发现授权放宽或阶段越界。Gate A 的独立提交、推送和远程 CI 尚未执行，因此当前状态是“本地实施与评审通过，待独立交付验证”，不是生产完成。

## 8. Gate B：DataFile 访问与受控交付切换

### 8.1 实施内容

- 所有 `switch-phase2` 文件访问调用改为“DataAsset -> AssetFileMembership -> DataFile”；
- 直接 file code 访问通过可见 membership 解析，不再根据 DataFile.access_level/publication_status 或 Dataset 放行；
- `available` 是唯一允许读取内容的物理状态，`blocked/quarantined/missing` 均拒绝；
- 继续复用允许根目录、规范化路径、防路径逃逸和 Nginx 受控交付；
- 已切换响应不返回绝对路径、不可见 membership、其他 Project 或内部 checksum；
- 旧 Dataset 外部接口若被 P0 标记为 `legacy-until-phase3`，保持隔离且不得调用新 service 后再 fallback。

### 8.2 测试

- 文件属于/不属于指定资产；
- 同一文件属于公开与私有资产；
- 直接 file code 的零条、一条、多条可见 membership；
- DataFile 四种 availability_status、is_current 和物理文件缺失；
- 允许根目录、符号链接/路径逃逸、HEAD/GET 或 Range 等既有交付行为；
- 对每个返回文件重新授权，查询次数和批量场景无明显 N+1 退化；
- 旧 DataFile.access_level/publication_status 改值不能使新仓访问从拒绝变为允许。

### 8.3 完成标准

- 所有 P0 标记为 `switch-phase2` 的文件访问调用不再依赖 Dataset/FileRelation；
- 已切换路径只有一个授权 service；
- 物理阻断可以立即拒绝内容访问且不删除资产关系或审计事实；
- Gate B 独立评审、提交并推送。

## 9. Gate C：JBrowse 与索引切换

### 9.1 能力契约

JBrowse 不根据 metadata 开关或文件扩展名猜测能力。第一批能力契约固定为：

- Reference Genome DataAsset：Profile family `reference_genome`，必须具有 `genome_fasta`，可选 `fasta_index`、`compression_index`；
- Annotation DataAsset：Profile family `genome_annotation`，必须具有 `annotation_gff`，可选 `tabix_index`；
- Annotation 必须通过单一 `uses_reference` 指向 Reference Genome；
- 调用时分别授权 Annotation、Reference Genome 及所使用的每个 DataFile；
- 派生 JBrowse 配置、索引和缓存不是独立 DataAsset，除非以后有独立 ADR 证明其长期复用价值。

### 9.2 AnnotationFeatureIndex 过渡

`AnnotationFeatureIndex` 和 `AnnotationFeature` 是保留能力，不在本阶段删除。实施时允许在现有 `AnnotationFeatureIndex` 增加到 Annotation DataAsset 的真实外键：

- 新路径只创建或读取 `annotation_asset`；
- 旧 `annotation` 外键只服务明确标记的 legacy 行；
- 数据库约束保证每行目标形状明确，不能同时指向旧 Annotation 和新 DataAsset；
- 不回填旧生产索引；新仓需要的索引从新资产重新构建；
- 阶段三在旧入口退出后单独审批删除旧 `annotation` 外键。

最终字段名、删除策略和约束必须在 Gate C 编码前形成小型 model/migration 评审，不能直接修改历史 migration。

### 9.3 调用切换

- JBrowse config/status/location service 改为接收 DataAsset 或稳定 asset_code；
- FASTA、FAI、GFF、Tabix 和 reference-name 解析只使用 AssetFileMembership.file_role；
- JBrowse 构建和索引命令通过新查询/授权 service 选择资产，不读取 FileRelation；
- 现有正式 URL 的重新设计属于阶段四；阶段二只完成可被阶段四复用的后端能力。若保留现有 browser asset 受控交付路由，必须改为新授权 service 且不改变为新的通用 API；
- 旧 Assembly/Annotation 路由保持 legacy 标记，阶段二不为其添加新旧 fallback。

### 9.4 测试与完成标准

- Reference Genome 与 Annotation 只通过 DataAsset、uses_reference 和成员文件完成 JBrowse 配置；
- 错误 Profile、缺少文件角色、重复 reference、目标未 released、跨 Project 非 public、文件阻断均安全失败；
- AnnotationFeatureIndex 的新外键、目标互斥、源文件变更和索引 stale 检测通过；
- JBrowse 返回的每个文件均独立授权；
- 新 JBrowse/index service 不导入旧 Assembly、Annotation 或 FileRelation；
- Gate C 独立评审、提交并推送。

## 10. Gate D：新仓导入、内部查询与阶段二收口

### 10.1 导入边界

阶段二不为旧 manifest 增加兼容转换器。优先重构现有 `import_data_batch` 成为新仓唯一批次入口，而不是创建 `*_v2`：

- manifest 明确 Project、Context、DataAsset、ExternalIdentifier、AssetFileMembership 和关系；
- DataFile 注册复用并收敛 `file_write_service`，不创建 FileRelation；
- DataFile 创建后先保持 `blocked`，经完整性 service 校验后才能变为 `available`；
- Context、资产、外部编号和关系只能调用阶段一唯一 service；
- 支持 dry-run、有限批次、幂等、审计、稳定冲突报告和失败重试；
- apply 前重新校验，单批次事务边界清晰，失败不得留下半个资产；
- 不扫描或自动导入旧 `manual_files`，只处理用户明确提供的新仓 manifest 和文件路径。

旧 `import_dataset_*`、旧专业实体导入、回填和层级修复命令不改造成新仓兼容写入；它们保持 `legacy-until-phase3` 或 `archive-only`，阶段三按处置矩阵退出。

### 10.2 内部查询边界

新增或收敛一个唯一 DataAsset 查询 service，供阶段二命令、JBrowse 和以后阶段四 API 复用：

- 以 DataAsset/Profile/Project/Context/ExternalIdentifier 为查询维度；
- 查询集在数据库层应用授权，分页后不能再次出现越权节点；
- 关系、Context 和文件成员按需预取，但每个返回节点仍受授权；
- 不返回 file_path，不读取 Dataset/FileRelation 或旧专业实体；
- 阶段二不增加正式 serializer、URL 或前端页面。

现有 Data Overview、Accession 详情和旧查询 API 不在本 Gate 静默改义；它们按 P0 结果留到阶段三删除或阶段四由新 API 替代。

### 10.3 Gate D 验证

- 从空测试库以真实用户创建 Project、成员和新仓批次；
- 导入 Sample Context、Reference Genome、Annotation、Raw Reads、文件成员、外部编号和关系；
- 重复导入幂等，非法 metadata、越权、文件缺失、checksum 错误和关系冲突可审计失败；
- 内部查询权限矩阵、分页、反向关系和 ExternalIdentifier 查询通过；
- 导入和查询运行时无 Dataset/FileRelation/旧专业实体 SQL；
- Gate D 独立评审、提交并推送。

## 11. 建议文件影响范围

实施前以 P0 处置矩阵为准，预计可能涉及：

```text
django2/files/models.py
django2/files/migrations/<new_additive_migration>.py
django2/files/services/data_asset_access_service.py
django2/files/services/datafile_access_service.py
django2/files/services/protected_asset_service.py
django2/files/services/annotation_feature_index_service.py
django2/files/services/jbrowse_*.py
django2/files/services/fasta_index_service.py
django2/files/services/reference_name_service.py
django2/files/services/file_write_service.py
django2/files/services/ingestion/
django2/files/management/commands/import_data_batch.py
django2/files/management/commands/build_*index*.py
django2/files/tests/
docs/audits/<阶段二调用面处置矩阵>.md
```

以下默认不修改：

- `vue_project/`；
- 新的正式 API/serializer/URL；
- 旧表和旧字段的删除 migration；
- 生产设置、生产数据库和生产文件系统；
- 历史 migration；
- DataAccessToken 模型和 scope。

如果实现需要同时修改正式 API 和前端，必须停止当前 Gate，重新确认是否已越过阶段四边界。

## 12. 测试与验收

每个 Gate 先运行最小相关测试。阶段二收口至少运行：

```bash
cd django2
python manage.py check
python manage.py makemigrations --check --dry-run files
python manage.py test files --noinput
python manage.py check --deploy --fail-level ERROR --settings=filemanager.settings_production
```

若改动现有 JBrowse 路由或任何前端正在调用的响应契约，还必须运行：

```bash
cd vue_project
npm test
npm run build
```

并确认 GitHub CI 在隔离 MySQL 8.0 中通过。授权、唯一约束、AnnotationFeatureIndex 目标互斥和并发测试不能只用 SQLite 验收。

## 13. 阶段二总体验收标准

只有同时满足以下条件，阶段二才能标记完成：

1. P0 对所有旧依赖运行入口给出处置结论；
2. 新仓授权只使用 User/AnonymousUser、ProjectMembership、DataAsset、AssetFileMembership 和 DataFile 物理状态；
3. owner、manager、contributor、viewer、创建者、非成员和匿名权限矩阵通过；
4. 资产、Context、关系和文件逐节点授权，公开响应不泄露私有对象存在性；
5. 直接 file code 访问必须先解析可见 membership；
6. DataFile.access_level/publication_status、Dataset 和 FileRelation 不能为新仓授予访问；
7. blocked/quarantined/missing 文件在所有新仓使用路径均被拒绝；
8. JBrowse、FASTA/注释索引和 reference-name 使用 Profile、AssetFileMembership 和 uses_reference；
9. AnnotationFeatureIndex 新路径不依赖旧 Annotation；
10. 新仓批次导入只调用唯一 service，不写旧结构；
11. 内部查询只查询新核心并在数据库层应用授权；
12. 每个已切换能力均无双读、双写或旧关系 fallback；
13. 旧 API、页面和待退出命令仍明确标记为 legacy，没有被描述为已切换；
14. 没有删除旧表、旧字段或历史 migration；
15. MySQL 8.0、完整 `files` 测试和 CI 通过；
16. 文档准确区分已切换后端能力、未切换用户入口和未执行生产验收。

## 14. 回滚边界

- 每个 Gate 独立提交；未部署时通过 Git revert 回滚该 Gate；
- additive migration 在尚未接入运行入口且无新仓持久数据时可回滚；
- 一旦新仓记录引用新增外键，回滚前必须先证明数据可解释，不得静默删除；
- 调用切换回滚不能恢复为“先新后旧”的 fallback；只能整体恢复到上一已批准入口；
- 索引和缓存可以重建，但 DataAsset、Context、ExternalIdentifier、membership 和审计事实不能作为缓存删除；
- 本阶段不以删除旧数据或旧表作为回滚方式。

## 15. 必须停止并请求决策

出现以下任一情况时停止实施：

- 需要 GenericForeignKey、字符串多态关系或第二个物理文件模型；
- 需要同时读取或写入新旧关系才能维持一个入口；
- 需要让 DataFile.access_level、旧 Token 或 Dataset 为新仓授权；
- 需要新增私有跨 Project 共享、对象级 ACL 或新的用户角色；
- 需要在阶段二创建正式新 API 或重做前端；
- JBrowse 无法在不复制专业事实的情况下表达所需关系；
- AnnotationFeatureIndex 过渡无法通过真实外键和数据库约束表达；
- 导入必须扫描旧生产目录、迁移旧业务关系或修改生产数据；
- 需要破坏性 migration、删表、删除历史 migration 或放宽授权；
- 无法保护工作区已有修改或无法形成 Gate 独立提交。

## 16. 本次文档评审结论

2026-11-27 首轮评审确认：

- 方案保持 ADR-005 的“阶段二先切换、阶段三再删除、阶段四建设正式 API/前端”顺序；
- 新授权主体明确限制为真实用户和匿名用户，没有沿用未成熟 Token；
- DataFile 物理状态只会拒绝访问，不会成为授权来源；
- JBrowse/AnnotationFeatureIndex 采用现有模型的 additive 过渡，不新建平行索引模型；
- 导入优先重构现有 `import_data_batch`，不创建 `*_v2`；
- 旧入口保留与新入口切换的边界明确，不允许同一能力双读、双写或 fallback；
- 删除旧表、正式 API、前端、生产部署均保持在本阶段之外。

评审未发现必须返回 ADR-005 的结构性冲突。用户于 2026-11-27 正式批准本文并授权先完成 P0、再进入 Gate A；Gate B 至 Gate D 仍须分别满足各自进入条件。

## 17. 批准后的第一项工作

本文批准后先执行 P0，只做调用面复核和处置矩阵，不立即修改 JBrowse、model 或 migration：

1. 以 G4 调用清单为起点重新搜索当前 HEAD；
2. 标记每个运行入口为 `switch-phase2`、`legacy-until-phase3`、`new-api-phase4` 或 `archive-only`；
3. 明确 Gate A 至 Gate D 的实际文件范围和测试基线；
4. 单独评审 P0 处置矩阵；
5. P0 通过后才进入 Gate A 新仓唯一读取授权。
