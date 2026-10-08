# GeneData 内置 JBrowse 2 基因组浏览器实施方案

## 1. 文档信息

- 项目：GeneData 数据仓库
- 目标：在现有 Vue 3 + Django 系统中增加内置 JBrowse 2 基因组浏览器
- 适用环境：Windows 开发环境、Linux 生产环境
- 实施原则：复用现有 Assembly、Annotation、DataFile、FileRelation 和 FASTA 索引能力，不修改生产原始数据文件
- 当前结论：技术上可行，建议先以 IR64 完成单 Assembly 验证，再逐步批量开放
- 文件命名核查依据：生产路径清单 `file_list_accession.txt`（2245 条路径）及 `production_full_manifest_20260924`
- 修订说明：已根据生产真实 `.fasta`、`.gff` 命名和特殊 Accession 名称补充格式探测、角色兼容和安全处理要求

## 2. 建设目标

在 Assembly 详情页面增加“基因组浏览器”入口，用户在 GeneData 页面内即可查看：

- Assembly 对应的参考基因组；
- 染色体或 Contig 列表；
- 指定染色体坐标区域；
- 基因、mRNA、exon、CDS 等注释；
- 注释特征的名称、位置、方向和属性；
- 不同 Assembly 对应的独立参考序列和注释轨道。

第一阶段不包括：

- BAM/CRAM 比对轨道；
- VCF 变异轨道；
- BigWig 覆盖度轨道；
- 多基因组共线性视图；
- 用户上传自定义轨道。

以上轨道可以在基础版本稳定后继续增加。

## 3. 当前项目条件

### 3.1 已具备能力

当前项目已经具备以下基础：

1. 前端使用 Vue 3 和 Vue Router，可以增加独立的基因组浏览器页面。
2. 已存在 Assembly 详情路由 `/assembly/:assemblyId`。
3. Assembly、Annotation、DataFile 和 FileRelation 已建立关联模型。
4. 已有确定性选择主基因组 FASTA 的服务逻辑，优先使用规范角色 `genome_fasta`，并兼容符合命名约定的历史角色 `genome`。
5. 已有 `build_fasta_indexes` 命令及 `.fai` 生成逻辑。
6. 已有 `AnnotationFeatureIndex` 和 `AnnotationFeature`，当前注释查询不再依赖在线解析完整文件。
7. 生产全量 Manifest 已明确 Assembly、Annotation 和文件之间的映射结构。

### 3.2 尚未具备能力

需要补充：

1. JBrowse 2 Web 静态应用；
2. JBrowse 动态配置接口；
3. 对生产 `.gff` 源文件进行格式探测、必要的 GFF3 标准化、排序、bgzip 压缩及 Tabix 索引；
4. 支持 HTTP Range 的生产文件读取方式；
5. Vue 基因组浏览器页面及 Assembly 入口；
6. 索引状态、过期检测和批量审计报告；
7. 生产真实文件的存在性、权限和内容格式验收。

### 3.3 特别说明

现有 `AnnotationFeatureIndex` 是数据库查询索引，不能直接替代 JBrowse 所需的 `.gff3.gz + .tbi` 文件。两套索引用途不同：

| 索引 | 用途 |
|---|---|
| `AnnotationFeatureIndex` | GeneData 当前注释列表、筛选和详情接口 |
| `.gff3.gz + .tbi` | JBrowse 按基因组区域分段读取注释轨道 |

生产 `manual_files` 应继续保持只读。JBrowse 产生的 `.fai`、`.gff3.gz` 和 `.tbi` 应写入独立衍生数据目录。

### 3.4 生产真实文件清单核查结果

已对生产路径清单 `file_list_accession.txt` 进行只读核查。该清单只包含文件路径，不包含文件大小、权限、校验值和文件内容，因此以下结论属于命名结构核查，不能替代生产服务器文件实体验收。

