---
title: ADR-001 DataAsset 统一科研数据身份与 Dataset 退役边界
status: active
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes: null
---

# ADR-001：DataAsset 统一科研数据身份与 Dataset 退役边界

## 状态

Accepted，2026-11-18。

本 ADR 批准长期稳定架构边界，不表示 DataAsset model、migration、API、权限、前端或生产迁移已经实现。

## 背景

GeneData 需要支持跨物种、跨组学、跨课题组以及显微图像、普通表格等非传统生物信息学数据。现有 `Dataset` 已承担数据身份、类型、版本、发布、可见性、文件分组、Accession 关联和 Manifest 等多种职责，但其名称和固定类型 choices 不适合作为长期通用科研数据核心。

代码审计还确认：

- DataFile 与 Dataset 同时存在真实外键和字符串 FileRelation 两条关联路径；
- Dataset 访问策略影响 DataFile 的有效权限；
- Dataset API 已进入 OpenAPI、测试和前端；
- 没有 Accession、Annotation 或 Species 的数据在结构上可以存在，但缺少统一身份和治理入口。

需要在开始实现前固定唯一科研数据身份和迁移边界。

## 决策

### 1. 唯一科研数据身份

`DataAsset` 是 GeneData 的目标唯一科研数据身份。`Dataset` 在完成映射、切换、生产验收和删除门槛后退役。

迁移期间的活动事实来源必须明确：

```text
切换前：Dataset
切换后：DataAsset
```

禁止长期双写、双读、无期限 fallback、两套平行 API 或两套活动事实来源。

### 2. 通用核心不依赖生物学层级

正式 DataAsset 必须能够在没有 Species、Accession、Sample、Assembly 或 Annotation 的情况下创建、授权、关联文件和参与分析追溯。

普通正式 DataAsset 目标上必须归属于一个 Project。公共参考数据使用明确的公共参考 Project，不以空 Project 表示共享语义。历史回填期可以通过渐进 migration 暂时允许空值，但创建服务不得接受无 Project 的正式新数据。

### 3. 专业实体是可选扩展

`Assembly`、`Annotation`、`Sample`、`Accession` 等实体继续保存专业字段或研究对象信息，但不再形成第二份通用科研数据身份。

- DataAsset 保存 code、名称、版本、状态、可见性和类型/Profile 等通用身份；
- DataFile 保存路径、大小、格式、checksum 和内容版本；
- 专业实体保存各自领域字段；
- 重复通用字段只能通过渐进迁移停止活动使用，不得长期双写。

专业扩展的具体一对一或中间表结构由后续 ADR 决定。

### 4. DataFile 保持唯一物理文件身份

不得新增平行物理文件模型。DataAsset 与 DataFile 使用具有真实外键的显式成员关系，保存文件角色、顺序、primary 状态和必要的生命周期信息。

正式方案不得使用 `FileRelation(related_type="data_asset")`。现有 `DataFile.dataset` 与 `FileRelation(dataset)` 必须经过审计、映射和核对后迁移到唯一成员关系。

成员表的最终名称和完整约束由最小 schema ADR 决定，但至少满足：

- 关系两端使用真实外键；
- 能表达一个 DataAsset 的多个文件及其角色；
- 不复制 DataFile 的物理属性；
- 数据库能够阻止重复和悬空关系；
- primary 和顺序规则具有可验证约束。

### 5. 血缘与业务归属分离

真实派生必须表达：

```text
输入 DataAsset/DataFile -> AnalysisRun -> 输出 DataAsset/DataFile
```

`FileRelation` 不承载执行或派生语义。历史推断或人工关系必须携带证据类型，不能伪装成真实运行记录。AnalysisRun 的物理结构由独立 ADR 决定。

### 6. 权限和发布必须 fail closed

DataAsset 和 Project 将成为授权入口，DataFile 仍需逐文件重新授权。迁移后的有效权限不得比当前 Dataset + DataFile 决策更宽松。

- 无法解析继承策略时默认拒绝；
- 未发布、私有或受限资产不得因公开输出而泄露存在性或元数据；
- 所有上下游和 Manifest 节点逐节点授权；
- 权限、发布状态和共享模型由后续 ADR 细化。

