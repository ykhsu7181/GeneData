---
title: GeneData ADR-004 G1/G2 离线收口操作清单
status: active
owner: 徐杨珂
last_reviewed: 2026-11-25
supersedes: null
---

# GeneData ADR-004 G1/G2 离线收口操作清单

## 1. 适用范围

本文只执行 ADR-004 的：

- **G1**：停止项目负责人的旧系统测试写入，确认没有其他用户或计划内写入，并记录统一截止时间；
- **G2**：把旧数据库备份到独立存储，生成原地 `manual_files` 文件清单，并保存代码和 migration 状态。

本文不授权停止旧服务、停止共享数据库实例、修改数据库权限、递归修改 `manual_files` 权限、删除旧数据、创建新仓生产库或部署新代码。停止旧前端、后端和定时任务属于 G3，必须另行批准。

`manual_files` 不制作完整副本，不计算全部 757G 文件的内容校验值。清单只登记相对路径、大小和修改时间；数据库已有 SHA-256 另行导出。以后重新接收某个旧文件时，再计算源文件和新仓副本的 SHA-256。

## 2. 数据库备份目录

本次数据库备份目录确定为：

```bash
DB_BACKUP_ROOT=/var/backups/genedata-legacy
```

该目录由管理员创建为 `0700`、所有者 `rdcheng:labuser`。2026-11-25 现场检查显示，MySQL `@@datadir` 位于 `/dev/mapper/centos-home`，备份目录位于 `/dev/sda2`，后者当时可用空间为 636G。该结果属于现场证据，重新执行时仍须由 G2 命令再次核验，不能把历史结果当成当前事实。

## 3. 进入现有 tmux 会话

在普通 SSH 提示符执行：

```bash
tmux new-session -A -s dataset-t0-audit
```

以下命令都在该会话中执行。不要使用顶层 `exit`、`logout`、`exec` 或 `set -e`；每个函数失败后都会返回当前提示符，不会关闭 tmux 会话。

## 4. G1：确认真实生产进程并冻结测试写入

先停止所有手工上传、删除、编辑和测试操作，然后复制执行：

```bash
g1_prepare() {
  BASE=/home/labuser/rdcheng/gd
  MANUAL_ROOT="$BASE/manual_files"
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  EVIDENCE_DIR="$BASE/legacy_archive/g1-g2-$STAMP"

  BACKEND_PID=
  for pid in $(pgrep -f gunicorn); do
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null) || continue
    case "$cmd" in
      *filemanager.wsgi*2025*|*2025*filemanager.wsgi*) BACKEND_PID=$pid; break ;;
    esac
  done
  [ -n "$BACKEND_PID" ] || { echo 'G1失败：未找到生产 Gunicorn'; return 1; }
  [ -r "/proc/$BACKEND_PID/environ" ] || { echo 'G1失败：无法读取生产进程环境'; return 1; }

  BACKEND_CWD=$(readlink -f "/proc/$BACKEND_PID/cwd")
  PYTHON_BIN=$(readlink -f "/proc/$BACKEND_PID/exe")
  case "$BACKEND_CWD" in "$BASE"/releases/*) ;; *) echo "G1失败：目录不是生产 release：$BACKEND_CWD"; return 1;; esac
  tr '\0' '\n' < "/proc/$BACKEND_PID/environ" | grep -qx 'DJANGO_SETTINGS_MODULE=filemanager.settings_production' || {
    echo 'G1失败：不是 production settings'; return 1;
  }
  ss -lntp 2>/dev/null | grep -q "pid=$BACKEND_PID," || {
    echo 'G1失败：该进程没有生产监听端口'; return 1;
  }

  while IFS= read -r -d '' item; do
    case "$item" in
      DJANGO_SECRET_KEY=*|GENEDATA_DB_*=*|GENEDATA_MANUAL_FILES_DIR=*|DJANGO_SETTINGS_MODULE=*) export "$item" ;;
    esac
  done < "/proc/$BACKEND_PID/environ"

  [ -n "${GENEDATA_DB_PASSWORD:-}" ] || { echo 'G1失败：生产进程没有数据库密码环境变量'; return 1; }
  for name in GENEDATA_DB_HOST GENEDATA_DB_PORT GENEDATA_DB_USER GENEDATA_DB_NAME; do
    [ -n "${!name:-}" ] || { echo "G1失败：生产进程缺少 $name"; return 1; }
  done
  MANUAL_ROOT=${GENEDATA_MANUAL_FILES_DIR:-$MANUAL_ROOT}
  [ -d "$MANUAL_ROOT" ] || { echo "G1失败：manual_files不存在：$MANUAL_ROOT"; return 1; }
  read -r -p '确认已停止本人全部测试写入，且没有其他用户或自动写入（输入 YES）：' CONFIRM
  CONFIRM=${CONFIRM//$'\r'/}
  CONFIRM=${CONFIRM//[[:space:]]/}
  [ "$CONFIRM" = YES ] || { echo 'G1停止：未确认写入冻结'; return 1; }

  umask 077
  install -d -m 700 "$EVIDENCE_DIR" || return 1
  (
    cd "$BACKEND_CWD" &&
    "$PYTHON_BIN" manage.py shell --settings=filemanager.settings_production \
      -c "from django.db import connection; connection.ensure_connection(); print('database_preflight=OK')"
  ) || { echo 'G1失败：数据库预检失败'; return 1; }
  (
    cd "$BACKEND_CWD" &&
    "$PYTHON_BIN" manage.py showmigrations --plan --settings=filemanager.settings_production \
      > "$EVIDENCE_DIR/migrations.txt"
  ) || { echo 'G1失败：migration状态读取失败'; return 1; }

  {
    echo "release_dir=$(basename "$BACKEND_CWD")"
    if git -C "$BACKEND_CWD" rev-parse --verify HEAD >/dev/null 2>&1; then
      echo "git_commit=$(git -C "$BACKEND_CWD" rev-parse HEAD)"
    else
      echo 'git_commit=not_available_in_release_directory'
    fi
  } > "$EVIDENCE_DIR/release_identity.txt"

  {
    echo "cutoff_utc=$STAMP"
    echo "backend_pid=$BACKEND_PID"
    echo "backend_cwd=$BACKEND_CWD"
    echo "python=$PYTHON_BIN"
    echo 'settings=filemanager.settings_production'
    echo "manual_files=$MANUAL_ROOT"
    echo 'test_writes_frozen=yes'
  } > "$EVIDENCE_DIR/cutoff.env"

  export BASE MANUAL_ROOT STAMP EVIDENCE_DIR BACKEND_PID BACKEND_CWD PYTHON_BIN
  echo "G1完成：$EVIDENCE_DIR"
}

g1_prepare <<< "YES"
echo "G1返回码：$?"
```