| 项目 | 数量 | 结论 |
|---|---:|---|
| 非空且唯一的文件路径 | 2245 | 清单内没有重复路径 |
| `genome.*.fasta` | 607 | 均为未压缩 `.fasta`，适合配合独立 `.fai` 使用 |
| `annotation.*.gff` | 517 | 对应 515 个不同 Accession，必须探测实际格式 |
| 有 FASTA 但没有 Annotation 的 Accession | 92 | 应正常降级为 `reference_only`，不得创建虚假 Annotation |
| 名称为 `.gff3` 的源文件 | 0 | 标准化输出应由索引任务生成 |
| 已有 `.fai` | 0 | 生产索引需要重新生成 |
| 已有 `.tbi` | 0 | 生产注释索引需要重新生成 |
| 文件名包含空格 | 154 | 禁止用未转义文件名拼接 Shell 命令或 URL |
| 文件名包含括号 | 4 | 内部路径和 Track ID 应使用数据库 ID |

清单中存在两个具有多个 Annotation 版本的 Accession：

- CG14：标准 Annotation 和 `IGDBv1.Allset`；
- R498：标准 Annotation 和 `IGDBv1.Allset`。

清单还包含 `Nanoay P.A` 等名称中自身带空格和点号的 Accession。因此运行时不得通过 `file_name.split('.')` 等方法反推 Accession、Assembly 或 Annotation，必须使用已经批准的 Manifest 和数据库 FileRelation。

当前批准的 `files.full.tsv` 映射 2240 条路径，原始清单中以下 5 条未被映射：

```text
centromere.OrufRS1.bed
miRNA.DR1.bed
codon.sh
supplymentary_data.txt
supplymentary_data.txt.bak_20260416
```

JBrowse 构建过程不得重新扫描全部 `manual_files` 并根据文件名自动绑定，也不得把上述排除项重新导入。源文件必须来自数据库中已经建立的 FileRelation。

## 4. 总体架构

```text
Assembly 详情页
    |
    | 点击“基因组浏览器”
    v
Vue GenomeBrowserView
    |
    | iframe 加载同域 JBrowse Web
    v
/jbrowse2/
    |
    | 请求 Assembly 动态配置
    v
Django JBrowse Config API
    |
    | 返回经过鉴权的文件 URL
    v
Nginx Range 文件服务
    |-- genome.fa
    |-- genome.fa.fai
    |-- annotation.sorted.gff3.gz
    `-- annotation.sorted.gff3.gz.tbi
```

推荐将完整 JBrowse Web 静态部署在 `/jbrowse2/`，然后在 Vue 页面内嵌。现有 Vue 生产路径已经使用 `/gb/`，JBrowse 不得占用或覆盖 `/gb/`。

## 5. 数据文件规范

### 5.1 参考基因组

JBrowse 使用：

```text
genome.fa
genome.fa.fai
```

现有未压缩 FASTA 可以继续使用，不复制大型 FASTA。`.fai` 可以通过现有索引服务生成，但生产环境应支持将索引输出到独立衍生目录。

### 5.2 基因注释

生产真实源文件的命名形式为：

```text
annotation.<accession>.gff
```

`.gff` 扩展名不能证明文件一定是 GFF3。索引任务必须先检查：

- 是否声明 `##gff-version 3`；
- 是否为合法的九列记录；
- attributes 列是否符合 GFF3 语法；
- `ID`、`Parent` 及 gene、mRNA、exon、CDS 层级是否可解析；
- 文件是否实际属于 GFF2、GTF 或其他非标准格式。

处理规则：

| 源文件检测结果 | 处理方式 |
|---|---|
| 有效 GFF3 | 排序后生成标准化 `.gff3.gz + .tbi` |
| 可可靠转换的 GFF2/GTF | 转换为标准 GFF3，再排序和索引 |
| 格式不完整或存在歧义 | 标记 `invalid_annotation_format`，不发布注释轨道 |

任何转换都只能写入衍生数据目录，不能覆盖生产源 `.gff`。

JBrowse 最终使用：

```text
annotation.sorted.gff3.gz
annotation.sorted.gff3.gz.tbi
```

有效 GFF3 的生成流程示例：

```bash
jbrowse sort-gff annotation.IR64.gff | bgzip > annotation.IR64.sorted.gff3.gz
tabix -p gff annotation.IR64.sorted.gff3.gz
```

上述命令只适用于内容已经确认是有效 GFF3 的源文件。正式实现中应由 Django 管理命令调用固定版本工具，不能依赖人工逐个运行，也不能把无法识别的 `.gff` 静默当作 GFF3。

