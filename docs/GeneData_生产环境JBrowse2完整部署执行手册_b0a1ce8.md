# GeneData 生产环境 JBrowse 2 完整部署执行手册（b0a1ce8）

## 1. 发布目标与证据边界

- 生产当前代码基线：`557aa17`。
- 本次目标提交：`b0a1ce81e0c57fd3519604e2f91a230dd4a3e2ee`。
- 目标分支：`feat/homepage-portal-redesign`。
- 生产根目录：`/home/labuser/rdcheng/gd`。
- 生产 Django 端口：`2025`。
- 生产设置：`filemanager.settings_production`。
- 生产原始文件目录：`/home/labuser/rdcheng/gd/manual_files`。
- JBrowse 衍生目录：`/home/labuser/rdcheng/gd/derived_data/jbrowse`。
- JBrowse Web 固定版本：`4.3.0`。

开发环境已经通过后端、前端、构建、脚本语法和 IR64 真实链路验证。生产代码切换、生产索引生成、Nginx reload、Range `206` 和页面验收在实际执行并保存输出前均属于待验证，不得提前标记为通过。

## 2. 发布包内容

发布包顶层目录为：

```text
GeneData_b0a1ce8_20260929/
├── django2/
├── dist/
├── jbrowse2-v4.3.0/
├── deploy/nginx/genedata-jbrowse2.conf.example
├── scripts/build_jbrowse2_web.sh
├── docs/PRODUCTION_DEPLOYMENT_RUNBOOK_b0a1ce8.md
├── RELEASE_INFO.txt
└── SHA256SUMS
```

发布包明确不包含：

- 数据库密码、`DJANGO_SECRET_KEY` 或 `.env`；
- `manual_files`、`derived_data`、数据库目录和日志；
- Python `.venv`、`node_modules`、开发运行状态；
- Windows 开发启动脚本；
- JBrowse 上游发布物中仅供演示和测试使用的 `test_data`；
- 未纳入 Git 的实验记录和临时材料。

`jbrowse2-v4.3.0` 保留 JBrowse Web 运行所需的 `index.html`、`static`、
`manifest.json`、字体和图标等资源；排除 `test_data` 不影响 GeneData 动态配置加载。

## 3. 强制安全原则

1. 不按端口直接停止进程。先核对 PID、工作目录、解释器、命令行和 tmux/进程管理归属。
2. 不覆盖或修改 `manual_files` 中的 FASTA、GFF 原始文件。
3. 新索引只写入 `derived_data/jbrowse`。
4. 后端和前端均使用完整新目录切换，不向活动目录零散复制文件。
5. 先验证发布包 SHA-256，再解压和切换。
6. `--apply` 前必须完成数据库备份；全量执行必须先完成 dry-run。
7. Nginx 配置只能由有权限的管理员修改，且必须先执行 `nginx -t`。
8. 保留旧代码、旧前端、数据库备份、审计报告和衍生索引，直至验收结束。

## 4. 开发机交付检查

在 PowerShell 中执行：

```powershell
cd D:\gene_manage_system\gene_manage_system

git rev-parse HEAD
git rev-list --left-right --count HEAD...origin/feat/homepage-portal-redesign

Get-FileHash `
  .\.artifacts\releases\GeneData_b0a1ce8_20260929.zip `
  -Algorithm SHA256

Get-Content `
  .\.artifacts\releases\GeneData_b0a1ce8_20260929.zip.sha256
```

预期：

- HEAD 为 `b0a1ce81e0c57fd3519604e2f91a230dd4a3e2ee`；
- 与远端分歧为 `0 0`；
- PowerShell 输出的 ZIP 哈希与 `.zip.sha256` 一致。

通过人工批准的传输方式上传以下两个文件，不要上传工作区目录：

```text
GeneData_b0a1ce8_20260929.zip
GeneData_b0a1ce8_20260929.zip.sha256
```

## 5. 生产只读预检

进入独立 tmux 会话：

```bash
tmux new -s genedata_b0a1ce8
```

设置本次操作变量：

```bash
export GD_ROOT=/home/labuser/rdcheng/gd
export RELEASE_NAME=GeneData_b0a1ce8_20260929
export UPLOAD_DIR="$GD_ROOT/uploads"
export STAGING_ROOT="$GD_ROOT/staging_b0a1ce8_20260929"
export PACKAGE_ROOT="$STAGING_ROOT/$RELEASE_NAME"
export RELEASE_TS="$(date +%Y%m%d_%H%M%S)"
export BACKUP_ROOT="$GD_ROOT/backups/jbrowse_b0a1ce8_$RELEASE_TS"
```

确认文件系统容量和 inode：

```bash
df -h "$GD_ROOT" "$GD_ROOT/manual_files"
df -i "$GD_ROOT" "$GD_ROOT/manual_files"
```

确认工具：

```bash
command -v unzip
command -v sha256sum
command -v bgzip
command -v tabix
command -v nginx