只有看到 `G1返回码：0` 才继续。该步骤不会关闭仍在线的旧服务；因为已确认旧系统只有项目负责人测试使用，所以采用管理性冻结。如果发现其他用户、自动上传、定时任务或任何继续写入，立即停止，G1 不通过。

## 5. G2-A：把旧数据库备份到独立存储

确认第 2 节目录已经创建并执行：

```bash
g2_database_backup() {
  [ -n "${EVIDENCE_DIR:-}" ] || { echo 'G2失败：请先完成G1'; return 1; }
  [ -d "${DB_BACKUP_ROOT:-}" ] || { echo 'G2失败：独立备份目录不存在'; return 1; }

  for cmd in mysql mysqldump gzip sha256sum findmnt; do
    command -v "$cmd" >/dev/null || { echo "G2失败：缺少 $cmd"; return 1; }
  done

  DB_DATA_DIR=$(MYSQL_PWD="$GENEDATA_DB_PASSWORD" mysql \
    -h "$GENEDATA_DB_HOST" -P "$GENEDATA_DB_PORT" -u "$GENEDATA_DB_USER" -NBe \
    'SELECT @@datadir') || { echo 'G2失败：无法读取MySQL数据目录'; return 1; }
  [ -d "$DB_DATA_DIR" ] || { echo "G2失败：当前主机无法核验MySQL数据目录：$DB_DATA_DIR"; return 1; }
  DB_FS=$(findmnt -no SOURCE --target "$DB_DATA_DIR") || return 1
  BACKUP_FS=$(findmnt -no SOURCE --target "$DB_BACKUP_ROOT") || return 1
  [ "$DB_FS" != "$BACKUP_FS" ] || { echo 'G2失败：数据库备份与MySQL数据目录位于同一文件系统'; return 1; }
  echo "MySQL数据文件系统：$DB_FS"
  echo "数据库备份文件系统：$BACKUP_FS"

  NON_INNODB=$(MYSQL_PWD="$GENEDATA_DB_PASSWORD" mysql \
    -h "$GENEDATA_DB_HOST" -P "$GENEDATA_DB_PORT" -u "$GENEDATA_DB_USER" -NBe \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${GENEDATA_DB_NAME}' AND table_type='BASE TABLE' AND engine<>'InnoDB'") || {
      echo 'G2失败：无法检查存储引擎'; return 1;
    }
  [ "$NON_INNODB" -eq 0 ] || { echo "G2失败：存在 $NON_INNODB 张非InnoDB表，不能使用当前一致性备份命令"; return 1; }

  DB_BACKUP_DIR="$DB_BACKUP_ROOT/$GENEDATA_DB_NAME-$STAMP"
  install -d -m 700 "$DB_BACKUP_DIR" || return 1
  SCHEMA="$DB_BACKUP_DIR/${GENEDATA_DB_NAME}_schema.sql.gz"
  FULL="$DB_BACKUP_DIR/${GENEDATA_DB_NAME}_full.sql.gz"

  MYSQL_PWD="$GENEDATA_DB_PASSWORD" mysqldump \
    -h "$GENEDATA_DB_HOST" -P "$GENEDATA_DB_PORT" -u "$GENEDATA_DB_USER" \
    --no-tablespaces --routines --triggers --events --no-data \
    "$GENEDATA_DB_NAME" | gzip -1 > "$SCHEMA.part"
  RC=("${PIPESTATUS[@]}")
  [ "${RC[0]}" -eq 0 ] && [ "${RC[1]}" -eq 0 ] || { echo 'G2失败：结构备份失败'; return 1; }
  mv "$SCHEMA.part" "$SCHEMA" || return 1

  MYSQL_PWD="$GENEDATA_DB_PASSWORD" mysqldump \
    -h "$GENEDATA_DB_HOST" -P "$GENEDATA_DB_PORT" -u "$GENEDATA_DB_USER" \
    --no-tablespaces --single-transaction --quick --routines --triggers --events \
    "$GENEDATA_DB_NAME" | gzip -1 > "$FULL.part"
  RC=("${PIPESTATUS[@]}")
  [ "${RC[0]}" -eq 0 ] && [ "${RC[1]}" -eq 0 ] || { echo 'G2失败：完整备份失败'; return 1; }
  mv "$FULL.part" "$FULL" || return 1

  gzip -t "$SCHEMA" "$FULL" || { echo 'G2失败：gzip校验失败'; return 1; }
  (cd "$DB_BACKUP_DIR" && sha256sum "$(basename "$SCHEMA")" "$(basename "$FULL")" > SHA256SUMS) || return 1
  cp "$EVIDENCE_DIR/cutoff.env" "$DB_BACKUP_DIR/"
  chmod 400 "$SCHEMA" "$FULL" "$DB_BACKUP_DIR/SHA256SUMS" "$DB_BACKUP_DIR/cutoff.env"

  export DB_BACKUP_DIR
  echo "数据库备份完成：$DB_BACKUP_DIR"
}

g2_database_backup
echo "数据库备份返回码：$?"
```