### 7. Dataset 语义必须分流后再退役

Dataset 当前字段原则上映射到 DataAsset，但生产审计若证明存在独立 Collection、Release 或多资产 Manifest 语义，应建立职责明确的单独设计，不得以此为由长期保留 Dataset 作为第二份科研数据身份。

旧 `/datasets/` API 如需兼容，只能是有明确版本、截止日期、调用方和删除门槛的迁移适配层；适配层不得拥有数据或形成新写入链路。

### 8. 分阶段实施

实施顺序固定为：

1. 仓库调用面审计；
2. 生产数据只读审计；
3. 最小 schema、权限和 Collection/Release 子 ADR；
4. 新增结构和测试，不切换活动读写；
5. Dataset -> DataAsset dry-run 映射；
6. 分批、幂等回填和核对；
7. 一次性切换活动读写；
8. 生产验收和观察期；
9. 删除 Dataset 活动引用；
10. 通过新 migration 删除旧表并增加 CI 防回流检查。

不得在一个任务中同时完成 model、migration、API、Vue 和生产切换。

## 本 ADR 未批准的内容

以下内容仍需独立评审，不得从本 ADR 推断为已批准实现：

- DataAsset 的完整字段、数据库表名、索引和全部 constraint；
- Masterdata、Profile、Schema Registry 的最终物理模型；
- Project 成员、课题组、共享和公开数据的完整权限模型；
- Collection、Release、Manifest 是否需要独立实体；
- AnalysisRun、Run 参与关系和 AssetRelation 的最终表结构；
- Assembly、Annotation 与 DataAsset 的具体迁移顺序；
- 生产回填批次、维护窗口和旧 API 下线日期。

`docs/architecture/GeneData_通用科研数据仓库总体设计.md` 负责维护当前 active 总体设计；具体字段和物理结构仍须由子 ADR 批准。

## 被否决的方案

### Dataset 与 DataAsset 长期并存

否决。会形成两份身份、权限和发布事实来源，持续增加同步与维护成本。

### 直接把 Dataset 表或类重命名为 DataAsset

否决。无法处理双文件关系、访问策略、Accession、Manifest、固定类型 choices 和外部契约语义。

### 使用 FileRelation 扩展 DataAsset 文件成员

否决。字符串多态关系无法提供真实外键、删除保护和完整约束，会把当前兼容债务固化为核心架构。

### 强制所有 DataAsset 具有 Accession 或 Annotation

否决。会阻止显微图像、普通表格、质谱和其他课题组数据进入通用仓库。

### 一次性大迁移

否决。Dataset 参与权限、外部 API 和生产文件关系，必须支持 dry-run、批次、核对、回滚和独立生产验收。

## 影响

正向影响：

- 新数据类型不再要求新增核心身份模型；
- 物理文件、科研数据身份和专业实体职责清晰；
- 无 Accession/Annotation 数据可使用统一仓库；
- Dataset 退役有明确终点，不形成永久兼容层；
- 权限、版本和血缘可围绕唯一身份演进。

成本与风险：

- 需要迁移 79 个已识别代码调用文件中的相关语义；
- 需要核对两条 Dataset 文件关系路径；
- 需要保持外部 Manifest 和访问控制兼容性；
- 生产数据可能包含无法自动映射的 Collection/Release 或多 Dataset 文件关系；
- 删除 Dataset 前必须完成生产只读审计、备份、恢复验证和回滚审批。

## 实施 Gate

本 ADR 允许继续编写子 ADR、只读审计和分阶段实施计划，但在以下 Gate 完成前，不批准生产回填或活动读写切换：

- 生产 Dataset T0 只读审计；
- 最小 DataAsset schema/constraint ADR；
- 权限与发布状态 ADR；
- Collection/Release/Manifest 语义决策；
- Dataset 映射 dry-run、幂等和冲突清单；
- 回滚与生产验收方案。

## 相关文档

- `AGENTS.md`
- `docs/ACTIVE_DOCUMENTS.md`
- `docs/architecture/GeneData_通用科研数据仓库总体设计.md`
- `docs/audits/GeneData_Dataset到DataAsset实施前审计_20261118.md`
