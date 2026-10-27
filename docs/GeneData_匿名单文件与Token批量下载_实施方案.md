# GeneData 匿名单文件与 Token 批量下载实施方案

- 文档日期：2026-10-27
- 适用项目：GeneData 基因组数据仓库
- 方案状态：待实施
- 目标版本：外部数据访问 API 与 `genedata` CLI 下一阶段

## 1. 文档目的

本方案用于统一 GeneData 公开文件的单文件下载、多文件批量下载、Token 权限、集群使用方式和后续 CLI 实施边界。

最终策略为：

1. 已公开、已发布且校验完整的单个文件允许匿名下载；
2. 多文件批量下载继续要求 Token；
3. 内部文件、私有文件和服务器归档不开放匿名访问；
4. CLI 在集群登录节点下载文件，计算节点只读取共享目录；
5. 所有下载继续使用受保护路径、HTTP Range 和 SHA-256 校验机制。

> 当前状态说明：现有生产下载接口仍要求 `file:read` Token。本文件描述的是待实施目标，不代表匿名单文件下载或独立 `genedata` CLI 已经上线。

## 2. 当前项目基础

当前项目已经具备以下能力：

- 公开文件目录和过滤查询；
- 稳定文件编号 `file_code`；
- 文件详情和 `content_url`；
- FASTA 与 FAI 伴随文件关系；
- Bearer Token、scope、有效期和撤销机制；
- 单文件内容接口；
- Nginx `X-Accel-Redirect` 文件发送；
- HTTP Range、`ETag`、`Last-Modified` 和 `Content-Length`；
- JSON/TSV Manifest；
- 不可变文件批次；
- 可选服务器归档；
- OpenAPI 契约。

已完成的生产验证包括：

- 登录节点能够访问 GeneData 文件内容接口；
- Range 请求返回 `206 Partial Content`；
- 大型 FASTA 完整下载和 SHA-256 校验成功；
- 计算节点不能直接访问外部网络；
- 计算节点可以读取登录节点写入共享目录的文件。

## 3. 最终访问策略

### 3.1 匿名单文件下载

只有同时满足以下条件的文件才能匿名下载：

- `publication_status=released`；
- `published_at` 已设置；
- `is_current=true`；
- 有效访问级别为 `public`；
- `content_version` 和 SHA-256 完整；
- 物理文件存在；
- 文件位于允许的受保护存储根目录中。

匿名用户可以直接访问：

```text
GET  /gd/api/v1/files/{file_code}/content/
HEAD /gd/api/v1/files/{file_code}/content/
```

示例：

```bash
curl -fLO \
  "https://example.org/gd/api/v1/files/FILE000013/content/"
```

### 3.2 需要 Token 的操作

以下操作继续要求 Token：

- 一次选择或下载多个文件；
- 自动将 FASTA 和 FAI 组合下载；
- 按 Accession 下载相关文件；
- 按 Dataset 下载相关文件；
- 按过滤条件下载前 N 个文件；
- 使用 Manifest 批量下载；
- 创建不可变服务器批次；
- 创建、查询和下载服务器归档；
- 访问内部数据。

普通批量下载 Token 建议包含：

```text
file:read
batch:create
batch:read
```

普通用户暂不默认获得：

```text
batch:archive
batch:download
```

### 3.3 非公开文件

以下文件不得因本次调整而匿名暴露：

- `access_level=internal`；
- `access_level=private`；
- 草稿或未发布文件；
- 非当前版本文件；
- 缺少发布时间、内容版本或摘要的文件；
- 物理文件缺失或逃逸受保护根目录的文件。

## 4. 匿名访问的边界与限流

单文件 HTTP 端点无法绝对识别调用者是否使用脚本循环下载。因此，“单文件匿名、批量需 Token”需要由接口规则、CLI 行为和限流共同实现。

建议的初始限流为：

| 类型 | 建议限制 | 识别依据 |
| --- | --- | --- |
| 匿名单文件下载 | 5 次/分钟 | 客户端 IP |
| 匿名下载日限额 | 20 个文件/天 | 客户端 IP |
| Token 文件下载 | 30 次/分钟 | Token prefix |
| 批次创建 | 10 次/分钟 | Token prefix |

