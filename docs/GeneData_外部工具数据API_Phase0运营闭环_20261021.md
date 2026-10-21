# GeneData 外部工具数据 API Phase 0 运营闭环

## 1. 实施基线与边界

- 实施分支：`feature/external-tool-data-api-v1`
- 固定基线：`feat/homepage-portal-redesign@efb1448b996b82fe31e9275563479fa5cd7003b9`
- 本阶段完成数据访问审计、SHA-256 回填、文件发布和 API Token 生命周期管理。
- 所有变更命令默认 dry-run；只有显式传入 `--apply` 才写数据库。
- 本阶段尚未提供 `/gd/api/v1/` HTTP 端点，也不代表 Nginx Range、限流和生产环境验证已经完成。

以下命令均在 `django2` 目录执行。正式执行前先完成数据库备份，并确认生产配置中的 `GENEDATA_PROTECTED_FILE_ROOTS` 指向真实数据根。

## 2. 迁移与只读审计

```powershell
python manage.py migrate --plan
python manage.py migrate
python manage.py audit_datafile_access --output-dir .artifacts/phase0-access-audit
```

审计命令不修改数据库。输出包括：

- 无 Dataset 文件数；
- inherited/private/internal/public 分布；
- 文件与 Dataset 策略冲突；
- 文件缺失或位于受保护根之外；
- SHA-256 缺失；
- genome FASTA 的 FAI 缺失或过期；
- ready/blocked 总数和逐文件 TSV 明细。

只有 TSV 中问题已解释或修复后，才进入回填和发布。

## 3. SHA-256 回填

先 dry-run：

```powershell
python manage.py backfill_datafile_sha256 `
  --dry-run `
  --batch-size 100 `
  --output-dir .artifacts/phase0-sha256
```

确认报告后执行：

```powershell
python manage.py backfill_datafile_sha256 `
  --apply `
  --batch-size 100 `
  --output-dir .artifacts/phase0-sha256
```

可用多个 `--data-file-id` 缩小范围。已有合法 SHA-256 的记录会跳过，因此中断后可安全重跑。命令在读取前后比较文件大小与纳秒级修改时间，并在入库前再次检查；发生变化的文件不会保存摘要。根外文件、缺失文件和读文件错误只记为失败项，不会阻止后续文件继续处理。

## 4. 清单式发布

发布清单使用 UTF-8 TSV：

```text
file_code	access_level	sha256
FILE000001	public	<64位SHA-256>
FILE000002	internal	<64位SHA-256>
```

`sha256` 列可留空，但正式发布建议填写，以固定本次批准的内容版本。`access_level` 只允许 `public` 或 `internal`。

先 dry-run：

```powershell
python manage.py publish_datafiles `
  --manifest public_files.tsv `
  --dry-run `
  --output-dir .artifacts/phase0-publication
```

通过后执行：

```powershell
python manage.py publish_datafiles `
  --manifest public_files.tsv `
  --published-by <Django用户名> `
  --apply `
  --output-dir .artifacts/phase0-publication
```

发布是整批原子操作。任一行存在文件不存在、非 current、根目录不合法、SHA-256 缺失或不匹配、Dataset 权限冲突、withdrawn 状态、FAI 缺失或过期等问题时，整批不写入。成功后写入 `access_level`、`publication_status=released`、`published_at` 和 `published_by`。

## 5. Token 生命周期

签发前预览，不会创建 Token：

```powershell
python manage.py issue_data_access_token `
  --name genescreen-prod `
  --scope metadata:read `
  --scope file:read `
  --access-tier public `
  --expires-in-hours 720 `
  --created-by <Django用户名> `
  --dry-run
```

正式签发：

```powershell
python manage.py issue_data_access_token `
  --name genescreen-prod `
  --scope metadata:read `
  --scope file:read `
  --access-tier public `
  --expires-in-hours 720 `
  --created-by <Django用户名> `
  --apply
```

明文 Token 只在该次命令输出中出现一次，数据库仅保存 HMAC-SHA256 摘要。不得把命令输出写入普通日志、Git 或工单正文。

查看 Token：

```powershell
python manage.py list_data_access_tokens
python manage.py list_data_access_tokens --include-inactive
```

撤销前预览并正式撤销：

```powershell
python manage.py revoke_data_access_token --token-prefix <前缀> --dry-run
python manage.py revoke_data_access_token --token-prefix <前缀> --apply
```

列表命令不显示明文或摘要；撤销后鉴权立即失效。

## 6. 完成判定与留证

每次生产操作保留命令版本、执行时间、操作者、stdout 和生成的 TSV，但签发 Token 的 stdout 必须进入受控凭证存储后立即清理。Phase 0 运营闭环完成需满足：

1. 迁移已应用且现有站点回归正常；
2. 审计报告中拟开放文件均为 ready；
3. SHA-256 apply 报告无未解释失败；
4. 发布 dry-run 与 apply 清单、数量一致；
5. Token 已设置最小 scope、合理有效期并完成保管；
6. 撤销演练证明旧 Token 立即失效。

开发环境已验证不等于生产已验证。生产数据库迁移、真实文件扫描、Nginx 和 HTTP API 验证须在对应阶段单独留证。