### 5.3 染色体名称一致性

FASTA 标题与 GFF3 第一列 `seqid` 必须能够对应。例如：

```text
FASTA: >Chr01
GFF3:  Chr01
```

如果 FASTA 使用 `Chr01` 而 GFF3 使用 `1`，JBrowse 可能成功打开，但注释轨道不会出现在正确区域。因此索引命令必须在注册文件前检查：

- 完全一致的序列名称；
- 可以安全映射的已知别名；
- 无法映射的序列名称；
- GFF3 中存在但 FASTA 中不存在的序列；
- FASTA 中存在但 GFF3 中没有注释的序列。

无法安全映射时，索引状态应为失败，不允许静默发布空轨道。

### 5.4 特殊文件名与安全标识

生产文件包含空格、点号和括号，例如：

```text
genome.Nanoay P.A.fasta
annotation.Nanoay P.A.gff
annotation.CG14.IGDBv1.Allset.gff
genome.2037(Rajahamsal).fasta
```

实施时必须遵守：

- 源文件关系来自 FileRelation，不从文件名推导业务实体；
- 调用外部命令使用参数数组，不拼接 Shell 命令字符串；
- JBrowse `trackId`、内部 Assembly Name 和衍生目录使用数据库 ID，例如 `assembly-123`；
- 页面显示名称可以继续使用真实 Accession 或 Annotation 名称；
- 所有 URL 通过后端按 DataFile ID 生成，不直接暴露或拼接物理文件名；
- 如确需使用文件名，必须经过严格路径边界检查和 URL 编码。

## 6. 衍生数据目录

### 6.1 生产环境变量

建议增加：

```env
GENEDATA_DERIVED_DATA_DIR=/home/labuser/rdcheng/gd/derived_data
GENEDATA_JBROWSE_DATA_DIR=/home/labuser/rdcheng/gd/derived_data/jbrowse
```

### 6.2 目录结构

```text
/home/labuser/rdcheng/gd/derived_data/jbrowse/
|-- assemblies/
|   `-- ASM_IR64/
|       `-- genome.IR64.fasta.fai
`-- annotations/
    `-- ANN_IR64/
        |-- annotation.IR64.sorted.gff3.gz
        `-- annotation.IR64.sorted.gff3.gz.tbi
```

目录和文件名应使用数据库 ID 或经过安全编码的唯一代码，不能直接把未经处理的用户输入拼接到路径中。

## 7. 后端开发方案

### 7.1 建议新增文件

```text
django2/files/services/jbrowse_index_service.py
django2/files/services/jbrowse_config_service.py
django2/files/management/commands/build_jbrowse_indexes.py
django2/files/jbrowse_api_views.py
django2/files/tests/unit/test_jbrowse_index_service.py
django2/files/tests/api/test_jbrowse_config_api.py
django2/files/tests/api/test_jbrowse_asset_api.py
```

需要修改：

```text
django2/files/urls.py
django2/files/services/ingestion/roles.py
django2/filemanager/settings.py
django2/filemanager/settings_production.py
```

如果需要专门记录构建状态，则增加模型和迁移；如果第一阶段完全复用 DataFile、FileRelation 及文件状态检查，可以暂不增加新模型。

### 7.2 文件角色

生产真实 Manifest 当前使用的源角色为：

```text
genome
annotation
```

项目规范和生成文件继续使用：

```text
genome_fasta
genome_index
```

建议新增：

```text
jbrowse_annotation_gff3
jbrowse_annotation_tabix
```

输入选择及生成映射规则：

| 文件 | related_type | 输入或输出 file_role |
|---|---|---|
| 原始 FASTA（优先） | `assembly` | `genome_fasta` |
| 原始 FASTA（历史兼容） | `assembly` | `genome`，仅接受合法的 `genome.<accession>.fasta` |
| 原始注释源文件 | `annotation` | `annotation` |
| FASTA FAI | `assembly` | `genome_index` |
| 排序压缩 GFF3 | `annotation` | `jbrowse_annotation_gff3` |
| Tabix TBI | `annotation` | `jbrowse_annotation_tabix` |

JBrowse 构建服务必须复用现有主基因组确定性选择逻辑，不能自行实现另一套“找到第一个 genome 文件”的规则。注释文件必须从当前 Annotation 的 FileRelation 中选择，不允许按目录扫描结果猜测归属。

### 7.3 索引构建命令

当前已经实现单 Assembly 和全量分批两种模式：

```bash
python manage.py build_jbrowse_indexes --assembly-id 123 --dry-run
python manage.py build_jbrowse_indexes --assembly-id 123 --apply
python manage.py build_jbrowse_indexes --assembly-id 123 --dry-run --output-dir /path/to/derived_data/jbrowse

