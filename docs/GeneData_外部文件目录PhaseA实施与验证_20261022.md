# GeneData 外部文件目录 Phase A 实施与验证

## 1. 实施基线

- 分支：`feature/external-file-catalog-all-materials`
- 基线提交：`3776a0df4182c3e61b0fad7f63f62f770d6681f8`
- 权威文件名清单：`E:\filelist (1).txt`
- 清单只作为只读输入，不写入仓库，不依据文件名自动发布数据。

## 2. Phase A 范围

- 新增全仓库文件目录：`GET /gd/api/v1/files/`；
- 精确文件名查询，重名返回全部有权限候选；
- 支持 Accession、Assembly、Dataset、Role、Format 和名称子串过滤；
- 新增稳定 `file_code` 元数据和内容 URL；
- 保留数字数据库 ID 兼容解析；
- Dataset Manifest 和 Accession 文件发现改用稳定内容 URL；
- 支持 ETag、`If-None-Match`、`If-Modified-Since` 和 HEAD；
- 增加 `DataFile.file_name` 数据库索引；
- 增加权威文件名清单覆盖率审计命令。

## 3. 安全边界

- 只返回已发布、当前、摘要有效、权限允许且物理文件存在的记录；
- 权限过滤发生在结果计数之前；
- API 不返回物理路径或受保护根目录；
- 文件名仅用于数据库查询，不能转换为文件系统路径；
- 重名文件不自动选择；
- 清单中未注册的名称不会自动创建 `DataFile`。

## 4. 全量文件名清单结果

开发机只读审计输出目录：

```text
D:\gene_manage_system\external_file_catalog_audit_20261022
```

结果：

| 指标 | 数量 |
|---|---:|
| 输入文件名 | 2,272 |
| Unicode/大小写规范化后唯一名称 | 2,272 |
| 开发库已注册 DataFile | 154 |
| 与清单唯一精确匹配 | 14 |
| 清单中尚未注册 | 2,258 |

该结果不表示 2,258 个物理文件丢失，只表示它们尚未以相同文件名注册为 `DataFile`。后续注册仍需要真实物理路径、材料关系、文件角色、大小、SHA-256、索引状态和发布审批。

## 5. 后续边界

Phase A 完成后，Phase B 才实现多选择器批量解析和不可变批次 Manifest。全部材料可下载还需要继续执行：

```text
物理文件盘点
→ Accession/Assembly/Dataset 关系匹配
→ SHA-256 与索引验证
→ 歧义人工审核
→ dry-run 发布
→ 分批 apply
→ Production Canary
```
