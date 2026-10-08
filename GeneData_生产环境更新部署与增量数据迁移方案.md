# GeneData 生产环境更新部署与增量数据迁移方案

## 1. 结论

目前不建议直接将开发工作区部署到生产环境。

项目已经基本适配生产环境 `manual_files` 的文件命名规则，但增量 Manifest、文件校验、绑定、隔离和占位层级清理等代码仍处于未提交状态。此外，项目尚未补齐 Gunicorn、systemd、Nginx、发布与回滚脚本等生产部署文件，生产安全配置也需要进一步完善。

推荐采用以下原则：

- 代码可以按确定的 Git commit/tag 一次部署。
- 真实 Assembly、Annotation 和文件关系必须按 Manifest 分批导入。
- `default` 和 `default-annotation` 必须按 Accession 分批替换，不能全局批量删除。
- 所有生产数据变更必须先 dry-run、审核报告、备份，然后再显式执行 `--apply`。

---

## 2. 当前开发环境数据状态

当前开发数据库统计如下：

| 项目 | 数量 |
|---|---:|
| Accession | 633 |
| Assembly | 607 |
| 名称为 `default` 的 Assembly | 472 |
| 有 `assembly_code` 的 Assembly | 135 |
| Annotation | 603 |
| 名称为 `default-annotation` 的 Annotation | 472 |
| 有 `annotation_code` 的 Annotation | 131 |
| DataFile | 144 |
| FileRelation | 161 |

开发环境中仍然存在大量 `default` 和 `default-annotation`。

这些记录主要来自早期数据库迁移。迁移为了兼容旧页面，为每个 Accession 自动建立了占位 Assembly，并为 Assembly 自动建立了占位 Annotation。它们不代表数据库中存在真实 FASTA 或 GFF 文件。

生产数据库的数量必须在生产服务器上单独查询，不能使用开发环境统计结果代替。

---

## 3. 生产环境 manual_files 适配情况

### 3.1 已支持的文件命名

当前代码已支持以下生产文件命名方式：

```text
genome.MH63.fasta
annotation.MH63.gff
transcriptome.all.MH63.fastaq.gz
transcriptome.root.MH63.fastaq.gz
transcriptome.shoot.MH63.fastaq.gz
transcriptome.stem.MH63.fastaq.gz
transcriptome.panicles.MH63.fastaq.gz
transcriptome.leaf.MH63.fastaq.gz
TEs.MH63.tar.gz
telomere.MH63.txt
centromere.MH63.tar.gz
rRNA.MH63.bed
tRNA.MH63.bed
genome.MH63.fasta.fai
```

同时兼容常规 `.fastq.gz` 和现有生产命名中的 `.fastaq.gz`。

### 3.2 已支持的内容校验

校验工具可以检查：

- FASTA 文件头和序列字符；
- GFF 列数及坐标字段；
- BED 标准格式和项目中的旧版 miRNA 格式；
- FAI 索引列格式；
- gzip 文件完整性；
- tar、tar.gz 压缩包完整性；
- 空文件；
- 文件名中的 Accession 与 Manifest 是否一致；
- 文件角色是否符合 Manifest 类型。

### 3.3 适配边界

仍需注意：

- 文件角色名称区分大小写，必须遵循约定。
- 文件名正确但内容损坏时仍会校验失败。
- `transcriptome.*.fastaq.gz` 必须是有效 gzip，且内部按 FASTQ 检查。
- 同一 Accession 存在多个 Assembly 时，普通自动绑定不会猜测目标 Assembly。
- 增量 Manifest 必须通过 `assembly_code` 和 `annotation_code` 明确指定层级。
- 只有扫描生产目录后，才能确认生产文件是否全部合格。

因此，当前状态可以描述为“代码规则基本适配”，不能在未审计生产目录的情况下认定生产数据已经完全适配。

---

## 4. default 产生原因及正确替换方式

### 4.1 为什么存在大量 default

早期迁移会对没有明确层级的 Accession 自动创建：