建议增加以下环境变量：

```bash
GENEDATA_ANON_CONTENT_RATE=5/minute
GENEDATA_ANON_CONTENT_DAILY_RATE=20/day
GENEDATA_TOKEN_CONTENT_RATE=30/minute
GENEDATA_BATCH_RATE=10/minute
```

生产部署前必须确认反向代理正确传递可信客户端 IP；否则所有匿名请求可能被计入同一个 Nginx 地址。

## 5. 后端实施

### 5.1 统一访问判定

修改统一的数据文件访问服务，使判定规则成为：

| 操作 | public | internal | private |
| --- | --- | --- | --- |
| 元数据查询 | 匿名允许 | 需要对应 Token | 拒绝 |
| 单文件内容 | 匿名允许 | 需要 `file:read` 和 internal tier | 拒绝 |
| 批次创建 | 需要 `batch:create` | 需要对应权限和 tier | 拒绝 |
| 批次读取 | 需要 `batch:read` | 需要对应权限和 tier | 拒绝 |
| 归档创建 | 需要 `batch:archive` | 需要对应权限和 tier | 拒绝 |
| 归档下载 | 需要 `batch:download` | 需要对应权限和 tier | 拒绝 |

为匿名公开内容增加明确判定原因：

```text
public_content
```

原有判定原因继续保留：

```text
token_authorized
authentication_required
invalid_or_inactive_token
insufficient_scope
insufficient_access_tier
```

### 5.2 功能开关

增加生产安全开关：

```bash
GENEDATA_ALLOW_ANONYMOUS_PUBLIC_CONTENT=false
```

代码部署后默认保持关闭。完成测试和生产抽样验证后再设置为：

```bash
GENEDATA_ALLOW_ANONYMOUS_PUBLIC_CONTENT=true
```

发生异常时可以先关闭开关恢复原有 Token 策略，再进行版本回退。

### 5.3 拆分限流器

现有内容请求限流需要拆分为：

```text
ExternalAnonymousContentBurstThrottle
ExternalAnonymousContentDailyThrottle
ExternalAuthenticatedContentThrottle
ExternalBatchThrottle
```

匿名请求按可信客户端 IP 计数，Token 请求按 Token prefix 计数。

### 5.4 文件发送机制

以下机制保持不变：

- Django 负责授权、路径解析和响应头；
- Nginx 负责发送实际文件内容；
- 使用 `X-Accel-Redirect`；
- 支持 HTTP Range 和断点续传；
- 保留 `ETag`、`Last-Modified`、`Content-Length` 和 `Accept-Ranges`；
- 保留根目录、路径穿越和符号链接逃逸检查；
- 不向客户端返回服务器物理路径。

### 5.5 OpenAPI 和使用手册

更新 OpenAPI 契约：

- 公开单文件 `GET/HEAD content`：Bearer Token 可选；
- 内部文件 `GET/HEAD content`：Bearer Token 必需；
- 批次和归档端点：Bearer Token 必需；
- 补充 `401`、`403`、`404` 和 `429` 响应说明；
- 说明匿名请求和 Token 请求的不同限流规则。

## 6. 网页实施

### 6.1 单文件入口

公开文件表格每行提供：

```text
[详情] [下载文件]
```

“下载文件”直接调用公开单文件内容接口，不再要求用户复制带 Token 的命令。

详情抽屉同样提供匿名“下载文件”入口。

### 6.2 多文件入口

用户可以跨分页勾选任意部分文件。选择区必须持续显示去重后的文件数和预计总大小；切换分页、查看详情或调整页面大小时，不得静默丢失已经选择的文件。

选择一个或多个文件后显示：

```text
☑ 同时包含 FASTA 索引（.fai）

[流式调用] [导出所选清单 TSV] [批量获取文件]
```

批量操作提示：

> 批量下载需要数据下载 Token。集群用户请在登录节点运行生成的 CLI 命令，文件将保存到计算节点可读的共享目录。

如果用户分别点击 FASTA 行和 FAI 行的“下载文件”，可以逐个匿名下载；自动组合下载属于多文件批量流程，需要 Token。

“导出所选清单 TSV”必须只导出用户实际勾选的文件，不得导出整个查询结果、整个当前页或完整目录。