bgzip --version
tabix --version
nginx -v
```

确认生产进程归属：

```bash
pgrep -af 'manage.py|gunicorn|uwsgi'
```

从输出中人工确定 GeneData PID 后再执行：

```bash
export GENEDATA_PID=实际GeneData_PID
pwdx "$GENEDATA_PID"
readlink -f "/proc/$GENEDATA_PID/exe"
ps -p "$GENEDATA_PID" -o pid,ppid,lstart,args
tr '\0' '\n' < "/proc/$GENEDATA_PID/environ" \
  | grep -E '^(CONDA_PREFIX|VIRTUAL_ENV|DJANGO_SETTINGS_MODULE|PYTHONPATH)='
```

必须确认：工作目录属于 `/home/labuser/rdcheng/gd/django2`，端口为 `2025`，设置为 `filemanager.settings_production`。不得停止 `2029` 或其他项目进程。

## 6. 校验并解压发布包

```bash
cd "$UPLOAD_DIR"
sha256sum -c "$RELEASE_NAME.zip.sha256"

test ! -e "$STAGING_ROOT"
mkdir -p "$STAGING_ROOT"
unzip -q "$RELEASE_NAME.zip" -d "$STAGING_ROOT"

cd "$PACKAGE_ROOT"
sha256sum -c SHA256SUMS
cat RELEASE_INFO.txt
```

只有外层 ZIP 和逐文件校验均通过才能继续。

## 7. 备份与生产环境变量

创建备份目录：

```bash
mkdir -p "$BACKUP_ROOT"
cp -a "$GD_ROOT/django2" "$BACKUP_ROOT/django2"
cp -a "$GD_ROOT/dist" "$BACKUP_ROOT/dist"
```

由管理员备份实际 Nginx 配置：

```bash
cp -a /home/Software/nginx/conf/nginx.conf \
  "$BACKUP_ROOT/nginx.conf"
```

使用现有安全方式加载生产变量，禁止打印 Secret：

```bash
test -n "$DJANGO_SECRET_KEY"
test -n "$GENEDATA_DB_PASSWORD"

export GENEDATA_MANUAL_FILES_DIR="$GD_ROOT/manual_files"
export GENEDATA_DERIVED_DATA_DIR="$GD_ROOT/derived_data"
export GENEDATA_JBROWSE_DATA_DIR="$GD_ROOT/derived_data/jbrowse"
export GENEDATA_BGZIP_COMMAND=bgzip
export GENEDATA_TABIX_COMMAND=tabix
export GENEDATA_JBROWSE_MANUAL_INTERNAL_PREFIX=/_protected_manual_files/
export GENEDATA_JBROWSE_DERIVED_INTERNAL_PREFIX=/_protected_derived_data/
```

创建衍生目录并由管理员设置为“生产 Django 用户可写、Nginx 可读”；不得改变 `manual_files` 权限：

```bash
mkdir -p "$GD_ROOT/derived_data/jbrowse"
namei -l "$GD_ROOT/derived_data/jbrowse"
```

使用现有生产数据库备份流程执行一致性备份，并记录备份文件路径、大小和 SHA-256。不要把数据库密码写入命令历史、截图或手册。

## 8. 准备不可变发布目录

```bash
export BACKEND_RELEASE="$GD_ROOT/releases/django2-b0a1ce8"
export FRONTEND_RELEASE="$GD_ROOT/releases/dist-b0a1ce8"
export JBROWSE_RELEASE="$GD_ROOT/releases/jbrowse2-v4.3.0"

test ! -e "$BACKEND_RELEASE"
test ! -e "$FRONTEND_RELEASE"
test ! -e "$JBROWSE_RELEASE"

