# GeneData 外部工具数据 API Dataset Manifest 验证

## 实现范围

- `GET /gd/api/v1/datasets/<dataset>/manifest/`：JSON Manifest。
- `GET /gd/api/v1/datasets/<dataset>/manifest.tsv`：TSV 下载资源，不追加尾斜杠。
- `<dataset>` 优先精确匹配唯一的 `dataset_code`；未命中时聚合同一 `bioproject_accession` 下的全部公开已发布 Dataset。
- 两个接口均要求 Bearer Token 具有 `dataset:manifest` scope，并使用独立的 Manifest 限流。
- Manifest 仅输出 `visibility=public`、`status=released` 的 Dataset 中经过统一访问决策的公开文件。
- 文件还必须满足 `is_current=True`、`publication_status=released`、已发布、SHA-256 有效、物理文件存在且位于受保护根内。
- 响应不包含 `file_path`。

## Accession 归属规则

文件的 Accession 依次从其明确的 Accession、Assembly、Annotation 或 Sample 关系解析。没有文件级关系时，才回退到 `DatasetAccession`。

如果只能得到一个 Accession，JSON 同时返回单值 `accession` 和 `accessions` 列表。如果存在多个候选，`accession` 为 `null`，`accessions` 返回完整排序列表，不任意选择第一项。TSV 的 `accession` 列使用逗号连接全部候选。

## JSON 关键字段

```text
dataset
dataset_codes
count
files[].id
files[].accession
files[].accessions
files[].role
files[].file_name
files[].format
files[].size
files[].sha256
files[].md5
files[].content_version
files[].content_url
```

## TSV 列

```text
accession
file_role
file_name
size
sha256
md5
content_version
url
```

TSV 的 `url` 为绝对 Content API URL，可直接交给 curl、Snakemake 或 Nextflow；实际下载仍需另外具备 `file:read` scope。

## 自动化验证

```powershell
python manage.py test files.tests.api.test_external_dataset_manifest_api_v1 --verbosity 2
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 1
```

结果：Dataset Manifest 定向测试 7 项通过；系统检查通过；没有新增迁移；全量测试 455 项通过、1 项按环境条件跳过。

覆盖场景包括 JSON、TSV、Dataset code、BioProject 聚合、直接 Dataset 外键、Dataset FileRelation、scope、限流、未发布/非 current/缺失/非公开文件过滤、私有或草稿 Dataset 隐藏，以及多 Accession 不猜选。

## 首个 Dataset 发布及真实验证

审计发现原有 289 个 Dataset 均属于 PRJEB73710 草稿私有数据，且没有 Dataset 文件或 Accession 关系，因此没有错误复用这些记录。开发库新建并正式发布：

```text
dataset_id=291
dataset_code=DS_IR64_REFERENCE_V1
dataset_name=IR64 Reference Genome and Annotation v1
dataset_type=genome
visibility=public
status=released
bioproject_accession=null
accession=IR64
DatasetAccession id=1
Dataset FileRelation ids=230,231,232
```

未填写 BioProject，因为现有证据不能把 IR64 参考文件归入 PRJEB73710。Dataset 绑定已经正式发布的三个文件：DataFile 14 FASTA、147 FAI、2 GFF。

使用同时具有 `dataset:manifest` 和 `file:read` 的 1 小时短期 Token 执行：

```powershell
curl.exe -H "Authorization: Bearer <TOKEN>" `
  http://127.0.0.1:8011/gd/api/v1/datasets/DS_IR64_REFERENCE_V1/manifest/

curl.exe -H "Authorization: Bearer <TOKEN>" `
  http://127.0.0.1:8011/gd/api/v1/datasets/DS_IR64_REFERENCE_V1/manifest.tsv
```

结果：JSON 和 TSV 均为 HTTP 200，返回 3 个文件；Accession 均为 IR64，角色分别为 `genome`、`genome_index`、`annotation`；SHA-256 与已发布记录一致；JSON 不包含 `file_path`；DataFile 14 的授权 HEAD 为 200。短期 Token 验证完成后已撤销。

精确回滚时，应先删除 FileRelation 230、231、232，再删除 DatasetAccession 1，最后删除 Dataset 291；三个 DataFile 及其原有关系不应删除或降级。