当用户勾选“同时包含 FASTA 索引（.fai）”时：

- 将每个已选 FASTA 的明确伴随 FAI 加入清单；
- 按 `file_code` 去重；
- 在导出前更新最终文件数和总大小；
- 没有 FAI 的 FASTA显示警告，但不阻止其余选择导出；
- FAI 关系出现歧义时停止导出，不允许按名称猜选。

例如，用户勾选 20 个目录文件，其中 12 个 FASTA 均有对应 FAI，则页面必须显示：

```text
已选择 32 个下载文件，共 <总大小>
```

导出的文件名固定为：

```text
selected-files.tsv
```

### 6.3 用户选择清单 TSV 契约

`selected-files.tsv` 是“用户选择意图”，不是授权凭证，也不是不可变批次快照。它可以在浏览器端根据已经加载且授权可见的目录数据生成，不要求页面保存或接收用户 Token。

字段必须与现有公开文件目录 TSV 保持一致：

```text
file_code	file_name	accession	assembly	dataset	role	format	size	sha256	content_url
```

字段规则：

| 字段 | 要求 |
| --- | --- |
| `file_code` | 必填；CLI 创建服务器批次时唯一可信的选择标识 |
| `file_name` | 必填；用于页面预览，不能替代 `file_code` |
| `accession` | 可空；多个值沿用现有逗号分隔格式 |
| `assembly` | 可空；多个值沿用现有逗号分隔格式 |
| `dataset` | 可空；多个值沿用现有逗号分隔格式 |
| `role` | 可空；多个值沿用现有逗号分隔格式 |
| `format` | 可空；用于预览和分组 |
| `size` | 必填非负整数；仅用于导出时预览，服务端批次值为最终依据 |
| `sha256` | 必填；仅用于差异提示，服务端批次快照值为最终依据 |
| `content_url` | 必填同源 URL；CLI 不得直接信任或携带 Token 请求该字段 |

导出要求：

- UTF-8 编码；
- 首行固定表头；
- Excel-compatible tab 分隔；
- Unix 换行符；
- 每个 `file_code` 最多出现一次；
- 按用户选择顺序输出，自动加入的伴随文件紧跟对应主文件；
- 不包含 Token、服务器物理路径、内部存储 URI 或数据库主键；
- 公式起始字符等电子表格注入内容必须安全转义或拒绝。

项目当前批次默认限制为最多 1000 个选择器、1000 个解析文件、总大小 500 GiB，批次有效期 24 小时，对应现有配置：

```text
GENEDATA_BATCH_MAX_SELECTORS=1000
GENEDATA_BATCH_MAX_FILES=1000
GENEDATA_BATCH_MAX_BYTES=536870912000
GENEDATA_BATCH_TTL_HOURS=24
```

部署环境可以通过配置收紧这些限制。网页应在导出前提示超限，但最终仍由服务器批次接口执行权威校验。

### 6.4 页面说明

页面顶部说明调整为：

> 公开单文件可直接下载。多文件批量获取、自动包含索引和服务器批次操作需要 GENEDATA_TOKEN。

## 7. `genedata` CLI 设计

### 7.1 匿名查询

```bash
genedata search files \
  --accession IR64 \
  --format FASTA
```

### 7.2 匿名单文件下载

```bash
genedata download FILE000013 \
  --output ./data
```

CLI 在单文件模式下不强制读取 Token。

### 7.3 Token 批量下载

安全输入 Token：

```bash
read -rsp "请输入 GeneData Token: " GENEDATA_TOKEN
echo
export GENEDATA_TOKEN
```

按过滤条件下载：

```bash
genedata download files \
  --format FASTA \
  --limit 100 \
  --include-fai \
  --jobs 2 \
  --output /public/home/$USER/genedata_cache
```

按 Accession 下载：

```bash
genedata download accession IR64 \
  --include genome,genome_index,annotation \
  --output /public/home/$USER/genedata_cache/IR64
```

按 Dataset 下载：

```bash
genedata download dataset DS_IR64_REFERENCE_V1 \
  --output /public/home/$USER/genedata_cache
```

使用 Manifest：

