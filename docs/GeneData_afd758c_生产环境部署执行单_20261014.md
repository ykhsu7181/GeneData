# GeneData afd758c 生产环境部署执行单

> 发布代码：`afd758cfa381c301190b78c6dbba29fb9b31f950`  
> 发布包：`GeneData_afd758c_20261014.zip`  
> 外层 SHA-256：`3eea9b5226edaf705b03b3244e37fd44b3cefcd79f35c76f30ab2f009a6cf34c`  
> 范围：发布“一键从注释结果定位 JBrowse”及其页面布局收口；先验证 Assembly 1400，再验证 Assembly 93。  
> 边界：不得修改 `manual_files`，不得顺带处理 32 条暂缓组装，不得在生产执行 `makemigrations`。

## 0. 执行顺序速查

| 顺序 | 执行端 | 操作 | 通过后进入 |
| ---: | --- | --- | --- |
| 1 | Windows 开发机 | 本地 SHA-256 复核并上传正式 ZIP 与 `.sha256` | 生产包校验 |
| 2 | 生产机维护账号 | 外层/包内哈希、源提交和 JBrowse 版本核对 | 只读预检 |
| 3 | 生产机维护账号 | PID、cwd、Python、settings、磁盘及权限核对 | 备份 |
| 4 | 生产机及数据库管理员 | 数据库、代码、前端、Nginx、JBrowse 和试点映射目录备份 | 新版本预检 |
| 5 | 生产机维护账号 | 准备不可变目录并运行新后端只读检查 | 维护窗口 |
| 6 | 生产机维护账号/Nginx 管理员 | 切换后端、前端、JBrowse alias 并重启服务 | 基础验收 |
| 7 | 生产机维护账号 | Assembly 1400 dry-run、审核、apply | 1400 全链路验收 |
| 8 | 浏览器/生产机 | Assembly 1400 全部通过 | Assembly 93 |
| 9 | 生产机维护账号 | Assembly 93 dry-run、审核、apply | 93 全链路验收 |
| 10 | 浏览器/生产机 | 旧功能回归并归档证据 | 发布完成 |

所有带 `实际...`、`<production-host>` 或 `实际生产域名` 的内容都必须先替换，禁止原样执行。数据库备份命令沿用生产环境已批准流程，本执行单不写入密码。

## 1. 发布门禁

开始维护窗口前必须满足：

1. 只上传正式 ZIP 和同名 `.sha256`，不得上传任何 `DO_NOT_DEPLOY` 文件。
2. 外层和包内哈希全部通过。
3. 已确认 GeneData 2025 服务的真实 PID、cwd、运行用户、Python 和 settings。
4. 数据库、活动后端、前端、Nginx 和 JBrowse Web 均有可读备份；数据库备份已记录大小和 SHA-256。
5. 新后端 `check` 通过，migration plan 已保存且不存在未评审迁移。
6. Assembly 1400、93 的文件关系和目标映射路径已只读核对。
7. 操作人、维护窗口、回滚人和生产域名已经确定。

任一门禁不满足即停止，不切换活动目录，不执行 `--apply`。

## 2. 路径和会话

以 GeneData 生产维护账号执行；不要在 root 的 tmux 中启动 Django。

```bash
tmux new -s genedata_afd758c

export GD_ROOT=/home/labuser/rdcheng/gd
export RELEASE_NAME=GeneData_afd758c_20261014
export UPLOAD_DIR="$GD_ROOT/uploads"
export STAGING_ROOT="$GD_ROOT/staging_afd758c_20261014"
export PACKAGE_ROOT="$STAGING_ROOT/$RELEASE_NAME"
export RELEASE_TS="$(date +%Y%m%d_%H%M%S)"
export BACKUP_ROOT="$GD_ROOT/backups/jbrowse_oneclick_afd758c_$RELEASE_TS"
export BACKEND_RELEASE="$GD_ROOT/releases/django2-afd758c"
export FRONTEND_RELEASE="$GD_ROOT/releases/dist-afd758c"
export JBROWSE_RELEASE="$GD_ROOT/releases/jbrowse2-v4.3.0-afd758c"
export AUDIT_ROOT="$GD_ROOT/audit_reports/jbrowse/oneclick_afd758c_$RELEASE_TS"

printf '%s\n' "$UPLOAD_DIR" "$STAGING_ROOT" "$PACKAGE_ROOT" \
  "$BACKUP_ROOT" "$BACKEND_RELEASE" "$FRONTEND_RELEASE" \
  "$JBROWSE_RELEASE" "$AUDIT_ROOT"
```

## 3. 上传、外层校验和解压

### 3.1 Windows 开发机复核

在 PowerShell 中执行：

