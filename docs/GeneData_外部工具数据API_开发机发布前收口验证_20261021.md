# GeneData 外部工具数据 API 开发机发布前收口验证

日期：2026-10-21

## 1. 新增能力

- `audit_external_api_readiness`：全材料只读暴露面审计，输出 summary、accessions、assemblies、datasets、files 五份 TSV；支持用稳定代码设置 `--require-*` 硬门禁。
- `publish_external_datasets`：基于 TSV 的 Dataset/Accession/FileRelation 事务式发布；默认 dry-run，校验稳定代码、SHA-256、文件公开就绪状态和元数据冲突，不删除既有关系。
- IR64 正式模板：DataFile 发布清单、Dataset 发布清单及后续材料空模板。
- 生产 HTTPS 设置：安全 Cookie 强制开启；SSL redirect、可信代理头和 HSTS 改为显式环境决策。
- 限流测试补充 `Retry-After`、Bearer Token 不回显和物理路径不泄漏断言。

## 2. 开发数据库全材料审计

报告目录：`D:\gene_manage_system\external_api_dev_readiness_20261021`

| 对象 | TOTAL | READY | 其他状态 |
| --- | ---: | ---: | --- |
| Accession | 633 | 633 | 无 |
| Assembly | 607 | 1 | AMBIGUOUS 472；MISSING_FILE 134 |
| Dataset | 290 | 1 | NOT_RELEASED 289 |
| DataFile | 154 | 3 | NOT_RELEASED 151 |

IR64 硬门禁结果：

- `FILE000013` FASTA：READY，匿名 metadata=yes，Token download=yes。
- `FAI_14`：READY，匿名 metadata=yes，Token download=yes。
- `FILE000001` GFF：READY，匿名 metadata=yes，Token download=yes。
- `DS_IR64_REFERENCE_V1`：READY，Manifest 3 files。
- `ASM_IR64`：READY，12 sequences。
- `required_blockers=0`。

审计报告字段及内容检查未发现 `file_path`、Windows/生产绝对路径或明文 Token。命令执行前后不修改数据库。

重要暴露面：Accession 基础元数据接口按设计允许匿名访问，因此部署 API 后 633 个 Accession 的 accession/species/sub_population/country/region 可被按已知 accession 查询；这不等同于它们的文件、Dataset 或 Region 已公开。目前完整文件数据面仍只有 IR64 达到 READY。

## 3. 发布清单演练

- DataFile dry-run：3 ready、0 blocked、0 applied。
- Dataset 第一次 dry-run 因模板名称与既有 Dataset 正式名称不一致而 3/3 blocked，未修改数据库。
- 修正为正式名称后：3 ready、0 blocked、0 applied。
- 自动化测试覆盖 dry-run、apply、重复 apply 幂等、SHA-256 错误整批阻断。

演练报告目录：`D:\gene_manage_system\external_api_dev_dryrun_20261021`。

## 4. 测试与近生产检查

| 检查 | 结果 |
| --- | --- |
| 新命令及安全定向测试 | 9/9 PASS |
| Management command 生命周期登记 | PASS |
| Django `files` 全量回归 | 476 tests，OK，1 skipped |
| Migration drift | `No changes detected` |
| OpenAPI JSON | PASS |
| `settings_production` 缺 Secret/DB password | 按预期 fail closed |
| `check --deploy`（一次性假凭证及显式 HTTPS/HSTS 开关） | PASS，0 issues |
| 开发机真实 HTTP 轻量检查 | 100/100 HTTP 200；2.101 s；47.59 req/s |

近生产配置检查只证明 settings 可正确加载，不代表生产 Nginx 已提供 `X-Forwarded-Proto`，也不构成启用 HSTS preload 的授权。实际值必须依据生产 `nginx -T` 证据决定。

## 5. 边界

- 没有生产数据库脱敏快照，因此未在开发机模拟生产对象数量；现有审计针对当前开发数据库。
- 没有修改 IR64 之外材料的发布状态。
- 没有推送分支、创建远端 tag 或连接生产 SSH。
- 生产 Nginx Range 206/416、数据库备份、migration、服务切换和 30 分钟观察仍必须在 Production Canary 中验证。
