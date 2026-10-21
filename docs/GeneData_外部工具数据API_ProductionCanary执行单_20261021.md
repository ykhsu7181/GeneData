# GeneData 外部工具数据 API v1 Production Canary 执行单

状态：**生产执行未开始**。本文已完成开发机可执行设计；生产 SSH 仍为 `rdcheng@<production-host>` 占位符，实际主机、维护窗口、数据库备份命令和服务重启方式尚未提供。严禁原样执行占位命令。

## 1. Canary 范围

- 只发布 API 后端、OpenAPI/运维文档及必要 migration；不改前端。
- 试点对象：IR64、Assembly `ASM_IR64`、Dataset `DS_IR64_REFERENCE_V1`。
- 预期文件代码应在生产只读预检中由关系查询确认；不得直接套用开发库主键 14/147/2。
- 流量仅限单个 2 小时 Canary Token；验收结束立即撤销。

## 2. 候选包证据（打包后填写）

| 项目 | 实际值 |
| --- | --- |
| Git branch | `feature/external-tool-data-api-v1` |
| Git commit | `PENDING_PACKAGE_BUILD` |
| ZIP | `PENDING_PACKAGE_BUILD` |
| ZIP SHA-256 | `PENDING_PACKAGE_BUILD` |
| 包内清单 | `PENDING_PACKAGE_BUILD` |
| 开发机测试 | `PENDING_FINAL_VERIFICATION` |

候选包必须从 clean detached worktree 生成，不得直接压缩当前脏工作区。

## 3. 生产只读预检

```bash
export GD_ROOT=/home/labuser/rdcheng/gd
export CANARY_TS="$(date +%Y%m%d_%H%M%S)"
export AUDIT_ROOT="$GD_ROOT/audit_reports/external_api/canary_$CANARY_TS"
export BACKUP_ROOT="$GD_ROOT/backups/external_api_canary_$CANARY_TS"
mkdir -p "$AUDIT_ROOT"

df -h "$GD_ROOT" "$GD_ROOT/manual_files" "$GD_ROOT/derived_data"
df -i "$GD_ROOT" "$GD_ROOT/manual_files" "$GD_ROOT/derived_data"
pgrep -af 'manage.py|gunicorn|uwsgi'
nginx -T > "$AUDIT_ROOT/nginx_before.txt"
```

记录并人工确认唯一活动服务的 PID、cwd、Python、用户、settings 与端口。确认 `/home/labuser/rdcheng/gd` 是预期根目录后，才可进入备份。另需从 `nginx -T` 证据确认 HTTP→HTTPS 跳转和 `X-Forwarded-Proto`；未确认时不得启用 Django SSL redirect 或 HSTS。

## 4. 备份门禁

```bash
mkdir -p "$BACKUP_ROOT"
cp -a "$GD_ROOT/django2" "$BACKUP_ROOT/django2"
cp -a /home/Software/nginx/conf/nginx.conf "$BACKUP_ROOT/nginx.conf"
sha256sum "$BACKUP_ROOT/nginx.conf" | tee "$AUDIT_ROOT/nginx_backup.sha256"
```

使用当前已批准的 MySQL 一致性备份流程，记录备份文件绝对路径、大小、完成状态和 SHA-256。没有数据库备份证据即停止。

## 5. 候选版本离线检查

解压到新的不可变目录，不覆盖活动目录。使用活动服务相同 Python：

```bash
cd '<new-backend-release>/django2'
export DJANGO_SETTINGS_MODULE=filemanager.settings_production
'<production-python>' manage.py check --deploy --settings=filemanager.settings_production
'<production-python>' manage.py showmigrations files
'<production-python>' manage.py migrate --plan --settings=filemanager.settings_production \
  | tee "$AUDIT_ROOT/migrate_plan.txt"
```

人工确认 migration plan 后才能在维护窗口执行 `migrate`。不得执行 `makemigrations`。

## 6. Nginx 与服务切换

