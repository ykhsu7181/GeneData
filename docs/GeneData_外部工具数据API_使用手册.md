# GeneData 外部工具数据 API v1 使用手册

适用版本：OpenAPI `1.6.0`。机器可读契约位于 `/gd/api/v1/openapi.json`，简明入口位于 `/docs/api/`。

## 1. 基本约定

- 生产基址示例：`https://riceome.hzau.edu.cn`。
- Token 只放在 `Authorization: Bearer ...` 请求头，不放在 URL、脚本源码、Git 或任务名称中。
- FASTA Region 坐标为 **1-based inclusive**；`start=1&end=120` 返回 120 bp。
- 文件内容由 API 鉴权后交给 Nginx 发送。调用方无需先把 FASTA 下载到 GeneData 应用服务器；分析工具若支持 URL/流输入可直接消费。需要随机访问或工具只接受路径时，调用方仍应下载到自己的任务工作目录，并同时下载索引。
- JSON/TSV Manifest 不返回服务器物理路径，只返回受控 API URL、校验和与版本。
- 已发布且有效访问级别为 `public` 的单个文件可匿名下载；内部文件、批次、归档、Dataset Manifest 和序列接口仍需相应 Token。

## 2. 安全地配置 Token

Linux/macOS：

```bash
read -rsp 'GeneData token: ' GENEDATA_TOKEN && echo
export GENEDATA_TOKEN
export GENEDATA_BASE_URL='https://riceome.hzau.edu.cn'
```

PowerShell：

```powershell
$SecureToken = Read-Host 'GeneData token' -AsSecureString
$TokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
$env:GENEDATA_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($TokenPointer)
$env:GENEDATA_BASE_URL = 'https://riceome.hzau.edu.cn'
```

结束后清除变量；不要启用会展开请求头的 shell trace 或 `curl -v` 日志。

## 3. curl 调用

公开发现接口可匿名使用：

```bash
curl --fail-with-body --silent --show-error \
  "$GENEDATA_BASE_URL/gd/api/v1/accessions/IR64/"

curl --fail-with-body --silent --show-error \
  "$GENEDATA_BASE_URL/gd/api/v1/accessions/IR64/files/?role=genome&format=FASTA"
```

按文件名查询全部已发布且有权访问的仓库文件；重名时返回多个候选：

```bash
curl --get --fail-with-body --silent --show-error \
  --data-urlencode "file_name=genome.fasta" \
  "$GENEDATA_BASE_URL/gd/api/v1/files/"

curl --get --fail-with-body --silent --show-error \
  --data-urlencode "file_name=genome.fasta" \
  --data-urlencode "accession=IR64" \
  --data-urlencode "role=genome_fasta" \
  "$GENEDATA_BASE_URL/gd/api/v1/files/"
```

查询响应中的 `file_code`、Accession、Assembly、Dataset 和 Role 用于消歧。调用方不得在重名时默认选择第一项。

获取 Dataset Manifest：

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/datasets/DS_IR64_REFERENCE_V1/manifest/"

curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  -o DS_IR64_REFERENCE_V1.manifest.tsv \
  "$GENEDATA_BASE_URL/gd/api/v1/datasets/DS_IR64_REFERENCE_V1/manifest.tsv"
```

匿名下载单个公开文件并校验：

```bash
curl --fail-with-body --location \
  -o reference.fa \
  "$GENEDATA_BASE_URL/gd/api/v1/files/FILE000013/content/"
sha256sum reference.fa
```

数字数据库 ID 下载地址在兼容期内仍可使用，但新脚本和 Manifest 必须使用稳定 `file_code`。可用 ETag 避免重复传输：

```bash
curl --fail-with-body --location \
  --etag-save FILE000013.etag \
  --etag-compare FILE000013.etag \
  -o reference.fa \
  "$GENEDATA_BASE_URL/gd/api/v1/files/FILE000013/content/"