完整备份可能长时间没有终端输出，这是 `mysqldump | gzip` 的正常表现。需要查看进度时，在 tmux 中按 `Ctrl-b`、再按 `c` 新建窗口，然后对实际备份目录执行：

```bash
watch -n 10 'du -sh /var/backups/genedata-legacy/* 2>/dev/null'
```

不要因为暂时没有输出而中断数据库备份。

## 6. G2-B：生成 `manual_files` 元数据清单

返回原 tmux 窗口，执行：

```bash
g2_manual_manifest() {
  [ -n "${EVIDENCE_DIR:-}" ] || { echo 'G2失败：请先完成G1'; return 1; }
  [ -n "${DB_BACKUP_DIR:-}" ] || { echo 'G2失败：请先完成数据库备份'; return 1; }
  MANIFEST="$EVIDENCE_DIR/manual_files.tsv"
  KNOWN_SHA="$EVIDENCE_DIR/datafile_known_sha256.tsv"

  if find "$MANUAL_ROOT" -xdev -type f \( -name $'*\t*' -o -name $'*\n*' \) -print -quit | grep -q .; then
    echo 'G2失败：存在带制表符或换行的文件名，不能安全生成TSV'; return 1
  fi

  printf 'relative_path\tsize_bytes\tmtime\n' > "$MANIFEST.tmp"
  find "$MANUAL_ROOT" -xdev -type f \
    -printf '%P\t%s\t%TY-%Tm-%TdT%TH:%TM:%TS%Tz\n' | LC_ALL=C sort >> "$MANIFEST.tmp"
  RC=("${PIPESTATUS[@]}")
  [ "${RC[0]}" -eq 0 ] && [ "${RC[1]}" -eq 0 ] || { echo 'G2失败：文件扫描失败'; return 1; }
  mv "$MANIFEST.tmp" "$MANIFEST"

  (
    cd "$BACKEND_CWD" &&
    "$PYTHON_BIN" manage.py shell --settings=filemanager.settings_production -c \
      "import csv,sys; from files.models import DataFile; w=csv.writer(sys.stdout,delimiter='\t',lineterminator='\n'); w.writerow(('file_path','file_size','sha256')); w.writerows(DataFile.objects.exclude(sha256__isnull=True).exclude(sha256='').values_list('file_path','file_size','sha256').iterator())" \
      > "$KNOWN_SHA"
  ) || { echo 'G2失败：已有SHA-256导出失败'; return 1; }

  awk -F '\t' 'NR>1 {n++; b+=$2} END {printf "file_count=%d\ntotal_bytes=%.0f\n", n, b}' \
    "$MANIFEST" > "$EVIDENCE_DIR/manual_files_summary.txt"
  (cd "$EVIDENCE_DIR" && sha256sum manual_files.tsv datafile_known_sha256.tsv manual_files_summary.txt cutoff.env migrations.txt release_identity.txt > EVIDENCE_SHA256SUMS) || return 1
  chmod 400 "$MANIFEST" "$KNOWN_SHA" "$EVIDENCE_DIR/manual_files_summary.txt" \
    "$EVIDENCE_DIR/migrations.txt" "$EVIDENCE_DIR/release_identity.txt" "$EVIDENCE_DIR/EVIDENCE_SHA256SUMS"
  cp "$MANIFEST" "$KNOWN_SHA" "$EVIDENCE_DIR/manual_files_summary.txt" "$EVIDENCE_DIR/migrations.txt" \
    "$EVIDENCE_DIR/release_identity.txt" "$EVIDENCE_DIR/EVIDENCE_SHA256SUMS" "$DB_BACKUP_DIR/" || return 1
  chmod 400 "$DB_BACKUP_DIR/manual_files.tsv" "$DB_BACKUP_DIR/datafile_known_sha256.tsv" \
    "$DB_BACKUP_DIR/manual_files_summary.txt" "$DB_BACKUP_DIR/migrations.txt" \
    "$DB_BACKUP_DIR/release_identity.txt" "$DB_BACKUP_DIR/EVIDENCE_SHA256SUMS"

  echo "文件清单完成：$EVIDENCE_DIR"
  cat "$EVIDENCE_DIR/manual_files_summary.txt"
}

g2_manual_manifest
echo "文件清单返回码：$?"
```

