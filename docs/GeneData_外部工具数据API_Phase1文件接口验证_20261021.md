# GeneData 外部工具数据 API Phase 1 文件接口验证

## 1. 本次实现范围

本次完成 `/gd/api/v1/` 的第一个可调用闭环：

- `GET /gd/api/v1/files/<id>/`：已发布文件元数据；公开元数据允许匿名读取。
- `GET /gd/api/v1/files/<id>/content/`：要求 Bearer Token 和 `file:read` scope。
- `HEAD /gd/api/v1/files/<id>/content/`：执行与 GET 相同的鉴权并返回文件响应头。
- Bearer Token 支持过期、撤销、scope 和 public/internal tier。
- metadata 与 content 使用独立基础限流。
- JBrowse 和 v1 Content API 共用受保护路径、URL 编码和响应头服务。

本次没有实现 Accession 文件发现、Dataset Manifest、FASTA Region，也没有完成真实 Nginx Range 验证。

## 2. 稳定契约

元数据响应不包含 `file_path`。Content 成功响应由 Django 返回：

```text
X-Accel-Redirect
Content-Disposition
Content-Length
Content-Type
ETag
Last-Modified
Accept-Ranges
X-Content-Type-Options
```

生产环境由 Nginx `internal` location 处理实际文件传输。Django 开发服务器不会解释 `X-Accel-Redirect`，因此本机只验证鉴权和响应头，不能据此声称 Range 或文件字节传输已通过。

## 3. 错误边界

| 场景 | HTTP | code |
|---|---:|---|
| Content 未提供 Token | 401 | `authentication_required` |
| Token 无效、过期或已撤销 | 401 | `invalid_token` |
| Token 缺少 scope | 403 | `insufficient_scope` |
| Token tier 不足 | 403 | `insufficient_access_tier` |
| 文件不存在、未发布、非 current、根外或物理文件缺失 | 404 | `not_found` |
| 超过基础限流 | 429 | DRF throttle response |

## 4. 开发机真实数据验证

验证对象：`DataFile id=14`，`FILE000013`，`genome.IR64.fasta`。

匿名 metadata：

```powershell
curl.exe -i http://127.0.0.1:8011/gd/api/v1/files/14/
```

结果：HTTP 200；返回大小 `393143971`、SHA-256、内容版本和 content URL，未返回物理路径。

匿名 HEAD：

```powershell
curl.exe -I http://127.0.0.1:8011/gd/api/v1/files/14/content/
```

结果：HTTP 401。

授权 HEAD：

```powershell
curl.exe -I `
  -H "Authorization: Bearer <TOKEN>" `
  http://127.0.0.1:8011/gd/api/v1/files/14/content/
```

结果：HTTP 200，关键响应头为：

```text
Content-Type: text/x-fasta
X-Accel-Redirect: /_protected_manual_files/genome.IR64.fasta
Content-Length: 393143971
Accept-Ranges: bytes
ETag: "sha256-df205b6bff738e32a72553bd7148c704ad5ff3db885190c7449c6f6864730070"
```

开发 Token：`genescreen-dev-file-read-20261021`，仅有 `file:read`，有效期 24 小时；文档不记录明文。

## 5. 自动化验证

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test files.tests.api.test_external_file_api_v1 `
  files.tests.api.test_jbrowse_asset_api `
  files.tests.unit.test_datafile_access_service --noinput
python manage.py test files --noinput
```

开发环境结果：定向测试 29 项通过、1 项条件跳过；`files` 全量测试 438 项通过、1 项条件跳过。

## 6. 仍待完成

1. 在测试或生产 Nginx 后验证 GET、HEAD、`200/206/416`、Content-Range 和 `curl -C -`。
2. 实现 Accession/Assembly 文件发现 API。
3. 实现 Dataset Manifest。
4. 实现带 `.fai` 的 FASTA Region API。
5. 补充正式 API 文档、Token 轮换和生产监控。
