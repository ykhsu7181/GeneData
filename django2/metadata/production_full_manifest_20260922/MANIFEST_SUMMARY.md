# GeneData 生产全量 Manifest 摘要

- 固化日期：2026-09-22
- 源清单：`source_file_list_accession.txt`
- 源路径数：2,245
- Assembly：607
- Annotation：517
- 文件绑定：2,242
- 例外：29
- 人工验收：四份 Manifest 已由项目负责人确认
- 自动结构验收：PASS
- 生产文件实体验收：待生产服务器执行

## 文件说明

- `assemblies.full.tsv`：Accession 与 Assembly 绑定及 Assembly 元数据。
- `annotations.full.tsv`：Annotation 与 Assembly 绑定；`is_default` 明确默认版本。
- `files.full.tsv`：生产 `manual_files` 文件到层级实体的完整映射。
- `exceptions.full.tsv`：3 个非业务文件和 26 个数据库中存在、但源清单没有 genome 文件的 Accession。
- `ACCEPTANCE_REPORT.txt`：开发环境跨表结构验收结果。
- `SHA256SUMS`：本包输入与四份结果文件的防篡改校验值。

CG14 和 R498 的标准命名 GFF 为默认 Annotation；`IGDBv1.Allset` GFF 为非默认版本。

## 验收边界

当前 PASS 表示 TSV 表头、唯一键、跨表引用、Accession/Assembly 一致性、Annotation 默认版本和文件映射结构均正确。开发机没有生产 `manual_files` 实体，因此文件存在性、权限、大小与内容格式必须在生产服务器执行部署手册中的文件系统验收。
