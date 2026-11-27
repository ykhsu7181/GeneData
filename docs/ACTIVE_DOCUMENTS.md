---
title: GeneData Active Documents
status: active
owner: 徐杨珂
last_reviewed: 2026-11-27
supersedes: null
---

# GeneData Active Documents

以下内容是当前项目允许作为实施依据的规则和文档。

| 主题 | 当前有效依据 | 状态 |
| --- | --- | --- |
| 仓库开发规则 | `/AGENTS.md` | active |
| 当前实现状态 | 代码、migration、测试和 CI | active |
| 文件管理主链路 | `DataFile + FileRelation` 是当前遗留实现；新仓目标由 ADR-004 及空库代码审计决定 | active implementation fact；不是目标设计 |
| DataAsset 统一科研数据身份 | `docs/adr/ADR-001-dataasset-unified-identity.md` | active；旧数据迁移段落已被 ADR-004 替代，固定专业实体目标已被 ADR-005 修订 |
| DataAsset 最小 schema、文件成员和发布边界 | `docs/adr/ADR-002-dataasset-minimum-schema.md` | active；旧数据回填段落已被 ADR-004 替代，DataAssetAccession 目标已被 ADR-005 替代 |
| DataAsset T3 新增结构实施历史 | `docs/architecture/GeneData_DataAsset_T3新增结构实施方案.md` | reference；开发结果保留，固定专业关系目标已被 ADR-005 替代，生产未部署 |
| 通用科研数据仓库总体设计 | `docs/architecture/GeneData_通用科研数据仓库重新定位说明.md` | active；替代原总体设计 |
| 新仓空库启用与旧系统离线收口 | `docs/adr/ADR-004-greenfield-data-layer-and-legacy-archive.md` | active；旧数据库要求独立备份恢复，`manual_files` 原地保留且不保证恢复；未授权生产操作 |
| DataAsset 核心载荷与专业上下文边界 | `docs/adr/ADR-003-dataasset-payload-and-context-boundaries.md` | active；迁移实施段落已被 ADR-004 替代，固定专业实体关系目标已被 ADR-005 替代 |
| DataAsset 通用上下文、外部标识与 Project 授权 | `docs/adr/ADR-005-dataasset-context-identifiers-and-project-authorization.md` | active；阶段一开发与 CI 已于 2026-11-27 收口，阶段二至四、删除 migration 和生产验收未完成 |
| ADR-005 第一阶段新核心基础实施 | `docs/architecture/GeneData_ADR005_阶段一新核心基础实施方案.md` | reference；阶段一开发与 CI 已完成，未发生业务入口切换、生产部署或旧表删除 |
| ADR-005 第二阶段权限与保留能力切换 | `docs/architecture/GeneData_ADR005_阶段二权限与保留能力切换实施方案.md` | active；P0 已冻结；Gate A、Gate B 均已提交、推送且 CI 通过；Gate C 已获准进入、尚未完成；未授权生产部署或旧表删除 |
| ADR-005 第二阶段 P0 调用面处置矩阵 | `docs/audits/GeneData_ADR005_阶段二P0调用面处置矩阵_20261127.md` | active；基于 commit `1de5530`，规定阶段二各能力入口的唯一去向 |
| Dataset 到 DataAsset 代码审计 | `docs/audits/GeneData_Dataset到DataAsset实施前审计_20261118.md` | reference |
| ADR-004 G4 代码适用性与调用面审计 | `docs/audits/GeneData_ADR004_G4代码适用性与调用面审计_20261126.md` | reference；本地审计交付物完成，G2 隔离恢复和 G3 仍未验收，不授权删除或实施 |
| API 使用与接口边界 | `docs/api_pages.md` | active |
| 开发、CI、部署与运维 | `docs/OPERATIONS.md` | active |
| ADR-004 G1/G2 离线收口操作 | `docs/GeneData_ADR004_G1_G2离线收口操作清单.md` | active；文档评审通过，G1 已由生产输出验证；G2 备份、清单和隔离恢复仍待验收 |
| Metadata TSV 数据准备 | `docs/metadata_tsv_source_guide.md` | active |
| 已知安全例外 | `docs/security_exceptions.md` | active |
| 旧生产数据审计 | T0、T1、T4 生产只读证据作为历史决策依据保留；全量迁移、回填和切换路线已由 ADR-004 终止 | reference |
| GenomeFile 退役 | 当前代码与 `0025_delete_genomefile`；生产 migration 和数据状态独立验收 | active |
| 数据血缘模型 | 尚未批准最终模型 | draft |

未列入本表的历史实施方案、评审意见、阶段记录和发布执行单不能指导当前实现。需要追溯时使用 Git 历史；
新的长期文档必须替代或更新现有主题入口，不得再创建平行“最终版”。