python manage.py build_jbrowse_indexes --all --dry-run \
  --batch-size 20 --resume \
  --report-dir /path/to/audit_reports/jbrowse

python manage.py build_jbrowse_indexes --all --apply \
  --batch-size 10 --resume \
  --report-dir /path/to/audit_reports/jbrowse
```

当前参数：

| 参数 | 含义 |
|---|---|
| `--assembly-id` | 只处理指定 Assembly；与 `--all` 二选一 |
| `--all` | 按 ID 顺序处理公开 Assembly 列表中的对象并排除严格占位项；与 `--assembly-id` 二选一 |
| `--dry-run` | 只检查，不创建文件或数据库记录 |
| `--apply` | 预检通过后生成、提升并登记索引文件 |
| `--output-dir` | 覆盖本次任务的衍生索引根目录 |
| `--batch-size` | 限制本次最多处理的待处理 Assembly 数量 |
| `--resume` | 从 `--report-dir` 中与模式对应的 checkpoint 继续 |
| `--retry-failed` | 与 `--resume` 配合，只重试 checkpoint 中的失败项 |
| `--report-dir` | 全量模式必填，保存 JSON、TSV 和 checkpoint |
| `--fail-on-error` | 写完报告后，只要本批存在失败就返回非零状态 |

`--dry-run` 和 `--apply` 必须且只能选择一个。dry-run 与 apply 使用独立 checkpoint，不能互相跳过。每个 Assembly 完成后立即原子更新 checkpoint；单项失败会写入报告但默认不阻断后续项目。`remaining_count` 表示尚未尝试的数量，`failed_checkpoint_count` 表示 checkpoint 中仍未解决的失败数量；只有两者同时为 `0` 才表示该模式全量完成。需要让自动化任务在存在失败时返回非零状态，应显式增加 `--fail-on-error`。

单个 Assembly 的处理流程：

1. 查找 Assembly。
2. 使用现有服务确定唯一主 FASTA。
3. 检查 FASTA 是否存在、可读且非空。
4. 检查已有 `.fai` 是否有效且未过期。
5. 在衍生目录生成新的 `.fai`，必要时替换旧索引。
6. 根据数据库关系选择 `is_default=True` 的 Annotation；没有 Annotation 时记录 `reference_only`。
7. 从该 Annotation 的 FileRelation 中选择当前 `annotation` 源文件。
8. 探测 `.gff` 的实际格式，验证九列结构、attributes 和父子关系。
9. 对有效 GFF3 直接标准化；对可可靠转换的 GFF2/GTF 先转换；无法识别时记录 `invalid_annotation_format`。
10. 对标准化 GFF3 排序、bgzip 压缩并生成 `.tbi`。
11. 对比 FASTA 和标准化 GFF3 的序列名称。
12. 将产物注册为 DataFile 和 FileRelation。
13. 对非默认 Annotation 版本生成独立可选轨道，不覆盖默认版本。
14. 输出成功、跳过、警告和失败记录。

索引生成要求：

- 在目标目录中使用临时文件；
- 所有步骤成功后执行原子替换；
- 失败时删除临时文件但保留旧的可用索引；
- 不修改原始 FASTA 和 `.gff`/GFF3；
- 同一索引不能被两个并发任务同时构建；
- 一个 Assembly 失败不能中断全部批处理。

数据发现边界：

- `--all` 只遍历数据库中满足条件的 Assembly 和 FileRelation；
- 不遍历 `manual_files` 目录发现新业务对象；
- 不根据文件名自动创建 Assembly 或 Annotation；
- 不重新绑定批准 Manifest 已排除的文件；
- 发现数据库文件记录与物理文件不一致时只报告，不自动改绑。

### 7.4 索引过期判断

至少比较：

- 源 DataFile ID；
- 源文件大小；
- 源文件修改时间；
- DataFile MD5（存在时）；
- 生成索引的工具版本；
- 索引文件是否存在且非空。

源文件发生变化后，旧索引必须返回 `stale_index`，不能继续作为可用轨道。

## 8. API 设计

### 8.1 Assembly 浏览器状态接口

可以将状态放在配置接口中，也可以单独提供：

```http
GET /gd/api/files/assemblies/{assembly_id}/jbrowse-status/
```

返回示例：

```json
{
  "assembly_id": 123,
  "status": "ready",
  "reference_ready": true,
  "annotation_ready": true,
  "message": ""
}
```

状态值：

```text
ready
reference_only
missing_genome
missing_fasta_index
missing_annotation_source
missing_annotation_index
invalid_annotation_format
stale_index
seqid_mismatch
ambiguous_genome
build_failed
```

### 8.2 JBrowse 配置接口

```http
GET /gd/api/files/assemblies/{assembly_id}/jbrowse-config/
```

返回示例：

```json
{
  "assembly": {
    "name": "assembly-123",
    "displayName": "IR64",
    "sequence": {
      "type": "ReferenceSequenceTrack",
      "trackId": "assembly-123-reference",
      "adapter": {
        "type": "IndexedFastaAdapter",
        "fastaLocation": {
          "uri": "/gd/api/files/browser-assets/101/"
        },
        "faiLocation": {
          "uri": "/gd/api/files/browser-assets/102/"
        }
      }
    }
  },
  "tracks": [
    {
      "type": "FeatureTrack",
      "trackId": "annotation-456-features",
      "name": "IR64 annotation",
      "assemblyNames": ["assembly-123"],
      "adapter": {
        "type": "Gff3TabixAdapter",
        "gffGzLocation": {
          "uri": "/gd/api/files/browser-assets/103/"
        },
        "index": {
          "indexType": "TBI",
          "location": {
            "uri": "/gd/api/files/browser-assets/104/"
          }
        }
      }
    }
  ],
  "defaultLocation": "Chr01:1..100000",
  "status": "ready"
}
```

配置接口必须：

- 只返回当前有效文件；
- 使用唯一 Assembly 上下文；
- 使用默认 Annotation 或明确指定的 Annotation；
- 内部 Assembly Name 和 Track ID 使用数据库 ID 等安全标识，显示名称与内部标识分离；
- 不返回服务器物理路径；
- 不在多个 Assembly 之间复用错误轨道；
- 没有注释时返回空 `tracks`，保留参考序列。

### 8.3 浏览器文件接口

```http
GET /gd/api/files/browser-assets/{file_id}/
```

接口职责：

1. 验证 DataFile 存在且 `is_current=True`；
2. 验证文件具有允许的 JBrowse 文件角色；
3. 验证调用者权限；
4. 验证文件路径位于允许的数据根目录；
5. 设置 `Content-Type` 和 `Content-Disposition: inline`；
6. 返回 `X-Accel-Redirect`，由 Nginx 传输文件；
7. 不通过 Django Worker 在线读取大型 FASTA 或 GFF3。

允许的文件类型：

```text
.fa
.fasta
.fna
.fai
.gff.gz
.gff3.gz
.tbi
```

## 9. Nginx 文件服务

建议使用内部路径，禁止用户直接访问服务器目录：

```nginx
location /_protected_manual_files/ {
    internal;
    alias /home/labuser/rdcheng/gd/manual_files/;
    gzip off;
}