```text
Accession
└── Assembly: default
    └── Annotation: default-annotation
```

该结构用于兼容旧数据，并不表示存在真实组装版本或注释版本。

### 4.2 不正确的处理方式

禁止采用以下方式处理：

- 直接把 `default` 重命名为真实 Assembly；
- 全局删除全部 `default`；
- 仅根据文件名猜测 Assembly 或 Annotation；
- 直接运行旧 `scan_files` 写入生产数据库；
- 在没有真实替代层级时删除占位记录。

### 4.3 正确替换流程

应按 Accession 分批执行：

```text
真实 FASTA/GFF
      ↓
增量 Manifest
      ↓
创建或复用真实 Assembly/Annotation
      ↓
建立 DataFile/FileRelation
      ↓
设置真实记录为默认版本
      ↓
仅清理该 Accession 的安全占位记录
```

例如 MH63 应在 Manifest 中明确记录：

```text
Accession: MH63
Assembly code: ASM_MH63
Assembly name: MH63 genome assembly
Genome file: genome.MH63.fasta

Annotation code: ANN_MH63
Annotation name: MH63 annotation
Annotation file: annotation.MH63.gff
```

### 4.4 占位记录允许删除的条件

只有同时满足以下条件，才允许删除占位记录：

- 已存在真实替代 Assembly 或 Annotation；
- 对应 FASTA/GFF 已通过内容校验；
- 真实文件已经绑定到真实层级；
- 占位记录没有 FileRelation；
- 占位记录没有旧版 GenomeFile 关系；
- 占位记录没有真实业务元数据；
- 删除后不会产生悬空子记录。

Manifest 尚未补齐的 Accession 必须继续保留占位记录。

---

## 5. 开发环境必须完成的工作

### 5.1 完成增量数据工具收尾

当前已经新增或修改但尚未提交的功能包括：

- `validate_manual_files`；
- `bind_manual_files`；
- `quarantine_invalid_manual_files`；
- `cleanup_placeholder_hierarchy`；
- `import_incremental_hierarchy_manifest`；
- `telomere` 文件角色；
- `.fai` 文件识别；
- `.fastq.gz` 和 `.fastaq.gz` 识别；
- Manifest 模板；
- 增量导入操作文档；
- 相关命令及解析器自动化测试。

部署前需要：

1. 完成增量流程剩余回归测试；
2. 检查 dry-run 报告格式；
3. 确认幂等执行行为；
4. 确认失败时事务整体回滚；
5. 将本次功能独立提交到 Git；
6. 为生产版本建立明确的 commit/tag。

### 5.2 补齐生产部署文件

当前项目仍缺少：

- Gunicorn 依赖；
- Gunicorn 启动配置；
- systemd service；
- Nginx 配置；
- 发布脚本；
- 回滚脚本；
- 数据库备份与恢复脚本；
- 完整生产环境变量模板；
- 生产部署验收清单。

生产环境不能使用 Django `runserver`。

### 5.3 补充环境变量模板

当前 `.env.example` 至少还应补充：

```text
DJANGO_SETTINGS_MODULE=filemanager.settings_production
GENEDATA_MANUAL_FILES_DIR=
GENEDATA_LOG_PATH=
GENEDATA_STATIC_ROOT=
DJANGO_ALLOWED_HOSTS=
DJANGO_CORS_ALLOWED_ORIGINS=
DJANGO_CSRF_TRUSTED_ORIGINS=
```

以下信息禁止提交到 Git：

- 数据库密码；
- Django Secret Key；
- 生产服务器私钥；
- 数据库备份；
- 生产审计报告；
- 隔离目录中的文件。

### 5.4 完善 HTTPS 安全配置

生产 HTTPS 环境建议补充：

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

确认 HTTPS 和反向代理稳定后再启用 HSTS。

### 5.5 处理 MySQL 条件唯一约束问题

当前 Django 系统检查提示：MySQL 不支持带条件的唯一约束。

