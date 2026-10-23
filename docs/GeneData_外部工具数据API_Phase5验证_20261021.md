# GeneData 外部工具数据 API Phase 5 验证记录

日期：2026-10-21
分支：`feature/external-tool-data-api-v1`

## 完成内容

- OpenAPI 3.0.3 / API 1.0.0 契约覆盖 8 条 v1 路径，并声明 Bearer、Range、FASTA、TSV、1-based inclusive 和标准错误响应。
- `/gd/api/v1/openapi.json` 提供机器可读契约；`/docs/api/` 提供无外部 CDN 依赖的文档入口。
- 完成 curl、Python、R、Snakemake、Nextflow 使用示例。
- 完成 Token 签发/轮换/撤销、发布审计、监控告警、故障定位和回滚手册。
- 完成 Production Canary 执行单；生产目标仍缺实际 SSH 主机与维护窗口，未执行生产变更。

## 开发机验证

| 检查 | 结果 |
| --- | --- |
| OpenAPI JSON 语法 | PASS |
| OpenAPI 契约测试 | 2/2 PASS |
| Django system check | PASS |
| 全量 `files` 测试 | 470 PASS，1 skipped |
| migration drift | `No changes detected` |
| 实际 HTTP `/gd/api/v1/openapi.json` | 200；OpenAPI 3.0.3；API 1.0.0；8 paths |
| 实际 HTTP `/docs/api/` | 200；包含 schema 链接 |
| Phase 5 临时 Token 残留 | 0 |

受保护接口的当前分支真实 curl 基线沿用同日已归档记录：Dataset Manifest JSON/TSV 均为 200 且 3 个文件；FASTA Region `ASM_IR64/Chr01:1-120` 为 200 且 120 bp；FASTA/FAI 审计为 PASS。

## 生产只读探测

2026-10-21 从开发机访问：

- `https://riceome.hzau.edu.cn/`：HTTP 200，TLS 校验通过。
- `https://riceome.hzau.edu.cn/gd/api/v1/openapi.json`：HTTP 404。

结论：新 API 尚未部署到公开生产入口。仓库中的 SSH 目标仍为 `rdcheng@<production-host>`，因此当前状态为 `BLOCKED_BEFORE_PRODUCTION`；没有上传包、运行 migration、签发生产 Token、切换服务或修改生产数据。