```bash
genedata download manifest selected-files.tsv \
  --preview

genedata download manifest selected-files.tsv \
  --jobs 2 \
  --output /public/home/$USER/genedata_cache
```

其中 `selected-files.tsv` 由公开文件目录中“导出所选清单 TSV”生成。对于 20 个、100 个或其他任意部分文件，用户不需要在命令行重复书写多个 `--file-code`。

CLI也允许通过查询生成同一格式的本地选择清单：

```bash
genedata select files \
  --accession IR64 \
  --include genome,genome_index,annotation \
  --manifest selected-files.tsv
```

### 7.4 选择清单到不可变批次的转换

CLI 读取 `selected-files.tsv` 时必须执行以下步骤：

1. 验证固定表头、UTF-8 编码、行数和字段类型；
2. 提取并按首次出现顺序去重 `file_code`；
3. 将 `file_name`、`size`、`sha256` 和 `content_url` 仅用于预览和差异提示；
4. 不直接使用选择清单中的 `content_url` 发送 Bearer Token；
5. 使用 Token 将 `file_codes` 和 `strict=true` 提交到 `POST /gd/api/v1/file-batches/`；
6. 服务端重新执行发布状态、访问级别、物理文件、内容版本、配额和权限校验；
7. 获取服务器生成的不可变批次 Manifest；
8. 以服务器 Manifest 中的文件名、大小、SHA-256、内容版本和同源 URL 作为下载依据；
9. 如果选择清单与服务器快照不一致，在实际下载前显示差异并停止，要求用户确认或重新导出；
10. 保存 `batch_id`、`snapshot_sha256` 和权威 Manifest，支持审计和恢复。

`--preview` 使用现有批次解析接口验证选择和配额，但不得下载原始文件。正式下载必须创建不可变批次，避免目录内容变化后静默下载不同版本。

### 7.5 批量处理流程

CLI 批量模式依次执行：

1. 查询符合条件的文件；
2. 展示文件数量、类型和总大小；
3. 检查 Token 和所需 scopes；
4. 创建不可变服务器批次；
5. 获取批次 Manifest；
6. 检查目标目录和可用磁盘空间；
7. 默认并发下载 2 个文件；
8. 使用 `.part` 文件和 HTTP Range 续传；
9. 对每个文件执行 SHA-256 校验；
10. 校验通过后原子改名；
11. 生成成功、跳过和失败报告。

不建议默认启动高并发。初始允许 `--jobs 1` 至 `--jobs 4`，默认值为 2。

### 7.6 目录组织

不同材料可能存在同名文件，不能把全部文件无条件平铺到一个目录。建议结构为：

```text
genedata_cache/
├── IR64/
│   └── ASM_IR64/
│       ├── genome.IR64.fasta
│       ├── genome.IR64.fasta.fai
│       └── annotation.IR64.gff
└── ZS97/
    └── ASM_ZS97R53/
        └── ...
```

FASTA 和对应 FAI 必须位于同一分析目录，并保持 `<fasta-name>.fai` 命名。

### 7.7 下载结果报告

批量下载生成：

```text
download-report.tsv
```

至少包含：

```text
file_code
file_name
status
size
sha256
local_path
error_code
```

状态至少包括：

```text
downloaded
cached
skipped
failed
```

## 8. 集群使用方式

集群网络链路固定为：

```text
GeneData REST API
        ↓
登录节点运行 genedata
        ↓
共享目录 /public/home/<user>/genedata_cache/
        ↓
LSF 计算节点读取本地共享文件
```

不得将外部下载命令放入计算节点作业，因为当前计算节点没有外部网络。

CLI 下载属于数据传输任务，不执行高 CPU 计算。大规模或长期传输仍应遵守集群管理员的登录节点使用规则。

## 9. 测试方案

### 9.1 后端权限测试

必须覆盖：

- 公开已发布文件匿名 GET 返回 `200`；
- 公开已发布文件匿名 HEAD 返回 `200`；
- 公开文件匿名 Range 返回 `206`；
- 内部文件匿名请求被拒绝；
- public tier Token 不能访问 internal 文件；
- private、draft、未发布、非当前和校验不完整文件不被匿名发现；
- 缺失物理文件返回 `404`；
- 批次接口无 Token 返回 `401`；
- 批次 Token 权限不足返回 `403`；
- 正确 Token 可以创建和读取批次；
- 匿名和 Token 内容请求使用不同限流桶；
- 匿名分钟限流和日限额生效；
- 关闭功能开关后恢复现有 Token 行为。