这会影响“每个 Accession 只能有一个默认 Assembly”和“每个 Assembly 只能有一个默认 Annotation”的数据库级保证。

生产前必须：

- 保留应用层“先取消旧默认，再设置新默认”的事务操作；
- 增加重复默认版本审计；
- 禁止绕过管理命令直接写入默认状态；
- 部署前检查重复默认记录；
- 评估是否需要通过 MySQL 生成列、触发器或其他数据库方案强化约束。

---

## 6. 需要在生产环境执行的工作

### 6.1 备份数据库和文件

部署前必须备份：

- MySQL 数据库；
- `manual_files`；
- 当前前端构建产物；
- 当前后端代码版本；
- 生产配置文件。

示例：

```bash
mysqldump ... > gene_manage_before_release.sql
tar -czf manual_files-backup-YYYYMMDD.tar.gz manual_files
```

备份完成后应验证备份文件大小，并至少进行一次恢复演练。

### 6.2 部署确定版本

生产环境只能部署：

- 已完成测试的 Git commit；
- 或明确标记的 release tag。

禁止直接复制带有未提交修改的开发工作区。

### 6.3 安装依赖和配置环境

生产服务器需要：

1. 创建或更新 Python 虚拟环境；
2. 安装锁定的依赖；
3. 设置生产环境变量；
4. 检查数据库连接；
5. 检查日志目录、静态目录和 `manual_files` 权限。

### 6.4 执行 Django 部署检查

```bash
python manage.py check --deploy \
  --settings=filemanager.settings_production
```

所有安全警告必须逐项评估，不能直接忽略。

### 6.5 检查和执行数据库迁移

先查看迁移计划：

```bash
python manage.py showmigrations \
  --settings=filemanager.settings_production

python manage.py migrate --plan \
  --settings=filemanager.settings_production
```

确认备份和迁移计划后再执行：

```bash
python manage.py migrate \
  --settings=filemanager.settings_production
```

### 6.6 收集静态文件

```bash
python manage.py collectstatic --noinput \
  --settings=filemanager.settings_production
```

### 6.7 构建前端

```bash
npm ci
npm test
npm run build
```

当前前端使用：

- `/gb/` 作为生产页面路径；
- `/gd/api/` 作为后端 API 路径；
- Hash Router 作为前端路由模式。

### 6.8 配置生产服务

Nginx 至少需要配置：

- `/gb/`：Vue 静态页面；
- `/gd/api/`：反向代理 Django/Gunicorn；
- `/static/`：Django 静态文件；
- 大文件下载的超时、缓冲及传输策略。

Django 应由 Gunicorn 和 systemd 管理，禁止以 `runserver` 作为生产服务。

### 6.9 审计生产 manual_files

首先只读执行：

```bash
python manage.py validate_manual_files \
  --settings=filemanager.settings_production
```

需要检查：

- 空文件；
- 损坏文件；
- 无法识别的命名；
- 未知 Accession；
- 多 Assembly 歧义；
- 数据库未登记文件；
- 数据库路径与实际路径不一致；
- 重复文件角色；
- 压缩包和格式错误。

### 6.10 分批执行增量 Manifest

每一批先 dry-run：

```bash
python manage.py import_incremental_hierarchy_manifest \
  --assembly-file /path/to/assembly.tsv \
  --annotation-file /path/to/annotation.tsv \
  --batch-id batch-001 \
  --settings=filemanager.settings_production
```

只有报告状态为 `READY` 时，才能执行：

```bash
python manage.py import_incremental_hierarchy_manifest \
  --assembly-file /path/to/assembly.tsv \
  --annotation-file /path/to/annotation.tsv \
  --batch-id batch-001 \
  --settings=filemanager.settings_production \
  --apply
```

每一批应用后应立即检查：

- Assembly 一级页面；
- Assembly 详情页；
- Assembly Statistics；
- Annotation 页面；
- 文件下载；
- Accession 到 Assembly 的跳转；
- Assembly 到 Annotation 的跳转；
- 默认版本是否唯一；
- 占位记录是否只清理了本批 Accession。