cp -a "$PACKAGE_ROOT/django2" "$BACKEND_RELEASE"
cp -a "$PACKAGE_ROOT/dist" "$FRONTEND_RELEASE"
cp -a "$PACKAGE_ROOT/jbrowse2-v4.3.0" "$JBROWSE_RELEASE"
chmod 0755 "$PACKAGE_ROOT/scripts/build_jbrowse2_web.sh"
```

确认 JBrowse 版本：

```bash
cat "$JBROWSE_RELEASE/version.txt"
test "$(tr -d '\r\n' < "$JBROWSE_RELEASE/version.txt")" = "4.3.0"
```

确认生产 Python；优先使用第 5 节从生产 PID 得到的解释器：

```bash
export DJANGO_PYTHON=/home/Software/anaconda3/envs/django2_env/bin/python3.9
"$DJANGO_PYTHON" -c 'import sys,django; print(sys.executable); print(django.get_version())'
```

对新后端执行只读检查：

```bash
cd "$BACKEND_RELEASE"
"$DJANGO_PYTHON" manage.py check --settings=filemanager.settings_production
"$DJANGO_PYTHON" manage.py showmigrations --plan \
  --settings=filemanager.settings_production > "$BACKUP_ROOT/migration_plan.txt"
```

本次提交未新增 migration，但仍必须保存实际 `showmigrations --plan` 输出。

## 9. 配置 Nginx

由管理员将发布包中的以下配置合并到 GeneData 所在 HTTPS `server` 块：

```text
deploy/nginx/genedata-jbrowse2.conf.example
```

必须保留：

```nginx
location /jbrowse2/ { ... }
location /_protected_manual_files/ { internal; ... }
location /_protected_derived_data/ { internal; ... }
```

不要覆盖现有 `/gb/` 和 `/gd/api/`。实际路径必须指向：

```text
/home/labuser/rdcheng/gd/releases/jbrowse2-v4.3.0/
/home/labuser/rdcheng/gd/manual_files/
/home/labuser/rdcheng/gd/derived_data/
```

先测试，不立即 reload：

```bash
nginx -t
```

## 10. 维护窗口切换代码

先通过已确认的 tmux 或进程管理方式停止且只停止 GeneData 2025 服务。停止后确认该 PID 消失，再切换目录：

```bash
cd "$GD_ROOT"

mv django2 "django2.pre_b0a1ce8_$RELEASE_TS"
cp -a "$BACKEND_RELEASE" django2

mv dist "dist.pre_b0a1ce8_$RELEASE_TS"
cp -a "$FRONTEND_RELEASE" dist
```

重新执行检查：

```bash
cd "$GD_ROOT/django2"
"$DJANGO_PYTHON" manage.py check --settings=filemanager.settings_production
```

通过原生产启动方式恢复 GeneData，示例命令仅用于核对参数：

```bash
"$DJANGO_PYTHON" manage.py runserver 0.0.0.0:2025 \
  --noreload --settings=filemanager.settings_production
```

不要在已有进程管理机制之外重复启动第二个 2025 服务。

后端 API 验证通过后，由管理员执行：

```bash
nginx -t && nginx -s reload
```

## 11. 代码切换后的只读验收

```bash
curl -sS -o /dev/null -w 'assemblies HTTP %{http_code}\n' \
  http://127.0.0.1:2025/gd/api/files/assemblies/

curl -sS -o /dev/null -w 'jbrowse HTTP %{http_code}\n' \
  https://生产域名/jbrowse2/

curl -sS https://生产域名/jbrowse2/version.txt
```

此时 IR64 未生成索引时，状态接口可以返回 `missing_fasta_index`，这不代表代码发布失败。

## 12. IR64 小批量生产验证

生产 IR64 Assembly ID 为 `1400`。先 dry-run：

```bash
cd "$GD_ROOT/django2"

"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --assembly-id 1400 --dry-run \
  --settings=filemanager.settings_production \
  > "$GD_ROOT/audit_reports/jbrowse/ir64_dry_run_$RELEASE_TS.json"
```

人工确认状态为 `ready_for_build` 或 `reference_only` 后再执行：

```bash
"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --assembly-id 1400 --apply \
  --settings=filemanager.settings_production \
  > "$GD_ROOT/audit_reports/jbrowse/ir64_apply_$RELEASE_TS.json"
