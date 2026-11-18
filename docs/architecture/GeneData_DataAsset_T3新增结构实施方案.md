---
title: GeneData DataAsset T3 新增结构实施方案
status: active
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes: null
---

# GeneData DataAsset T3 新增结构实施方案

## 1. 状态与目标

Accepted，2026-11-18。

本方案是 ADR-002 获批后的 T3 实施门禁。批准范围仅限本文列出的开发环境新增结构与验证，不包含
API、前端、生产部署、回填或 Dataset 切换。

T3 只完成“新增结构并验证，不切换活动读写”：

1. 建立唯一的版本控制 DataType/Profile/Schema 注册表入口；
2. 新增 `DataAsset`、`AssetFileMembership`、`DataAssetAccession` 三个目标模型；
3. 新增只服务于 DataAsset 的创建校验和 fail-closed 权限组合能力；
4. 用模型、约束、注册表和权限测试证明结构可用；
5. 保持 `Dataset` 为当前活动事实来源，不回填、不双写、不切换 API 或前端。

### 1.1 实施结果

T3 已在开发分支完成，尚未部署生产：

- `4ce83f0`：版本控制注册表、唯一加载/校验入口和注册表测试；
- `c91f2cd`：三个目标模型、migration `0026_auto_20261118_1523` 和数据库约束测试；
- `0211590`：最小创建 service、资产—文件授权组合入口和针对性测试；
- `python manage.py test files --noinput`：470 项通过，1 项既有跳过；
- `python manage.py makemigrations --check --dry-run files`：无 migration 漂移；
- 生产设置检查无 ERROR，保留现有 HSTS 和 SSL redirect 两项 WARNING。

本结果不表示 migration `0026` 已在生产执行，也不表示存在 DataAsset 生产数据、API、前端、回填或
Dataset 切换。

## 2. 已核实的实现约束

- 后端为 Django 3.2，数据库和 CI 目标为 MySQL 8；
- 当前 `Dataset`、`DatasetAccession`、`DataFile` 和 `FileRelation` 位于 `django2/files/models.py`；
- 当前文件授权集中在 `files/services/datafile_access_service.py`，仍通过 `DataFile.dataset` 和
  `FileRelation(dataset)` 计算 Dataset 策略；
- 当前没有可直接复用的 Project 成员关系模型；
- T3-A 已引入 `jsonschema` 和唯一 DataAsset 注册表入口；新增普通类型不需要新增数据库表；
- MySQL 不会实施 Django 3.2 的条件 `UniqueConstraint(condition=...)`，不能用看似存在、实际未落库的
  条件唯一约束实现 primary 不变量。

## 3. 范围

### 3.1 T3-A：注册表最小原型

新增一个版本控制的 JSON 注册表目录和一个加载/校验 service：

- 注册表声明 `data_type_key`、`profile_key`、schema version、metadata JSON Schema、允许的 file role、
  deprecated 状态和替代项；
- service 统一完成注册表自身校验、key/profile 查找、规范化 schema digest、metadata 校验和 file role
  校验；
- digest 对规范化 JSON 计算 SHA-256，不接受调用方自行声明的 digest；
- 注册表默认只读，进程内缓存以文件内容为边界；测试可注入独立临时注册表，不增加第二个加载入口；
- 原型至少覆盖 genome、microscopy 和 tabular 三类 profile，证明新增普通类型不修改模型或 API 分支；
- 使用单一成熟 JSON Schema 依赖，不自行实现不完整的 schema 解释器。

建议路径：

- `django2/files/data_asset_registry/registry.json`
- `django2/files/services/data_asset_registry_service.py`
- `django2/files/tests/unit/test_data_asset_registry_service.py`

### 3.2 T3-B：三个模型和新增 migration

按 ADR-002 新增：

- `DataAsset`；
- `AssetFileMembership`；
- `DataAssetAccession`。

实施约束：

- 不修改、删除或重命名现有 `Dataset`、`DatasetAccession`、`DataFile.dataset` 和
  `FileRelation(dataset)`；
- 不新增 `FileRelation(data_asset)`；
- 不新增 Collection、Release、DataType、Profile、PropertyDefinition 或专业类型资产表；
- 新表为空，因此核心必填字段第一版直接非空；不为假设中的回填问题提前制造 nullable 债务；
- migration 只创建空表、索引和约束，不运行生产数据查询或回填；
- 外键删除行为按 ADR-002 使用 `PROTECT`，只有资产本身删除时成员行使用 `CASCADE`；资产硬删除限制由
  service 负责，T3 不暴露删除 API。

### 3.3 MySQL primary 唯一约束

为在 MySQL 8 中真正保证条件唯一性，两个关系模型各增加一个仅用于数据库不变量的可空
`primary_slot` 字段：