---

## 7. 开发环境与生产环境职责划分

| 工作项 | 开发环境完成 | 生产环境执行 |
|---|:---:|:---:|
| 文件命名解析代码 | 是 | 否 |
| 格式校验代码 | 是 | 否 |
| 增量 Manifest 命令 | 是 | 否 |
| 自动化测试 | 是 | 否 |
| Manifest 模板 | 是 | 否 |
| Gunicorn/systemd/Nginx 模板 | 是 | 否 |
| 前端测试和构建验证 | 是 | 再执行一次 |
| 生产密码与 Secret Key | 否 | 是 |
| 生产数据库备份 | 否 | 是 |
| 生产 manual_files 备份 | 否 | 是 |
| 生产目录只读审计 | 可模拟 | 是 |
| `migrate --plan` | 可预演 | 是 |
| `migrate` | 测试库执行 | 是 |
| Manifest dry-run | 测试数据执行 | 是 |
| Manifest `--apply` | 测试库验收 | 是 |
| 生产 default 清理 | 否 | 按批执行 |
| 生产页面验收 | 否 | 是 |

---

## 8. 生产环境禁止直接执行的操作

- 禁止直接运行旧 `scan_files` 扫描并写入全量数据；
- 禁止全局删除所有 `default`；
- 禁止在多 Assembly 情况下猜测文件关系；
- 禁止把开发数据库覆盖到生产数据库；
- 禁止把开发环境隔离目录复制到生产业务目录；
- 禁止提交数据库备份、密码或审计报告；
- 禁止在没有数据库和文件备份时执行 `--apply`；
- 禁止在 dry-run 状态不是 `READY` 时继续应用；
- 禁止在生产环境使用 Django `runserver`；
- 禁止在未验证回滚方案时批量处理全部 Accession。

---

## 9. 推荐实施顺序

### 阶段一：开发环境收尾

1. 完成增量 Manifest 流程验收；
2. 完成相关后端回归测试；
3. 补齐 Gunicorn、systemd、Nginx 和环境变量模板；
4. 修复生产安全检查；
5. 完成前端测试与构建；
6. 将本次变更独立 Git 提交；
7. 创建 release tag。

### 阶段二：测试服务器预演

1. 使用生产目录结构进行部署；
2. 使用脱敏数据库副本；
3. 执行 `validate_manual_files`；
4. 执行增量 Manifest dry-run；
5. 执行小批量 apply；
6. 验证页面、下载和回滚；
7. 记录操作时长和失败处理方法。

### 阶段三：生产代码部署

1. 停止写入或进入维护窗口；
2. 备份数据库和文件；
3. 部署确定 commit/tag；
4. 安装依赖；
5. 执行部署检查；
6. 执行数据库迁移；
7. 收集静态文件；
8. 部署前端；
9. 启动 Gunicorn/systemd；
10. 切换 Nginx；
11. 完成基础冒烟测试。

### 阶段四：生产数据分批迁移

1. 全量只读审计 `manual_files`；
2. 修复或隔离无效文件；
3. 准备第一批 Manifest；
4. 执行 dry-run；
5. 审核报告；
6. 执行 apply；
7. 验证该批 Accession；
8. 继续下一批；
9. Manifest 全部补齐后再评估剩余占位记录。

---

## 10. 最终原则

项目升级应拆分为两个独立过程：

1. **代码部署**：使用经过测试的固定 Git 版本完成；
2. **数据迁移**：使用增量 Manifest 按 Accession 分批完成。

代码部署完成不代表应立即删除全部 `default`。只有当某个 Accession 的真实 Assembly、Annotation 和文件关系全部建立并通过验证后，才能清理该 Accession 的占位层级。

这样可以在 Manifest 逐步补齐的情况下持续推进生产更新，同时避免因全量清理导致页面无法访问、文件关系丢失或数据层级错误。