```

验证：

```bash
curl -sS https://生产域名/gd/api/files/assemblies/1400/jbrowse-status/
curl -sS https://生产域名/gd/api/files/assemblies/1400/jbrowse-config/
```

从配置 JSON 中取得 FASTA、FAI、GFF3.gz 和 TBI 的 `browser-assets` URL，逐一验证：

```bash
curl -sS -D - -o /dev/null \
  -H 'Range: bytes=0-99' \
  https://生产域名/gd/api/files/browser-assets/实际文件ID/
```

预期为 `206 Partial Content`、`Content-Range: bytes 0-99/...`。浏览器中从 IR64 Assembly 详情页进入，验证参考序列、注释轨道、坐标跳转、缩放和 feature 点击。

## 13. 全量分批 dry-run

首次和后续均使用同一命令，checkpoint 不存在时会自动创建：

```bash
mkdir -p "$GD_ROOT/audit_reports/jbrowse"

"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --all --dry-run --batch-size 20 --resume \
  --report-dir "$GD_ROOT/audit_reports/jbrowse" \
  --settings=filemanager.settings_production
```

重复执行，直到：

```text
remaining_count = 0
failed_checkpoint_count = 0
```

若存在失败，先根据 TSV/JSON 修复数据或关系，再执行：

```bash
"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --all --dry-run --batch-size 20 --resume --retry-failed \
  --report-dir "$GD_ROOT/audit_reports/jbrowse" \
  --settings=filemanager.settings_production
```

不得因为 `remaining_count=0` 就忽略 `failed_checkpoint_count`。

## 14. 全量分批 apply

只有全量 dry-run 审核完成后才能执行：

```bash
"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --all --apply --batch-size 10 --resume \
  --report-dir "$GD_ROOT/audit_reports/jbrowse" \
  --settings=filemanager.settings_production
```

每批检查磁盘、服务状态、JSON/TSV 报告和错误日志。失败项修复后使用：

```bash
"$DJANGO_PYTHON" manage.py build_jbrowse_indexes \
  --all --apply --batch-size 10 --resume --retry-failed \
  --report-dir "$GD_ROOT/audit_reports/jbrowse" \
  --settings=filemanager.settings_production
```

全量完成条件仍然是 `remaining_count=0` 且 `failed_checkpoint_count=0`。没有 Annotation 的 Assembly 可以合法完成为参考序列浏览；不能将其记为带注释浏览。

## 15. 回滚

### 15.1 尚未执行任何索引 apply

1. 通过已确认的原启动方式停止 GeneData。
2. 恢复 `django2.pre_b0a1ce8_$RELEASE_TS` 和 `dist.pre_b0a1ce8_$RELEASE_TS`。
3. 恢复 `$BACKUP_ROOT/nginx.conf`。
4. 执行 `nginx -t` 后 reload。
5. 使用原命令重新启动 2025 服务。
6. 验证原接口和页面。

### 15.2 已执行索引 apply

除代码和 Nginx 回滚外，还必须依据本次数据库备份和审计报告决定是否恢复数据库。不要直接删除 `derived_data`：文件和数据库关系必须保持一致。衍生文件应先保留，待回滚验收和依赖审计完成后再决定是否归档。

## 16. 最终验收记录

| 项目 | 状态 | 证据 |
|---|---|---|
| 外层 ZIP SHA-256 | 待执行 | `.zip.sha256` 输出 |
| 包内逐文件 SHA-256 | 待执行 | `sha256sum -c SHA256SUMS` |
| 数据库备份 | 待执行 | 路径、大小、SHA-256 |
| 后端 check | 待执行 | 命令输出 |
| 生产 API | 待执行 | HTTP 状态 |
| JBrowse 4.3.0 静态页面 | 待执行 | version.txt、HTTP 200 |
| IR64 索引 | 待执行 | dry-run/apply JSON |
| IR64 Range | 待执行 | 四类资源 HTTP 206 |
| IR64 页面 | 待执行 | 浏览器验收记录 |
| 全量 dry-run | 待执行 | checkpoint、JSON、TSV |
| 全量 apply | 待执行 | checkpoint、JSON、TSV |
| 旧功能回归 | 待执行 | Assembly、Annotation、下载 |
| 回滚材料保留 | 待执行 | 备份目录清单 |

只有完成实际生产验证后，才能把相应项目改为 `PASS`。
