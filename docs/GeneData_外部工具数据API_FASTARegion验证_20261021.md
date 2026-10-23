# GeneData 外部工具数据 API FASTA Region 验证

## 接口

```http
GET /gd/api/v1/assemblies/<assembly_code>/sequence/
    ?sequence=<sequence_id>
    &start=<1-based-inclusive>
    &end=<1-based-inclusive>
```

第一版仅支持普通未压缩 FASTA 和已发布、当前、新鲜、五列完整的 `.fai`。请求要求 Bearer Token 具有 `sequence:read` scope。

## 边界

- `start >= 1`
- `end >= start`
- `end <= sequence length`
- 默认单次不超过 `GENEDATA_SEQUENCE_MAX_BASES=1000000`
- 默认响应不超过 `GENEDATA_SEQUENCE_MAX_RESPONSE_BYTES=1100000`
- 不存在序列：`sequence_not_found`
- 非法坐标：`invalid_region`
- 超过区间上限：`region_too_large`
- 缺失、过期、歧义或无效索引：对应 `fasta_index_*` 错误
- `.fa.gz`/`.fasta.gz`：`unsupported_fasta_compression`

实现通过标准 FAI 的 `offset / line_bases / line_width` 对 FASTA 做二进制 seek，不扫描完整 FASTA。现有只读染色体查询继续兼容两列简化 FAI；Region API 单独要求标准五列 FAI。

## 索引门禁

新增：

```powershell
python manage.py audit_public_fasta_indexes
python manage.py audit_public_fasta_indexes --assembly ASM_IR64
```

状态为 `PASS / MISSING_INDEX / STALE_INDEX / INVALID_INDEX / MISSING_FILE`。失败时命令返回非零状态。

真实 IR64 审计：

```text
assembly_id=131
assembly_code=ASM_IR64
status=PASS
genome_file_id=14
index_file_id=147
sequence_count=12
```

## 真实 curl

使用一小时、仅含 `sequence:read` 的短期 Token 请求：

```powershell
curl.exe -H "Authorization: Bearer <TOKEN>" `
  "http://127.0.0.1:8011/gd/api/v1/assemblies/ASM_IR64/sequence/?sequence=Chr01&start=1&end=120"
```

结果：HTTP 200，`Content-Type: text/x-fasta`，`Content-Length: 144`，`X-Sequence-Id: Chr01`，`X-Sequence-Start: 1`，`X-Sequence-End: 120`，`X-Coordinate-System: 1-based-inclusive`。FASTA 头为：

```text
>ASM_IR64|Chr01:1-120
```

响应包含 120 个碱基。`start=0&end=10` 返回 HTTP 400 和 `invalid_region`。短期 Token 验证完成后已撤销。

## 自动化验证

定向测试覆盖 LF、CRLF、跨行随机访问、鉴权、限流、坐标、序列不存在、区间与响应上限、索引发布状态、新鲜度、压缩 FASTA 拒绝，以及审计命令 PASS/失败行为。

真实 Nginx 的文件 Content API Range `206/416` 仍属于独立部署验证项；Region API 本身由 Django 只返回所请求的小区间，不等同于完整文件 Range 验证。