合并 `deploy/nginx/genedata-jbrowse2.conf.example` 中两个 internal protected location，逐项确认 alias。执行：

```bash
nginx -t
# 使用生产环境既有、已批准的服务切换/重启命令
curl --fail-with-body --silent --show-error \
  'https://riceome.hzau.edu.cn/gd/api/v1/openapi.json' \
  -o "$AUDIT_ROOT/openapi.json"
```

不得猜测 systemd/tmux 命令；实际重启方式必须由生产服务所有者填写。

## 7. 数据状态与 Token

在生产库按 `file_code`/关系核对 IR64 FASTA、FAI、GFF；仅当三者已处于批准发布状态时继续。若需发布，使用批准 TSV 先 dry-run 后 `--apply`，并保存报告。

```bash
cd '<active-backend>/django2'
'<production-python>' manage.py audit_public_fasta_indexes --assembly ASM_IR64 \
  | tee "$AUDIT_ROOT/fasta_index_audit.txt"
'<production-python>' manage.py list_data_access_tokens --include-inactive \
  > "$AUDIT_ROOT/token_inventory.tsv"
```

使用 `metadata/external_api_release_template/` 中的 IR64 清单分别执行 DataFile 和 Dataset dry-run；确认 SHA-256、稳定代码及报告无 blocker 后，才能在批准窗口使用 `--apply`。随后执行全材料只读审计，并使用 `--require-*` 参数为 IR64 设置硬门禁。其他材料只盘点，不自动发布。

确认 Dataset `DS_IR64_REFERENCE_V1` 为 public/released 且只关联批准文件。随后按运维手册签发 2 小时 Token，将明文只存 Secret Manager，并在当前 shell 中安全注入 `GENEDATA_TOKEN`。

## 8. HTTP Canary 验收

```bash
export BASE_URL=https://riceome.hzau.edu.cn

curl --fail-with-body --silent --show-error \
  "$BASE_URL/gd/api/v1/accessions/IR64/" \
  -D "$AUDIT_ROOT/accession.headers" -o "$AUDIT_ROOT/accession.json"

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$BASE_URL/gd/api/v1/datasets/DS_IR64_REFERENCE_V1/manifest/" \
  -D "$AUDIT_ROOT/manifest.headers" -o "$AUDIT_ROOT/manifest.json"

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$BASE_URL/gd/api/v1/datasets/DS_IR64_REFERENCE_V1/manifest.tsv" \
  -D "$AUDIT_ROOT/manifest_tsv.headers" -o "$AUDIT_ROOT/manifest.tsv"

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$BASE_URL/gd/api/v1/assemblies/ASM_IR64/sequence/?sequence=Chr01&start=1&end=120" \
  -D "$AUDIT_ROOT/region.headers" -o "$AUDIT_ROOT/region.fa"
```

从 Manifest 读取生产 `content_url`，执行完整 GET=200、合法 Range=206、越界 Range=416。保存响应头与内容 SHA-256；不得把 Token 写入证据文件。

通过标准：OpenAPI 200；accession 200；JSON/TSV 200 且三文件身份、角色和校验和符合批准基线；Region 200、120 bp、坐标头正确；文件 200/206/416 全部符合；响应不得出现物理路径。

## 9. 观察、撤销与结论

保持 Canary 单流量 30 分钟，检查 5xx、409、429、延迟、磁盘和 Django/Nginx 错误日志。任一回滚条件触发即按运维手册回滚。

验收后立即撤销 Canary Token，并验证旧 Token 请求返回 403。将以下结论之一写入执行记录：

- `PASS_PRODUCTION_CANARY`：所有门禁、HTTP 检查、观察期和 Token 撤销均有证据。
- `ROLLED_BACK`：记录触发条件、回滚时间和回归结果。
- `BLOCKED_BEFORE_PRODUCTION`：未改生产；记录缺失的主机、窗口、备份或权限。

当前结论：`BLOCKED_BEFORE_PRODUCTION`（生产 SSH 主机为占位符，尚未产生任何生产变更）。