该命令只读取文件元数据和数据库已有 SHA-256，不读取全部文件内容，不修改数据库，也不修改 `manual_files`。

## 7. 结果检查与状态判定

执行：

```bash
ls -lh "$DB_BACKUP_DIR"
ls -lh "$EVIDENCE_DIR"
(cd "$DB_BACKUP_DIR" && sha256sum -c SHA256SUMS)
(cd "$EVIDENCE_DIR" && sha256sum -c EVIDENCE_SHA256SUMS)
echo 'tmux会话保持开启'
```

状态必须分开记录：

- **G1 已完成**：真实生产进程、production settings、release 目录、migration 状态和数据库连接均已确认；项目负责人显式确认已停止测试写入；没有发现其他用户或自动写入。
- **G2 备份已生成**：数据库结构备份、完整备份、SHA-256 和 `manual_files` 清单均已生成并通过本地校验。
- **G2 待验收**：数据库备份尚未在独立的 MySQL 环境完成恢复验证时，不得写成“G2 已完成”。恢复验证必须在非生产数据库实例中另行执行并保存表数量、migration 状态和抽样查询证据。

完成 G1/G2 不等于 G3 已获批准。不要关闭旧服务，不要删除旧数据库或 `manual_files`。

## 8. 文档评审结论

2026-11-25 文档级评审通过。项目负责人提供的生产输出显示 G1 返回码为 0，证据目录为生产私有目录；仓库不保存该生产证据。G2 数据库备份、文件清单和隔离恢复验证仍须根据实际输出分别验收。评审确认：

- 不猜测 PID、Python、数据库连接或 `manual_files` 路径，而是从同时匹配 Gunicorn、`filemanager.wsgi`、端口 2025、production settings 和 release 目录的生产进程读取；端口与 WSGI 参数的命令行顺序不作假设；
- 不打印数据库密码，不把密码写入备份文件或命令行参数；
- 自动读取 MySQL `@@datadir`，检查数据库备份目录与数据库数据目录不在同一文件系统；执行人还必须用 `lsblk` 确认两者不是同一底层磁盘或存储卷；
- 不使用顶层 `exit`、`logout`、`exec` 或 `set -e`，失败后 tmux 会话仍保留；
- 不递归 `chmod` 旧文件，不停止共享数据库实例，不执行 migration 或生产数据写入；
- 文件清单仅扫描元数据，不对 757G 内容做全量 SHA-256；
- release 身份和 `showmigrations --plan` 结果与截止时间一起保存；
- 数据库备份生成、独立环境恢复验证和 G2 最终验收被明确区分。

数据库备份目录已确定为 `/var/backups/genedata-legacy`，现场已确认它与 MySQL 数据目录位于不同文件系统。尚未解决的现场前置条件是隔离恢复验证环境；数据库备份、清单或恢复任一项缺少成功证据时，都不能把 G2 标记为完成。