### 9.2 CLI 测试

必须覆盖：

- 匿名单文件下载；
- 浏览器导出的 `selected-files.tsv` 可以被 CLI 解析；
- 选择 20 个文件时只创建包含这 20 个文件及明确伴随文件的批次；
- 跨分页选择不会丢失或混入未选择文件；
- 选择清单重复 `file_code` 时稳定去重；
- 缺失表头、重复表头、非法大小、非法摘要和超限行数被拒绝；
- 选择清单中的外域 `content_url`、服务器路径和公式注入内容不能影响下载请求；
- CLI 只将 `file_code` 提交给批次接口，并使用服务器返回的权威 Manifest；
- 选择清单和服务器快照不一致时在下载前停止；
- 多文件无 Token 时在创建批次前停止；
- 正确 Token 批量下载成功；
- FASTA 与 FAI 放在同一目录；
- Range `206` 断点续传；
- 服务端忽略 Range 并返回 `200` 时安全重下；
- SHA-256 错误时不生成正式文件；
- 已下载且摘要正确时跳过；
- 同名文件目录冲突处理；
- 拒绝跨域 `content_url`，防止 Bearer Token 泄露；
- 100 个文件部分失败后可恢复；
- Token 不出现在日志、异常和报告中。

### 9.3 回归测试

必须确认以下现有能力不受影响：

- 文件目录过滤和分页；
- Dataset Manifest；
- 文件批次和快照；
- 服务器归档；
- FASTA region API；
- Nginx protected file serving；
- 已有 Token 的内部数据访问；
- JBrowse 受保护资源访问。

## 10. 生产验收

### 10.1 匿名查询和下载

```bash
BASE_URL="https://example.org"
FILE_CODE="FILE000013"

curl -fsS \
  "$BASE_URL/gd/api/v1/files/?format=FASTA&page_size=1"

curl -fsSI \
  "$BASE_URL/gd/api/v1/files/$FILE_CODE/content/"

curl -fsS \
  -H "Range: bytes=0-1023" \
  -o first_1024.bin \
  "$BASE_URL/gd/api/v1/files/$FILE_CODE/content/"

wc -c first_1024.bin
```

预期结果：

```text
HTTP 206
Content-Length: 1024
Accept-Ranges: bytes
Content-Range: bytes 0-1023/<完整大小>
```

### 10.2 完整文件校验

```bash
curl -fL \
  -o genome.test.fasta \
  "$BASE_URL/gd/api/v1/files/$FILE_CODE/content/"

echo "<预期SHA256>  genome.test.fasta" | sha256sum -c -
```

### 10.3 批次权限

验证：

1. 无 Token 创建批次返回 `401`；
2. 只有 `file:read` 的 Token 创建批次返回 `403`；
3. 具有 `file:read,batch:create,batch:read` 的 Token 创建批次成功；
4. Manifest 文件数量和快照摘要正确；
5. 登录节点批量下载成功；
6. 计算节点能够读取共享目录中的结果。

增加一次网页选择清单的端到端验收：

1. 在公开文件目录跨分页勾选 20 个不同类型的文件；
2. 分别验证勾选和取消“同时包含 FASTA 索引”；
3. 导出 `selected-files.tsv`；
4. 确认 TSV 只包含实际选择及明确伴随文件；
5. 执行 `genedata download manifest selected-files.tsv --preview`；
6. 执行正式下载；
7. 对照服务器批次 Manifest、下载报告和本地文件数量；
8. 逐文件验证 SHA-256；
9. 中断后重新运行，确认已完成文件被跳过、未完成文件继续下载。

### 10.4 限流和日志

验证：

- 匿名请求超过阈值返回 `429`；
- Token 请求不与匿名 IP 限流桶混用；
- 日限额按可信客户端 IP 生效；
- Nginx access log 能定位文件编号、状态码、Range 和传输量；
- 日志不包含 Bearer Token。