```powershell
$ReleaseDir = 'D:\gene_manage_system\production_release_afd758c'
$ReleaseName = 'GeneData_afd758c_20261014'
$ExpectedSha256 = '3eea9b5226edaf705b03b3244e37fd44b3cefcd79f35c76f30ab2f009a6cf34c'
$ZipPath = Join-Path $ReleaseDir "$ReleaseName.zip"
$SidecarPath = "$ZipPath.sha256"

$ActualSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
if ($ActualSha256 -ne $ExpectedSha256) {
    throw "Release SHA-256 mismatch: $ActualSha256"
}

Get-Item -LiteralPath $ZipPath, $SidecarPath |
    Select-Object FullName, Length, LastWriteTime
```

只允许上传：

```text
GeneData_afd758c_20261014.zip
GeneData_afd758c_20261014.zip.sha256
```

不得上传同目录中任何以 `DO_NOT_DEPLOY` 开头的文件。

### 3.2 Windows 开发机上传

先将 `<production-host>` 替换为实际 SSH 主机名或 IP：

```powershell
$ProdSsh = 'rdcheng@<production-host>'
ssh $ProdSsh 'mkdir -p /home/labuser/rdcheng/gd/uploads'
scp $ZipPath $SidecarPath "${ProdSsh}:/home/labuser/rdcheng/gd/uploads/"
```

如果生产环境不允许直接 `scp`，使用批准的文件传输渠道，但生产落点仍为 `/home/labuser/rdcheng/gd/uploads/`，并在上传后重新校验。

### 3.3 生产机校验和解压

登录生产机并进入第 2 节创建的 tmux 会话，然后执行：

```bash
cd "$UPLOAD_DIR"
sha256sum -c "$RELEASE_NAME.zip.sha256"

test ! -e "$STAGING_ROOT"
mkdir -p "$STAGING_ROOT"
unzip -q "$UPLOAD_DIR/$RELEASE_NAME.zip" -d "$STAGING_ROOT"

cd "$PACKAGE_ROOT"
sha256sum -c SHA256SUMS | tee "$STAGING_ROOT/internal_sha256.txt"
cat RELEASE_INFO.txt
grep -Fx 'source_commit=afd758cfa381c301190b78c6dbba29fb9b31f950' RELEASE_INFO.txt
grep -Fx '4.3.0' jbrowse2-v4.3.0/version.txt
```

必须看到外层 `OK`、包内全部 `OK`、完整源提交和 JBrowse 4.3.0。失败即停止。

## 4. 生产只读预检

```bash
df -h "$GD_ROOT" "$GD_ROOT/manual_files" "$GD_ROOT/derived_data"
df -i "$GD_ROOT" "$GD_ROOT/manual_files" "$GD_ROOT/derived_data"
command -v unzip sha256sum bgzip tabix nginx
pgrep -af 'manage.py|gunicorn|uwsgi'
```

从输出人工确定唯一 GeneData 2025 服务 PID：

```bash
export GENEDATA_PID=实际GeneData_PID
pwdx "$GENEDATA_PID"
readlink -f "/proc/$GENEDATA_PID/exe"
ps -p "$GENEDATA_PID" -o user,pid,ppid,lstart,args
tr '\0' '\n' < "/proc/$GENEDATA_PID/environ" \
  | grep -E '^(CONDA_PREFIX|VIRTUAL_ENV|DJANGO_SETTINGS_MODULE|PYTHONPATH|GENEDATA_)='
export DJANGO_PYTHON="$(readlink -f "/proc/$GENEDATA_PID/exe")"
```

记录但不要输出密钥或数据库密码。必须确认 cwd 为实际活动后端、端口为 2025、settings 为 `filemanager.settings_production`，并记录当前生产代码身份。若活动目录是 Git 工作区，可执行：

```bash
git -C "$GD_ROOT/django2" rev-parse HEAD 2>/dev/null || true
```

## 5. 备份

```bash
mkdir -p "$BACKUP_ROOT" "$AUDIT_ROOT"
cp -a "$GD_ROOT/django2" "$BACKUP_ROOT/django2"
cp -a "$GD_ROOT/dist" "$BACKUP_ROOT/dist"
cp -a /home/Software/nginx/conf/nginx.conf "$BACKUP_ROOT/nginx.conf"

if [ -d "$GD_ROOT/releases/jbrowse2-v4.3.0" ]; then
  cp -a "$GD_ROOT/releases/jbrowse2-v4.3.0" \
    "$BACKUP_ROOT/jbrowse2-v4.3.0"
fi
```

使用现有已批准流程完成 MySQL 一致性备份，保存路径、大小、结束状态和 SHA-256。另行备份 Assembly 1400、93 将写入的映射文件目录；不存在时记录 `ABSENT_BEFORE_DEPLOY`，不要创建伪备份。