location /_protected_derived_data/ {
    internal;
    alias /home/labuser/rdcheng/gd/derived_data/;
    gzip off;
}
```

Django 根据 DataFile 的安全路径返回对应的内部重定向。Nginx 负责 Range 请求和文件传输。

配置修改后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Range 验证：

```bash
curl -I \
  -H "Range: bytes=0-99" \
  https://example.org/gd/api/files/browser-assets/101/
```

必须返回：

```text
HTTP/1.1 206 Partial Content
Accept-Ranges: bytes
Content-Range: bytes 0-99/...
```

如果返回 `200 OK` 并发送完整文件，不得进入正式上线阶段。

## 10. JBrowse Web 部署

### 10.1 部署路径

建议部署到：

```text
https://example.org/jbrowse2/
```

不要使用现有 Vue 项目的 `/gb/` 路径。

### 10.2 版本管理

- 使用固定版本，不使用自动变化的 `latest`；
- JBrowse 静态产物纳入发布包或独立版本目录；
- 记录 JBrowse、Node.js、samtools、bgzip 和 tabix 版本；
- 生产页面不依赖未固定版本的第三方 CDN；
- 保留上一版本静态目录用于回滚。

### 10.3 同域策略

优先让 Vue、JBrowse 和文件 API 使用同一域名，从而减少 CORS 和登录状态问题。如果必须跨域，需要明确配置：

- `Access-Control-Allow-Origin`；
- `Range` 请求；
- 凭据策略；
- 安全响应头。

## 11. Vue 前端改造

### 11.1 新增文件

```text
vue_project/src/views/GenomeBrowserView.vue
```

可选新增：

```text
vue_project/src/services/jbrowseApi.js
vue_project/src/components/GenomeBrowserStatus.vue
```

### 11.2 新增路由

```javascript
{
  path: '/assembly/:assemblyId/browser',
  name: 'genome-browser',
  component: () => import('../views/GenomeBrowserView.vue'),
  meta: {
    requiresAuth: true
  }
}
```

### 11.3 Assembly 详情入口

在 `AssemblyView.vue` 增加：

```text
基因组浏览器 / Genome Browser
```

按钮规则：

- 有真实主 FASTA：允许进入；
- 没有 FASTA：禁用并提示；
- 索引未生成：进入状态页或提示管理员构建；
- 只有 FASTA 没有 Annotation：允许进入，只显示参考序列。

### 11.4 浏览器页面

页面加载流程：

1. 从路由读取 `assemblyId`；
2. 请求 JBrowse 配置接口；
3. 根据状态显示加载、错误或空注释提示；
4. 使用 iframe 加载 `/jbrowse2/`；
5. 传入配置 URL、Assembly 和初始位置；
6. Assembly 改变时重新创建 iframe，避免残留上一 Assembly 状态。

页面应包含：

- 返回 Assembly 详情入口；
- Assembly 和 Accession 名称；
- 索引状态提示；
- 自适应高度的 JBrowse 区域；
- 中英文文案；
- 加载失败后的重试按钮。

## 12. 分阶段实施步骤

### 阶段一：生产环境只读检查

1. 确认 `samtools`、`bgzip`、`tabix`、Node.js 和 Nginx 版本。
2. 确认运行用户可以读取 `manual_files`。
3. 确认衍生数据目录可以由运行或索引用户写入。
4. 检查磁盘可用空间。
5. 对 `genome.IR64.fasta` 和 `annotation.IR64.gff` 执行格式探测，确认该 `.gff` 的实际标准版本。
6. 确认 IR64 Assembly、Annotation 和文件绑定唯一。
7. 统计全部源 `.gff` 的文件大小、格式版本、空文件和九列异常，形成只读预检报告。

本阶段不修改原始文件和数据库。

### 阶段二：IR64 索引原型

1. 实现 JBrowse 索引服务。
2. 实现 `build_jbrowse_indexes` 命令。
3. 对 IR64 执行 `--dry-run`。
4. 判断 `annotation.IR64.gff` 是有效 GFF3、可转换格式还是无效格式。
5. 生成 IR64 `.fai`、标准化 `.gff3.gz` 和 `.tbi`。
6. 校验染色体名称。
7. 注册生成的 DataFile 和 FileRelation。

### 阶段三：文件访问和 Range

1. 实现浏览器文件接口。
2. 配置 Nginx 内部文件路径。
3. 验证鉴权、路径边界和文件类型。
4. 使用 `curl` 确认返回 `206 Partial Content`。
5. 确认大文件不经过 Django Worker 传输。

### 阶段四：动态配置接口

1. 实现状态和配置服务。
2. 输出 IR64 的 IndexedFastaAdapter 配置。
3. 输出 IR64 的 Gff3TabixAdapter 配置。
4. 验证无 Annotation Assembly 的 `reference_only` 状态。
5. 验证冲突和过期索引状态。

### 阶段五：JBrowse 和 Vue 接入

1. 部署固定版本 JBrowse Web 到 `/jbrowse2/`。
2. 新增 Vue 路由和页面。
3. 在 Assembly 详情页增加入口。
4. 完成中英文文案。
5. 验证刷新、返回和 Assembly 切换。

### 阶段六：小批量试运行

选择约 10 个具有代表性的 Assembly，包括：

- 正常 FASTA + 内容有效的 `.gff`；
- 只有 FASTA；
- 多个 Annotation 版本；
- 文件名包含空格或特殊字符；
- 染色体使用 `Chr01`；
- 染色体使用 `1`；
- 大型 `.gff`；
- 一个可转换或格式异常的 `.gff`（如生产预检发现）；
- 野生稻物种；
- 非默认 Assembly；
- 历史兼容 `genome` 角色。

修复所有可重复的数据或程序问题后再进行全量构建。

### 阶段七：全量构建和上线

1. 执行全量 `--dry-run`。
2. 保存审计报告。
3. 评估磁盘空间和预计执行量。
4. 分批构建全部可用索引。
5. 对失败项单独重试，不覆盖成功项。
6. 完成生产验收。
7. 开放全部满足条件的 Assembly 入口。

## 13. 测试方案

### 13.1 后端单元测试

- 唯一主 FASTA 可以正确选择；
- 多个主 FASTA 返回冲突；
- 无 FASTA 返回 `missing_genome`；
- 无 Annotation 返回 `reference_only`；
- 过期索引返回 `stale_index`；
- `.gff` 内容不是有效 GFF3 时不会直接交给 `Gff3TabixAdapter`；
- 可转换格式必须先产生标准化 GFF3；
- 无法识别的格式返回 `invalid_annotation_format`；
- 生成失败不会覆盖旧索引；
- FASTA 和 GFF3 `seqid` 不匹配会被识别；
- 特殊字符不会造成路径穿越；
- `Nanoay P.A` 等名称不会因点号或空格被错误拆分；
- CG14、R498 默认与非默认 Annotation 不会相互覆盖；
- `--all` 不会扫描目录或导入 Manifest 排除项；
- 重复运行保持幂等。

### 13.2 API 测试

- 配置接口不返回 `file_path`；
- 只返回当前有效文件；
- 文件接口拒绝不允许的文件角色；
- 不存在的 Assembly 返回 404；
- 文件关系冲突返回 409；
- 未授权访问符合项目权限策略；
- 配置中的所有 URL 都可以访问。

### 13.3 前端测试

- Assembly 详情入口正常；
- 浏览器加载状态正常；
- 错误状态提示清楚；
- 无注释时仍能浏览参考序列；
- Assembly 切换不会串用轨道；
- 中英文文案正常；
- 浏览器区域在常用分辨率下可用。

### 13.4 生产验收

必须满足：

1. Range 请求返回 `206 Partial Content`。
2. 浏览器不会下载完整 FASTA 后才显示。
3. 染色体列表与 `.fai` 一致。
4. 标准化注释位置与原始 `.gff` 抽样一致，转换过程未改变坐标语义。
5. 点击基因可以看到属性。
6. IR64 可以正常缩放、拖动和跳转坐标。
7. 无 Annotation Assembly 可以正常显示参考序列。
8. Django Worker 不承担大型文件持续传输。
9. API 和页面不泄露服务器物理路径。
10. 原有 Assembly、Annotation 和下载功能无回归。

## 14. 审计报告

索引命令应生成 JSON 和 TSV 报告，例如：

```text
audit_reports/jbrowse/jbrowse_index_report_YYYYMMDD_HHMMSS.json
audit_reports/jbrowse/jbrowse_index_report_YYYYMMDD_HHMMSS.tsv
```

至少包含：

- Assembly ID、Assembly Code 和 Accession；
- FASTA DataFile ID；
- Annotation ID 和源文件 ID；
- Annotation 是否为默认版本；
- 源注释扩展名、检测到的实际格式及是否发生转换；
- 索引状态；
- 参考序列数量；
- 注释记录数量；
- 不匹配的序列名称；
- 生成文件路径；
- 文件大小；
- 工具版本；
- 开始和结束时间；
- 错误信息。

汇总应包含：

```text
total
ready
reference_only
skipped
stale
invalid_annotation_format
seqid_mismatch
failed
```

## 15. 发布顺序

推荐发布顺序：

1. 备份数据库并保存当前代码、前端和 Nginx 配置版本。
2. 发布后端索引和配置接口代码，但暂不展示前端入口。
3. 如有迁移，执行数据库迁移。
4. 配置衍生数据目录。
5. 配置并验证 Nginx 内部文件服务。
6. 部署固定版本 JBrowse Web。
7. 为 IR64 生成索引。
8. 完成 IR64 后端和页面验收。
9. 发布 Vue 基因组浏览器页面和 IR64 入口。
10. 完成小批量 Assembly 验证。
11. 分批生成其余索引。
12. 根据索引状态逐步开放其他 Assembly。

不要先开放全部入口再批量修复数据。

## 16. 回滚方案

出现问题时按照以下顺序回滚：

1. 通过前端开关隐藏“基因组浏览器”入口。
2. 回滚 Vue 静态文件。
3. 回滚 Django 代码和数据库迁移（如迁移可逆且确需回滚）。
4. 恢复上一版本 JBrowse 静态目录。
5. 恢复 Nginx 配置并执行 `nginx -t`。
6. 保留衍生索引和审计报告，暂时不要删除。

回滚过程中禁止：

- 删除或覆盖生产 `manual_files`；
- 删除未确认无依赖的 DataFile；
- 修改原始 FASTA 或 `.gff`/GFF3；
- 用虚假 Annotation 补齐没有 GFF 的 Assembly。

## 17. 工作量评估

| 工作项 | 预计工作量 |
|---|---:|
| 真实 `.gff` 格式预检及 IR64 原型 | 1～2 天 |
| 索引服务和管理命令 | 1～2 天 |
| 配置 API 和安全文件接口 | 1～2 天 |
| JBrowse 部署及 Nginx Range | 1 天 |
| Vue 页面和 Assembly 入口 | 0.5～1 天 |
| 小批量验证、全量构建和生产验收 | 1～2 天 |

如果生产 `.gff` 内容实际均为有效 GFF3，预计总工作量为 5～8 个开发工作日。如果存在需要转换或人工修复的 GFF2、GTF、非标准 GFF，预计增加到 7～10 个开发工作日，且数据修复数量可能进一步影响工期。实际批量索引耗时还取决于生产 `.gff` 文件体积、磁盘速度和服务器负载，不应将机器执行时间等同于开发工作量。

## 18. 交付物

完成实施后应交付：

1. JBrowse 2 固定版本静态应用；
2. Vue 基因组浏览器页面及 Assembly 入口；
3. Django JBrowse 配置接口；
4. 安全的浏览器文件接口；
5. Nginx Range 文件服务配置；
6. JBrowse 索引构建命令；
7. 索引状态和过期检测；
8. 后端和前端自动化测试；
9. IR64 验收记录；
10. 全量索引审计报告；
11. 发布和回滚记录。

## 19. 最终上线门槛

以下条件全部满足后才能认定 JBrowse 2 已达到生产可用状态：

- IR64 和小批量代表 Assembly 均通过验收；
- Nginx Range 请求稳定返回 206；
- 生产 `.gff` 已完成实际格式探测，非 GFF3 文件已转换或明确隔离；
- FASTA 与 GFF3 序列名称已经校验；
- 索引生成过程不修改 `manual_files`；
- 索引任务只读取已批准的数据库 FileRelation，不扫描目录自动绑定文件；
- 大文件不由 Django Worker 持续传输；
- 配置接口不泄露物理路径；
- 无 Annotation 的 Assembly 能正确降级为仅参考序列；
- 索引过期和构建失败具有明确状态；
- 原有页面和下载接口通过回归测试；
- 发布、审计和回滚材料齐全。
