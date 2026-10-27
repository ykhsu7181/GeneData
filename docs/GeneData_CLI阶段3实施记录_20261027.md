# GeneData CLI 阶段 3 实施记录

## 1. 结论

阶段 3 的独立 `genedata` CLI MVP 已完成源码实现和 wheel 构建。CLI 位于仓库根目录的 `genedata_cli/`，运行时不导入 Django，也没有第三方 Python 运行依赖，最低支持 Python 3.9。

本阶段未连接生产环境，不代表生产部署或集群验收已经完成。

## 2. 已实现范围

- `genedata search files`：匿名查询公开文件目录；
- `genedata show FILE_CODE`：匿名读取公开文件详情；
- `genedata download FILE_CODE`：匿名下载单个公开文件；
- `genedata download manifest selected-files.tsv --preview`：使用 Token 调用批次解析接口，不下载文件；
- `genedata download manifest selected-files.tsv`：创建严格、不可变服务器批次，获取权威 JSON/TSV Manifest 后下载；
- 严格校验固定 TSV 表头、UTF-8、字段数量、非负大小、SHA-256 和最多 1000 个唯一 `file_code`；
- 只向批次 API 提交选择清单中的 `file_code`，不使用选择 TSV 的 URL 携带 Token；
- 在下载前比较选择清单与服务器快照的文件集合、顺序、名称、大小、SHA-256 和内容 URL；
- 差异存在时停止下载并要求重新导出；
- 同源 URL 和同源重定向检查，防止 Bearer Token 被发送到其他源；
- 1 至 4 个有限并发，默认 2；
- `.part` 断点续传、大小检查、SHA-256 检查和原子改名；
- 已校验目标文件作为缓存复用；现有目标内容不一致时安全失败，不静默覆盖；
- 按 Accession/Assembly 组织目录并拒绝路径穿越；
- 输出批次证据、服务器权威 Manifest 和 `download-report.tsv`。

## 3. 构建结果

构建命令：

```text
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
```

生成物：

```text
genedata_cli/dist/genedata_cli-0.1.0-py3-none-any.whl
SHA256 20e10fa27ce47c182ee8540f1ba97cd7721ef132d98ecc161c1f3a5d50242473
```

`dist/` 是本地构建目录并由 Git 忽略；wheel 可以从已提交源码复现生成。

## 4. 本阶段验证

- CLI 单元测试：12 个通过；
- Python 源码和测试 `compileall`：通过；
- `python -m genedata_cli --version`：输出 `genedata 0.1.0`；
- wheel：成功生成，并确认包含命令入口和全部运行模块。

已覆盖的关键行为包括：

- TSV 首次出现顺序去重；
- 非法表头、大小和摘要拒绝；
- 浏览器选择与服务器快照差异阻断；
- 预览不创建批次、不下载内容；
- 批次请求不携带选择 TSV 的 URL；
- 匿名单文件下载；
- Range 续传、完整 `.part` 恢复和缓存复用；
- 路径穿越、跨域 URL 和跨域重定向拒绝。

## 5. 下一阶段边界

阶段 4 应在干净 Python 环境安装本 wheel，并使用本地模拟 HTTP 服务验证查询、匿名下载、401/403/409/429、Range 恢复、连接中断和摘要不匹配。随后才能进入生产或集群只读验收。