```bash
mkdir -p "$BACKUP_ROOT/jbrowse_pilot_assemblies"
for ASSEMBLY_ID in 1400 93; do
  SOURCE_DIR="$GD_ROOT/derived_data/jbrowse/assemblies/assembly-$ASSEMBLY_ID"
  if [ -d "$SOURCE_DIR" ]; then
    cp -a "$SOURCE_DIR" "$BACKUP_ROOT/jbrowse_pilot_assemblies/"
  else
    printf 'assembly-%s ABSENT_BEFORE_DEPLOY\n' "$ASSEMBLY_ID" \
      | tee -a "$BACKUP_ROOT/jbrowse_pilot_assemblies/absent.txt"
  fi
done

find "$GD_ROOT/derived_data/jbrowse/assemblies" \
  -maxdepth 2 -type f \
  \( -path '*/assembly-1400/*' -o -path '*/assembly-93/*' \) \
  -print | sort | tee "$BACKUP_ROOT/pilot_mapping_files_before.txt"
```

## 6. 准备不可变发布目录

```bash
test ! -e "$BACKEND_RELEASE"
test ! -e "$FRONTEND_RELEASE"
test ! -e "$JBROWSE_RELEASE"
mkdir -p "$GD_ROOT/releases"

cp -a "$PACKAGE_ROOT/django2" "$BACKEND_RELEASE"
cp -a "$PACKAGE_ROOT/dist" "$FRONTEND_RELEASE"
cp -a "$PACKAGE_ROOT/jbrowse2-v4.3.0" "$JBROWSE_RELEASE"

test -f "$BACKEND_RELEASE/manage.py"
test -f "$FRONTEND_RELEASE/index.html"
test -f "$JBROWSE_RELEASE/index.html"
grep -Fx '4.3.0' "$JBROWSE_RELEASE/version.txt"
sha256sum "$JBROWSE_RELEASE/plugins/genedata-responsive-layout.js"
```

插件哈希必须为：

```text
50f2abd3336ace2d7f68d9c7e1b7aca9430ae24e83f1d88cafcda666fb5a1421
```

## 7. 新后端只读检查

保留现有生产环境变量，包括数据库、密钥和 JBrowse 数据目录变量。不要把值写入记录。

```bash
cd "$BACKEND_RELEASE"
"$DJANGO_PYTHON" manage.py check \
  --settings=filemanager.settings_production
"$DJANGO_PYTHON" manage.py makemigrations --check --dry-run files \
  --settings=filemanager.settings_production
"$DJANGO_PYTHON" manage.py showmigrations --plan \
  --settings=filemanager.settings_production \
  | tee "$BACKUP_ROOT/migration_plan.txt"
```

本发布不应生成新的 migration。若出现未评审迁移或配置错误，停止部署；禁止在生产执行 `makemigrations`。

## 8. Nginx 准备

现有 `/jbrowse2/` alias 必须切换到：

```nginx
location /jbrowse2/ {
    alias /home/labuser/rdcheng/gd/releases/jbrowse2-v4.3.0-afd758c/;
}
```

受保护的 `manual_files` 和 `derived_data` internal location 保持原配置。修改后只测试，暂不 reload：

```bash
nginx -t
```

## 9. 维护窗口切换

使用已经确认的 tmux、systemd、supervisor 或其他真实进程管理方式停止且只停止 GeneData 2025 服务。确认原 PID 消失后：

```bash
cd "$GD_ROOT"
test ! -e "django2.pre_afd758c_$RELEASE_TS"
test ! -e "dist.pre_afd758c_$RELEASE_TS"

mv django2 "django2.pre_afd758c_$RELEASE_TS"
cp -a "$BACKEND_RELEASE" django2
mv dist "dist.pre_afd758c_$RELEASE_TS"
cp -a "$FRONTEND_RELEASE" dist

test -f "$GD_ROOT/django2/manage.py"
test -f "$GD_ROOT/dist/index.html"
cd "$GD_ROOT/django2"
"$DJANGO_PYTHON" manage.py check \
  --settings=filemanager.settings_production
```

使用原生产方式启动唯一 2025 服务，不额外启动第二个实例。随后由 Nginx 管理员执行：

```bash
nginx -t && nginx -s reload
```

## 10. 代码切换后的基础验收

```bash
curl -sS -o /dev/null -w 'assemblies HTTP %{http_code}\n' \
  http://127.0.0.1:2025/gd/api/files/assemblies/
curl -sS -o /dev/null -w 'jbrowse HTTP %{http_code}\n' \
  https://实际生产域名/jbrowse2/
curl -sS https://实际生产域名/jbrowse2/version.txt
```

预期 JBrowse HTTP 200、版本 4.3.0。浏览器强制刷新后确认新页面头和剩余视口自适应生效。

## 11. Assembly 1400 映射门禁

先只执行 dry-run，并保存完整 JSON：

