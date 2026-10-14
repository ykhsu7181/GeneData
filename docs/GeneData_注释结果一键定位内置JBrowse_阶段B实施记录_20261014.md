# GeneData：从注释结果一键定位内置 JBrowse 阶段 B 实施记录

> 实施日期：2026-10-14
> 结论：**阶段 B 的代码与自动化测试已完成；生产试点映射回填尚未执行，因此阶段 B 处于“开发验证通过、生产试点待部署”状态。**
> 操作边界：本轮修改 Django 代码和测试；没有写入生产数据库、生产衍生目录或生产 `FileRelation`。

## 1. 已实现内容

### 1.1 注释结果稳定标识

- `serialize_feature()` 新增只读字段 `feature_id`。
- 注释数据缓存前缀由 `data` 提升为 `data-v2`，防止发布后短期命中缺少 `feature_id` 的旧缓存。
- 新增 `feature_index_version`：由索引 ID、`indexed_at`、源 DataFile ID、大小、mtime 和 MD5 生成 SHA-256。

### 1.2 共享 refName 服务

新增 `files/services/reference_name_service.py`，统一完成：

- 解析 FASTA 标题第一 token，作为 JBrowse refName；
- 解析 `OriSeqID=`，建立 `原始 GFF seqid/OriSeqID -> FASTA 第一 token` 映射；
- 读取并校验 FAI 第一列和序列长度；
- 明确保留一对多歧义，不以后写覆盖前值；
- 生成 Assembly 级 JSON 映射资产；
- 使用临时文件、完整 JSON 校验和 `os.replace()` 原子替换；
- 通过 `DataFile` 和 `FileRelation(file_role=jbrowse_refname_aliases)` 注册映射；
- 使用 schema、算法版本、Assembly ID、FASTA/FAI DataFile ID、大小、mtime 和 MD5 判定过期。

原 `jbrowse_index_service.py` 已改用此共享解析服务，索引构建、映射回填和定位接口不再维护不同的名称转换算法。映射角色没有加入浏览器资源白名单，不能通过 `browser-assets` 直接下载。

### 1.3 可信坐标解析 API

新增只读接口：

```text
GET /gd/api/files/assemblies/<assembly_id>/annotations/<annotation_id>/features/<feature_id>/jbrowse-location/
```

可选查询参数：

```text
feature_index_version=<客户端已知版本>
```

服务端依次验证：

1. Assembly 对外可见，Annotation 确实属于该 Assembly；
2. 指定 Assembly/Annotation 的 JBrowse 状态为 `ready`；
3. AnnotationFeatureIndex 为当前源文件的 `ready` 索引；
4. `feature_id` 属于该 Annotation 当前索引；
5. Assembly 当前 FASTA/FAI 与映射资产指纹一致；
6. 原始 `seqid` 只能映射到唯一 JBrowse refName；
7. `1 <= start <= end <= FAI sequence_length`。

成功响应包含：

- `assembly_id`、`annotation_id`、`feature_id`、`feature_index_version`；
- `ref_name`、精确特征区间和扩展后的视野区间；
- 规范 `loc`；
- 阶段 A 已验证 URL 所需的 `assembly_name` 和 `track_id`。

视野边距采用 `max(ceil(feature_length × 20%), 500 bp)`，并裁剪到序列边界。

### 1.4 失败关闭与错误语义

| HTTP | 代表情况 |
| ---: | --- |
| 400 | 非正整数 ID |
| 404 | Assembly/Annotation/Feature 不存在、不可见或层级错配；统一响应，避免枚举其他上下文对象 |
| 409 | 客户端索引版本冲突或 refName 别名歧义 |
| 422 | 别名缺失或特征坐标越界 |
| 503 | JBrowse、注释索引、FASTA/FAI 或 refName 映射缺失、无效或过期 |

前端后续应读取稳定的 `code` 字段，不解析英文 `detail`。

### 1.5 映射回填命令

新增：

```text
python manage.py backfill_jbrowse_refname_aliases --assembly-id <ID> --dry-run
python manage.py backfill_jbrowse_refname_aliases --assembly-id <ID> --apply
```

批量模式要求 `--report-dir`，并支持：

- `--batch-size`
- `--resume`
- `--retry-failed`
- `--rate-limit-seconds`
- `--output-dir`

命令被登记为 active 生命周期。`--dry-run` 只扫描 FASTA/FAI 并报告，不创建目录、DataFile 或 FileRelation；`--apply` 才原子写入并注册映射。
`--output-dir` 与现有 `build_jbrowse_indexes` 一致，表示 JBrowse 数据根目录；省略时使用 `GENEDATA_JBROWSE_DATA_DIR`。

## 2. 自动化验证

新增测试覆盖：

- W2275 型 `OriSeqID=chr1 -> GWHESLA...` 正向映射；
- 普通 refName、自身别名和一对多歧义保存；
- `feature_id` 出现在注释查询结果；
- 定位响应、500 bp 最小边距和阶段 A URL 所需标识；
- 错误 Assembly/Annotation/Feature 的统一 404；
- 索引版本冲突、索引重建后旧 `feature_id` 失效；
- 映射缺失/过期、JBrowse 未就绪、坐标越界、别名歧义；
- 映射原子生成和 DataFile/FileRelation 注册；
- 单 Assembly dry-run/apply；
- 批量检查点、断点续跑和限速；
- 原 JBrowse 索引构建继续使用相同解析结果。

验证结果：

```text
python manage.py check
System check identified no issues (0 silenced).

DJANGO_SETTINGS_MODULE=filemanager.settings_sqlite_test
python manage.py test files --noinput
Ran 396 tests ... OK (skipped=2)
```

另执行阶段 B 相关的 16 项定向测试并通过。完整回归已包含新增的批处理命令用例。

## 3. 本地真实数据预检结果

本地数据库不是阶段 A 使用的生产快照：

- 本地 IR64 是 Assembly 131，不是生产 Assembly 1400；其 FAI 记录指向 Linux 路径 `/home/ykxu/...`，当前 Windows 环境无法读取，dry-run 返回 `reference_missing`。
- 本地 W2275 是 Assembly 582，不是生产 Assembly 93；当前缺少 Assembly 级主 FASTA 关系，dry-run 返回 `genome_missing`。
- 本地 Assembly 93 是历史 placeholder；Assembly 1400 不存在。

因此本轮没有执行任何 `--apply`，也没有把合成测试映射登记为真实试点资产。这是环境边界，不是生产数据失败结论。

## 4. 阶段 B 剩余生产门禁

代码部署到能够访问生产数据库和生产物理文件的环境后，按以下顺序执行：

```text
python manage.py backfill_jbrowse_refname_aliases --assembly-id 1400 --dry-run
python manage.py backfill_jbrowse_refname_aliases --assembly-id 93 --dry-run
```

只有两项均为 `ready_for_build`、歧义统计符合预期并核对输出目录后，才分别执行 `--apply`。随后验证：

1. 每个 Assembly 只有一个 primary `jbrowse_refname_aliases` 关系；
2. JSON 中 FASTA/FAI 指纹与当前 DataFile 和物理文件一致；
3. 使用生产查询返回的一条 `feature_id` 调用定位 API；
4. W2275 返回 `GWHESLA00000001`，IR64 返回 `Chr01`；
5. 接口不返回物理路径，映射 DataFile 不能由浏览器资产 API 下载。

完成以上生产试点后，阶段 B 才可标记为全部通过并进入生产意义上的阶段 C 联调。目前可以继续开发阶段 C，但前端入口必须保持失败关闭，不能在映射尚未回填的环境中宣称功能可用。