## 11. 实施阶段

### 阶段 0：建立集成基线

- 从包含外部文件 API、批次服务和公开文件目录的集成分支创建独立工作树；
- 确认工作树干净；
- 运行当前 Django、Vue、ESLint 和生产构建基线；
- 保存当前 OpenAPI 和生产抽样结果。

### 阶段 1：匿名单文件后端策略

- 增加匿名公开内容判定；
- 增加功能开关；
- 拆分匿名和 Token 限流；
- 更新 API 测试和 OpenAPI；
- 不修改批次和归档权限。

### 阶段 2：网页单文件和批量入口

- 单行提供匿名下载；
- 批量入口继续提示 Token；
- 支持跨分页保留用户选择；
- 增加“导出所选清单 TSV”，只导出实际选择；
- 复用现有目录 TSV 字段契约；
- 在选择清单中按规则加入并去重 FAI；
- 更新中英文说明；
- 保持 FAI 为用户可选项；
- 增加前端源检查和构建验证。

### 阶段 3：独立 `genedata` CLI

- 建立独立 Python 包；
- 实现查询、单文件匿名下载和详情；
- 实现 `selected-files.tsv` 解析、预览和严格校验；
- 根据选择清单中的 `file_code` 创建不可变 Token 批次；
- 实现权威 Manifest、有限并发、续传和摘要校验；
- 生成 wheel 和使用文档；
- 不依赖 Django 运行环境。

### 阶段 4：开发环境验收

- 运行全部后端和前端测试；
- 使用模拟 HTTP 服务验证异常和恢复；
- 在干净 Python 环境安装 wheel；
- 验证 CLI 帮助、查询、单文件和批量命令。

### 阶段 5：生产灰度

- 先部署代码但保持匿名开关关闭；
- 验证原有 Token 下载未回归；
- 开启匿名功能；
- 对一个 FASTA、一个 FAI 和一个非 FASTA 文件做匿名验证；
- 对一个 100 文件批次做 Token 验证；
- 观察限流、Nginx 日志、错误率和带宽；
- 保留关闭开关和版本回退路径。

## 12. 工作量估算

| 工作项 | 估算 |
| --- | --- |
| 后端匿名策略、限流和测试 | 0.5～1 个工作日 |
| 网页入口、跨页选择、选择清单导出和文案 | 0.5～1 个工作日 |
| 通用批量 CLI | 1～2 个工作日 |
| 开发与生产验收 | 0.5 个工作日 |
| 合计 | 2.5～4.5 个工作日 |

估算不包含 Conda 正式发布、服务器归档扩展、账号登录系统和跨平台安装器。

## 13. 回退方案

优先回退方式：

```bash
GENEDATA_ALLOW_ANONYMOUS_PUBLIC_CONTENT=false
```

关闭开关后，公开内容接口恢复为必须提供 `file:read` Token。

如果代码本身存在问题：

1. 部署上一版本前端和 Django 包；
2. 重载应用服务；
3. 保持 Nginx protected location 不变；
4. 重新验证 Token 下载、Range 和 SHA-256；
5. 保留故障时间段日志和请求证据。

本方案不涉及数据库数据删除，因此正常情况下不需要数据回滚。

## 14. 最终验收标准

只有满足以下条件才能标记为完成：

- 公开单文件无需 Token 即可下载；
- 内部、私有和未发布文件没有被匿名暴露；
- 匿名 HEAD、完整 GET 和 Range 请求均正确；
- 匿名限流和日限额生效；
- 批次端点无 Token 无法调用；
- 网页可以把任意部分选择导出为符合契约的 `selected-files.tsv`；
- 选择清单只包含用户选择和明确勾选的伴随文件；
- CLI 根据选择清单创建不可变服务器批次，不直接信任可编辑 URL 和摘要；
- 普通批量 Token 可以下载多种文件类型；
- 100 文件批次可以中断恢复；
- 每个下载文件完成 SHA-256 校验；
- FASTA 和 FAI 配对、命名和目录正确；
- CLI Token 不出现在日志和报告中；
- 登录节点下载、计算节点读取链路通过；
- OpenAPI、网页说明和运维手册与实际行为一致；
- 功能开关和版本回退均已验证。