- primary 记录必须为 `1`；
- 非 primary 记录必须为 `NULL`；
- `DataAssetAccession` 使用唯一 `(asset, primary_slot)`；
- `AssetFileMembership` 使用唯一 `(asset, file_role, primary_slot)`；
- `CheckConstraint` 保证业务字段与 `primary_slot` 一致；
- 所有正式写入只经过 service，由 service 设置该字段；绕过 service 的错误写入由数据库拒绝。

MySQL 允许唯一索引中存在多行 `NULL`，因此该结构既允许多个非 primary 记录，又能真正限制一个
primary。该字段不进入 serializer、Manifest 或前端契约，不产生新表和第二份业务事实。

### 3.4 T3-C：创建与授权 service

新增一个 DataAsset 写入 service，负责：

- 校验注册表 key、profile、schema version、schema digest 和 metadata；
- 校验成员 file role；
- 在事务内创建资产、成员和 Accession 关系；
- 设置 primary guard 字段并把数据库完整性错误转换为稳定领域错误；
- 拒绝空字符串、未知注册项、未知角色和不完整正式资产；
- 不写入 Dataset，不双写 FileRelation，不执行自动迁移猜测。

新增或收敛一个 DataAsset 授权组合入口，负责：

- 资产未 released、状态无法识别或 Project 缺失时 fail closed；
- DataAsset visibility 只能收紧，不能放宽 DataFile 策略；
- 每个成员文件继续调用现有 `resolve_datafile_access`，不复制文件授权实现；
- T3 不暴露 DataAsset API，因此只提供可测试的领域决策和后续权限对比基础；
- Project 成员关系尚无批准模型，T3 不虚构项目 ACL；private 和 lab_internal 的交互式用户授权继续
  保持未开放，后续独立决策。

建议路径：

- `django2/files/services/data_asset_service.py`
- `django2/files/services/data_asset_access_service.py`
- 对应 unit tests

### 3.5 T3-D：验证

必须覆盖：

- 无 Accession 的资产可以创建；
- 一个资产可关联多个 Accession，但最多一个 primary；
- 一个 DataFile 可属于多个资产，同一资产内不能重复；
- 每个资产/file role 最多一个 primary 文件；
- 未知 profile、schema、metadata 字段和 file role 被拒绝；
- 新增一种测试类型只增加注册表条目，不修改 model；
- 资产策略或文件策略任一更严格时取更严格结果；
- 草稿、未发布、无 Project、无 checksum 或文件未 released 时拒绝；
- Dataset 当前查询、授权和 API 行为不变。

提交前至少运行：

```bash
cd django2
python manage.py check
python manage.py makemigrations --check --dry-run files
python manage.py test files.tests.unit.test_data_asset_registry_service --noinput
python manage.py test files.tests.unit.test_data_asset_models --noinput
python manage.py test files.tests.unit.test_data_asset_service --noinput
python manage.py test files.tests.unit.test_data_asset_access_service --noinput
python manage.py test files.tests.unit.test_datafile_access_service --noinput
python manage.py test files --noinput
python manage.py check --deploy --fail-level ERROR --settings=filemanager.settings_production
```

## 4. 明确不做

T3 不实施：

- Dataset -> DataAsset 映射、回填或生产审计；
- Dataset/DataAsset 双读、双写、fallback 或兼容 API；
- serializer、ViewSet、URL、OpenAPI、Vue 页面或外部工具切换；
- Project 成员表、用户级 ACL、Collection、Release、AnalysisRun 或血缘模型；
- Annotation、Assembly、Sample 等专业实体的 DataAsset 中间表；
- 生产部署、migration 执行或生产数据修改。

## 5. 提交边界

T3 拆成两个聚焦提交，避免模型、依赖和授权一次混合：

1. 注册表、JSON Schema 依赖及注册表单元测试；
2. 三个模型、新 migration、创建/授权 service 及针对性测试。

两个提交均不得切换现有 Dataset 路径。第二个提交必须以第一个提交和本方案批准为前提。

## 6. 回滚

- T3 尚无生产数据和活动调用方；代码回滚只删除新增 service、注册表和模型引用；
- migration 若仅在开发/CI 执行，可反向删除三个空表；
- 若 migration 已进入生产，即使表为空也必须通过受审反向 migration 或后续 migration 处理，不手工
  删除表；
- 一旦后续开始回填，本回滚方案失效，必须在 T4 单独制定数据备份和恢复方案。

## 7. 批准门槛

本方案已批准，允许依次进入 T3-A 和 T3-B/C 编码，不表示允许生产部署、回填或 Dataset 切换。

已确认：

1. 接受使用两个内部 `primary_slot` 字段换取 MySQL 可执行的数据库唯一约束；
2. 接受 T3 暂不建设 Project 成员表，非公开交互式授权继续 fail closed；
3. 接受 T3 只新增结构，不提供新 API 或前端入口；
4. 接受后续 T4 才开发 dry-run 映射和回填准备。