```bash
cd "$GD_ROOT/django2"
"$DJANGO_PYTHON" manage.py backfill_jbrowse_refname_aliases \
  --assembly-id 1400 --dry-run \
  --settings=filemanager.settings_production \
  | tee "$AUDIT_ROOT/assembly-1400-dry-run.json"
```

只有同时满足以下条件才可 apply：

- `status=ready_for_build`；
- `write_performed=false`；
- `ambiguous_alias_count=0`；
- primary FASTA/FAI 唯一、可读且与当前索引一致；
- `planned_path` 位于 `$GD_ROOT/derived_data/jbrowse`；
- 引用数量和别名数量符合阶段 A 核对结果。

通过后执行：

```bash
"$DJANGO_PYTHON" manage.py backfill_jbrowse_refname_aliases \
  --assembly-id 1400 --apply \
  --settings=filemanager.settings_production \
  | tee "$AUDIT_ROOT/assembly-1400-apply.json"
```

立即验证：

1. 状态接口为 `ready`、`annotation_ready=true`、`location_ready=true`；
2. Annotation 查询返回正整数 `feature_id`；
3. 定位接口返回 IR64 的 `Chr01` 定位范围；
4. 配置中的 FASTA、FAI、GFF3.gz、TBI 分别返回 HTTP 206 和正确 `Content-Range`；
5. 页面显示正确 Annotation 轨道与目标特征，新窗口 URL 与 iframe 初始 URL 一致；
6. 返回后恢复原 accession、assembly、annotation、chromosome、分页和筛选上下文；
7. API 不泄露服务器物理路径。

定位接口格式：

```text
/gd/api/files/assemblies/1400/annotations/697/features/<feature_id>/jbrowse-location/
```

Assembly 1400 任一项失败即停止，不进入 Assembly 93。

## 12. Assembly 93 映射门禁

仅在 Assembly 1400 全部通过后执行同样流程：

```bash
"$DJANGO_PYTHON" manage.py backfill_jbrowse_refname_aliases \
  --assembly-id 93 --dry-run \
  --settings=filemanager.settings_production \
  | tee "$AUDIT_ROOT/assembly-93-dry-run.json"
```

确认 `ambiguous_alias_count=0` 且预期 `OriSeqID` 可唯一映射后：

```bash
"$DJANGO_PYTHON" manage.py backfill_jbrowse_refname_aliases \
  --assembly-id 93 --apply \
  --settings=filemanager.settings_production \
  | tee "$AUDIT_ROOT/assembly-93-apply.json"
```

按 Assembly 1400 的同一清单验收，并确认定位结果使用 `GWHESLA00000001`。任一异常停止扩展，不处理其他 Assembly。

## 13. 旧功能回归

浏览器中至少验证：

- 首页、品种搜索和 IR64 品种详情；
- Assembly 列表、Assembly 详情和相关文件；
- Annotation 表格与图形模式；
- 文件下载及 `Content-Disposition`；
- 无定位参数的普通 JBrowse 入口；
- Assembly 1248 仍为仅参考序列；
- Assembly 1216 仍保持未就绪保护；
- 中英文切换和移动端页面头。

## 14. 回滚

若代码或页面验收失败且尚未执行映射 apply：

1. 停止新 GeneData 2025 服务；
2. 恢复 `django2.pre_afd758c_$RELEASE_TS`；
3. 恢复 `dist.pre_afd758c_$RELEASE_TS`；
4. 恢复 `$BACKUP_ROOT/nginx.conf`，执行 `nginx -t` 后 reload；
5. 使用原方式启动服务并回归旧功能。

若已经执行 Assembly 1400 或 93 的 apply，除上述代码回滚外，还必须使用已校验的数据库备份和对应映射目录备份恢复一致状态。禁止临时 SQL、直接删除 `DataFile/FileRelation`、删除整个 `derived_data/jbrowse` 或修改 `manual_files`。

## 15. 最终验收记录

| 项目 | 状态 | 证据位置 |
| --- | --- | --- |
| 上传后外层 SHA-256 | 待生产执行 |  |
| 包内 1158 项 SHA-256 | 待生产执行 |  |
| 当前生产身份/PID/cwd | 待生产执行 |  |
| 数据库及目录备份 | 待生产执行 |  |
| 新后端 check/migration plan | 待生产执行 |  |
| Nginx 配置测试与 reload | 待生产执行 |  |
| 前端/JBrowse 4.3.0 | 待生产执行 |  |
| Assembly 1400 dry-run/apply | 待生产执行 |  |
| Assembly 1400 全链路 | 待生产执行 |  |
| Assembly 93 dry-run/apply | 待生产执行 |  |
| Assembly 93 全链路 | 待生产执行 |  |
| 旧功能回归 | 待生产执行 |  |
| 回滚材料 | 待生产执行 |  |

只有保存实际生产输出后，才能把对应状态改为 PASS。