```

请求 Region：

```bash
curl --fail-with-body --silent --show-error \
  -H "Authorization: Bearer $GENEDATA_TOKEN" \
  "$GENEDATA_BASE_URL/gd/api/v1/assemblies/ASM_IR64/sequence/?sequence=Chr01&start=1&end=120" \
  -o IR64.Chr01.1-120.fa
```

## 4. Python、R 与任务引擎

Python：

```python
import os
import requests

base = os.environ["GENEDATA_BASE_URL"].rstrip("/")
headers = {"Authorization": f"Bearer {os.environ['GENEDATA_TOKEN']}"}
response = requests.get(
    f"{base}/gd/api/v1/assemblies/ASM_IR64/sequence/",
    params={"sequence": "Chr01", "start": 1, "end": 120},
    headers=headers,
    timeout=60,
)
response.raise_for_status()
open("IR64.region.fa", "wb").write(response.content)
```

R：

```r
library(httr2)
base <- Sys.getenv("GENEDATA_BASE_URL")
token <- Sys.getenv("GENEDATA_TOKEN")
resp <- request(paste0(base, "/gd/api/v1/datasets/DS_IR64_REFERENCE_V1/manifest/")) |>
  req_headers(Authorization = paste("Bearer", token)) |>
  req_perform()
manifest <- resp_body_json(resp)
```

Snakemake：

```python
rule ir64_region:
    output: "IR64.Chr01.1-120.fa"
    shell:
        "curl --fail-with-body --silent --show-error "
        "-H \"Authorization: Bearer $GENEDATA_TOKEN\" "
        "\"$GENEDATA_BASE_URL/gd/api/v1/assemblies/ASM_IR64/sequence/?sequence=Chr01&start=1&end=120\" "
        "-o {output}"
```

Nextflow：

```nextflow
process IR64_REGION {
  output: path 'IR64.region.fa'
  script:
  """
  curl --fail-with-body --silent --show-error \
    -H "Authorization: Bearer \$GENEDATA_TOKEN" \
    "\$GENEDATA_BASE_URL/gd/api/v1/assemblies/ASM_IR64/sequence/?sequence=Chr01&start=1&end=120" \
    -o IR64.region.fa
  """
}
```

## 5. `genedata` CLI

从仓库构建 wheel：

```bash
cd genedata_cli
python3 -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
python3 -m pip install dist/genedata_cli-0.1.0-py3-none-any.whl
```

查询、详情和匿名单文件下载：

```bash
genedata search files --accession IR64 --format FASTA
genedata show FILE000013
genedata download FILE000013 --output ./data
```

使用网页导出的所选清单：

```bash
genedata download manifest selected-files.tsv --preview
genedata download manifest selected-files.tsv \
  --jobs 2 \
  --output /public/home/$USER/genedata_cache
```

预览和正式批次均要求 `GENEDATA_TOKEN`。CLI 只采信选择清单中的 `file_code`；正式下载使用服务器不可变 Manifest 中的文件名、大小、摘要和同源内容地址。选择清单和服务器快照不一致时会在下载前停止。

## 6. 状态码处理

| 状态码 | 含义 | 调用方动作 |
| --- | --- | --- |
| 400 | 查询参数或坐标错误 | 修正请求，不重试原请求 |
| 401 | 缺少 Token | 添加 Bearer Token |
| 403 | Token 无效、已撤销、权限或访问级别不足 | 停止任务并联系管理员 |
| 404 | 资源不存在或为防泄露而隐藏 | 核对标识符与发布状态 |
| 409 | Assembly 歧义或 FASTA/索引状态冲突 | 停止任务并报告运维 |
| 413 | Region 超过限制 | 拆分区间 |
| 416 | Range 超出文件范围 | 修正 Range |
| 429 | 触发限流 | 按 `Retry-After` 退避，不要并发重试 |

生产任务应保存 Manifest、响应头、文件 SHA-256 和 API 版本作为可重复性证据，但不得保存 Token。
