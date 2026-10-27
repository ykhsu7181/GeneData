# GeneData CLI

`genedata` 是不依赖 Django 的轻量客户端，支持公开文件查询、匿名单文件下载，以及通过 `selected-files.tsv` 创建受 Token 保护的不可变批次。

## 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install genedata_cli-0.1.0-py3-none-any.whl
genedata --help
```

可通过 `--base-url` 或环境变量配置服务地址：

```bash
export GENEDATA_BASE_URL='https://riceome.hzau.edu.cn'
```

## 查询和匿名单文件下载

```bash
genedata search files --accession IR64 --format FASTA
genedata show FILE000013
genedata download FILE000013 --output ./data
```

公开单文件下载不要求 Token。服务端仍会执行发布状态、访问级别、校验和和物理路径检查。

## 使用网页所选清单

预览会调用服务器批次解析接口，不下载文件：

```bash
read -rsp 'GeneData token: ' GENEDATA_TOKEN && echo
export GENEDATA_TOKEN
genedata download manifest selected-files.tsv --preview
```

正式下载会创建不可变批次、保存权威 Manifest，并在比较网页选择和服务器快照后下载：

```bash
genedata download manifest selected-files.tsv \
  --jobs 2 \
  --output /public/home/$USER/genedata_cache
```

CLI 只把 TSV 的 `file_code` 发送给批次 API；不会使用 TSV 中的 URL 携带 Token。下载 URL、文件名、大小和 SHA-256 均来自服务器权威 Manifest。批量模式要求 Token 同时具有 `batch:create`、`batch:read` 和内容下载所需权限。

批量输出目录会保存：

- `batch-<batch_id>.json`
- `<batch_id>.manifest.json`
- `<batch_id>.manifest.tsv`
- `download-report.tsv`

默认并发数为 2，允许范围为 1 至 4。集群用户应在登录节点执行下载，并把 `--output` 指向计算节点可读的共享目录。
