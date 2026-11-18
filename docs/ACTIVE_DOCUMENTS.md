---
title: GeneData Active Documents
status: active
owner: 徐杨珂
last_reviewed: 2026-11-18
supersedes: null
---

# GeneData Active Documents

以下内容是当前项目允许作为实施依据的规则和文档。

| 主题 | 当前有效依据 | 状态 |
| --- | --- | --- |
| 仓库开发规则 | `/AGENTS.md` | active |
| 当前实现状态 | 代码、migration、测试和 CI | active |
| 文件管理主链路 | `DataFile + FileRelation` 当前实现 | active |
| DataAsset 统一科研数据身份 | `docs/adr/ADR-001-dataasset-unified-identity.md` | active |
| DataAsset 最小 schema、文件成员和发布边界 | `docs/adr/ADR-002-dataasset-minimum-schema.md` | active |
| DataAsset T3 新增结构实施 | `docs/architecture/GeneData_DataAsset_T3新增结构实施方案.md` | active |
| 通用科研数据仓库总体设计 | `docs/architecture/GeneData_通用科研数据仓库总体设计.md` | active |
| Dataset 到 DataAsset 代码审计 | `docs/audits/GeneData_Dataset到DataAsset实施前审计_20261118.md` | reference |
| API 使用与接口边界 | `docs/api_pages.md` | active |
| 开发、CI、部署与运维 | `docs/OPERATIONS.md` | active |
| Metadata TSV 数据准备 | `docs/metadata_tsv_source_guide.md` | active |
| 已知安全例外 | `docs/security_exceptions.md` | active |
| Dataset/DataFile 生产数据审计与迁移 | T0、T1 生产只读证据已核对；尚未回填或切换 | draft |
| GenomeFile 退役 | 当前代码与 `0025_delete_genomefile`；生产 migration 和数据状态独立验收 | active |
| 数据血缘模型 | 尚未批准最终模型 | draft |

未列入本表的历史实施方案、评审意见、阶段记录和发布执行单不能指导当前实现。需要追溯时使用 Git 历史；
新的长期文档必须替代或更新现有主题入口，不得再创建平行“最终版”。
