# GeneData Assembly 页面实施方案评审意见

> 状态：已合并归档。本文件仅作为评审记录，不再作为开发依据；开发与验收统一以修订后的《GeneData Assembly 页面实施方案》为唯一基准。

## 1. 评审结论

总体方案方向合理，能够基于 GeneData 当前的 `Accession → Assembly → Annotation` 数据关系实施，页面结构与现有系统风格也基本一致。

建议在修订下述业务定义、文件选择规则、公共序列化逻辑、权限策略和字段校验后进入开发。

综合评价：**8/10，修订后可实施。**

---

## 2. 已确认的第一版业务口径

### 2.1 Related assemblies

原方案中的 `Revision history` 第一版统一调整为：

```text
Related assemblies
```

中文建议名称：

```text
相关组装
```

业务定义：

```text
Related assemblies
= 当前 Accession 下的全部 Assembly
```

例如：

```text
02428
├── default
├── haplotype-demo
└── v2-polish
```

采用该名称的原因是：同一 Accession 下的多个 Assembly 不一定具有严格的前后修订关系，也可能是不同单倍型、不同组装方法或平行发布版本。第一版尚未建立版本前驱、替代关系或发布日期等信息，因此不使用 `Revision history`。

当前 Assembly 在列表中显示轻量的“当前”状态；其他 Assembly 可以点击并跳转至对应详情页：

```text
/assembly/:assemblyId
```

### 2.2 Related Files

“相关文件”第一版统一定义为：

```text
当前 Accession 范围内的全部相关文件
```

查询边界：

```text
1. 当前 Accession 直接关联的 DataFile
2. 当前 Accession 下全部 Assembly 关联的 DataFile
3. 上述 Assembly 下全部 Annotation 关联的 DataFile
```

第一版不包含其他 Accession 范围内的文件，也不通过 Dataset、Sample 等关系继续向外扩展文件范围。

边界可表达为：

```text
Accession
├── Accession files
├── Assembly A files
│   ├── Annotation A1 files
│   └── Annotation A2 files
└── Assembly B files
    └── Annotation B1 files
```

因此，“相关文件”按钮与“下载”按钮具有不同职责：

```text
下载
→ 下载当前 Assembly 的主基因组 FASTA

相关文件
→ 查看当前 Accession 范围内的全部相关文件
```

推荐直接复用现有 Accession 文件聚合接口：

```text
GET /gd/api/files/accessions/:accession/files/
```

也可以由 Assembly Detail API 返回该接口地址：

```json
{
  "related_files_url": "/gd/api/files/accessions/02428/files/"
}
```

---

## 3. 可直接保留的设计

以下设计与现有项目结构相符，可以保留：

1. 使用 `/assembly/:assemblyId` 作为 Assembly 详情页唯一定位方式。
2. 页面固定为四个主要模块：基本信息、Assembly Statistics、Annotation、Related assemblies。
3. Annotation 只显示当前 Assembly 直接关联的 Annotation。
4. Related assemblies 显示当前 Accession 下的全部 Assembly。
5. 第一版不新增 `AssemblyRevision`、`Chromosome` 或 `AssemblySequence` 模型。
6. Assembly 统计信息使用正式模型字段保存，缺失值统一显示 `-`。
7. Accession 页面与 Assembly 页面共用 Assembly、Annotation 表格组件。
8. 文件下载继续使用现有 DataFile 下载接口：

```text
GET /gd/api/files/data-files/<file_id>/download/
```

9. 页面保持白底、浅蓝背景、细分隔线、弱边框和轻圆角的 GeneData 现有风格。

---

## 4. 必须修订的技术问题

### 4.1 明确主基因组 FASTA 的选择规则

“下载”按钮只下载当前 Assembly 的主基因组 FASTA，但原方案中的“优先 `is_primary=True`”还不足以保证结果唯一。

推荐规则：

1. 只查询当前 Assembly 的直接文件关系；
2. 使用规范且唯一的文件角色，例如 `genome_fasta`；
3. 只选择 `DataFile.is_current=True` 的文件；
4. 优先选择 `FileRelation.is_primary=True`；
5. 出现多个 primary 文件时记录数据错误，不静默任选；
6. 没有 primary 文件时，仅在存在唯一 current FASTA 的情况下允许回退；
7. 没有可用文件时返回 `genome_download_url = null`，前端禁用下载按钮。

建议在导入流程或数据库约束层保证：

```text
同一个 Assembly + file_role 最多只有一个 primary 文件
```

### 4.2 复用公共序列化逻辑

现有 Accession Detail Service 已有 Assembly 和 Annotation 的字段拼装逻辑。新 Assembly Detail Service 不应再维护一套独立的字段兼容规则。

建议抽取：

```python
serialize_assembly(assembly)
serialize_annotation(annotation)
```

由以下接口共同使用：

```text
Accession detail
Assembly detail
```

需要保留并统一测试现有兼容优先级，例如：

```text
assembly_name → display_name → name
assembly_accession → standard_id
annotation_version → release_version
```

### 4.3 统一 API 权限策略

Assembly 前端路由设置了 `requiresAuth: true`，但部分现有 Accession 只读 API 使用 `AllowAny`。

新 API 上线前必须明确统一策略：

```text
方案 A：登录后可访问
方案 B：作为开放数据库公开只读访问
```

不能只依赖前端路由保护接口。后端权限类及测试必须与最终产品策略一致。

### 4.4 增加统计字段校验

建议为新增统计字段增加模型校验、数据库约束或导入校验：

```text
genome_size >= 0
chromosome_count >= 0
contig_count >= 0
n50 >= 0
0 <= gc_content <= 100
```

同时明确：

```text
genome_size 和 n50 以 bp 整数保存
gc_content 保存百分数，例如 43.5，而不是 0.435
Mb、Gb 和 % 仅在展示层格式化
```

### 4.5 明确 `/assembly` 的行为

详情页使用 `/assembly/:assemblyId` 后，仍需明确无参数入口 `/assembly` 的行为。

第一版可选择：

```text
/assembly
→ Assembly 列表或选择页
```

或者：

```text
/assembly
→ 重定向至已有的基因组/品种入口
```

不建议让无 `assemblyId` 的路由直接进入详情组件并产生模糊错误。

---

## 5. 页面与交互修订建议

### 5.1 模块名称

第一版四个模块建议统一为：

| 中文 | 英文 |
| --- | --- |
| 基本信息 | Basic Information |
| 组装统计 | Assembly Statistics |
| 注释版本 | Annotation |
| 相关组装 | Related assemblies |

### 5.2 Assembly accession 标签

效果图中的 `Submitted GenBank assembly` 只适用于 GenBank `GCA_` 编号。如果未来可能展示 RefSeq `GCF_` 编号，推荐使用通用标签：

```text
Assembly accession
```

如业务要求区分来源，可以根据编号或来源字段动态显示 `GenBank assembly` 与 `RefSeq assembly`。

### 5.3 状态处理

除空数据状态外，页面还应包含：

```text
初始加载状态
切换 Related assembly 时的加载状态
接口失败状态与重试入口
Assembly 不存在状态
无权限状态
下载文件缺失状态
```

### 5.4 表格响应式

Annotation 和 Related assemblies 表格需要补充移动端方案：

```text
优先允许表格横向滚动
固定首列或操作列应谨慎使用
窄屏下可隐藏低优先级字段
不能通过强制压缩导致字段难以阅读
```

---

## 6. 修订后的 Assembly Detail API 建议

推荐接口：

```text
GET /gd/api/files/assemblies/<id>/summary/
```

推荐返回结构：

```json
{
  "success": true,
  "data": {
    "assembly": {},
    "accession": {},
    "species": {},
    "statistics": {},
    "annotations": [],
    "related_assemblies": [],
    "genome_download_url": null,
    "related_files_url": "/gd/api/files/accessions/02428/files/"
  }
}
```

字段语义：

```text
annotations
→ 当前 Assembly 的全部 Annotation

related_assemblies
→ 当前 Accession 下的全部 Assembly

genome_download_url
→ 当前 Assembly 主基因组 FASTA 的下载地址

related_files_url
→ 当前 Accession 范围内全部相关文件的查询地址
```

建议将原返回字段 `assemblies` 改为 `related_assemblies`，使 API 字段和页面业务语义一致。

---

## 7. 修订后的测试要求

### 7.1 Backend

```text
✓ 合法 assemblyId 返回正确 Assembly
✓ Assembly 不存在时返回 404
✓ annotations 只包含当前 Assembly 的 Annotation
✓ related_assemblies 只包含当前 Accession 的 Assembly
✓ related_assemblies 不包含其他 Accession 的 Assembly
✓ 当前 Assembly 能被正确识别
✓ 主下载文件只从当前 Assembly 的直接关系中选择
✓ 主下载文件必须为 current genome FASTA
✓ 多个 primary genome FASTA 会被识别为数据异常
✓ 没有可用 genome FASTA 时 genome_download_url 为 null
✓ Related Files 返回当前 Accession 直接关联的文件
✓ Related Files 返回当前 Accession 下 Assembly 关联的文件
✓ Related Files 返回上述 Assembly 下 Annotation 关联的文件
✓ Related Files 不返回其他 Accession 范围内的文件
✓ Related Files 不通过 Dataset、Sample 等关系继续向外扩展范围
✓ 缺失统计字段返回 null
✓ 统计字段导入时执行范围和类型校验
✓ API 权限行为符合最终权限策略
```

### 7.2 Frontend

```text
✓ /assembly/:assemblyId 正常加载
✓ /assembly 无参数入口行为明确
✓ 页面固定为四个主要模块
✓ Related assemblies 替代 Revision history
✓ Annotation 只显示当前 Assembly 的关联项
✓ Related assemblies 显示当前 Accession 的全部 Assembly
✓ 当前 Assembly 有“当前”标记且不重复跳转
✓ 点击其他 Assembly 可切换详情
✓ 下载按钮只下载当前 Assembly 主基因组 FASTA
✓ 无主文件时下载按钮禁用并给出提示
✓ Related Files 显示当前 Accession 范围内的全部相关文件
✓ 缺失数据统一显示 -
✓ 加载、错误、404 和无权限状态正常
✓ 表格在窄屏下可用
✓ 中英文切换正常
✓ Accession 页面能够正确进入 Assembly 详情
```

---

## 8. 推荐实施顺序

### Phase 1：业务契约与数据模型

```text
确认 Related assemblies 命名与返回字段
确认当前 Accession 范围内全部相关文件的查询边界
统一 genome_fasta 文件角色
增加 Assembly 统计字段、校验和 migration
扩展 assembly_manifest.tsv 导入及测试
```

### Phase 2：公共逻辑重构

```text
抽取 serialize_assembly
抽取 serialize_annotation
抽取或补充主基因组文件选择逻辑
保证 Accession 现有接口行为不变
```

### Phase 3：后端接口

```text
实现 Assembly Detail API
实现或扩展 Accession direct files 查询
补齐权限、文件选择和数据边界测试
```

### Phase 4：公共前端组件

```text
AssemblyVersionTable / RelatedAssembliesTable
AnnotationVersionTable
Accession 页面回归测试
```

组件命名可以选择通用的 `AssemblyVersionTable`，但页面标题与用户可见文案必须使用 `Related assemblies`。

### Phase 5：Assembly 页面

```text
基本信息
Assembly Statistics
Annotation
Related assemblies
下载
Related Files Drawer
加载、异常、空状态和响应式适配
```

### Phase 6：入口调整

```text
Accession → Assembly 详情
Related assemblies → 其他 Assembly 详情
明确 /assembly 无参数入口
```

### Phase 7：Genome 页面退出

旧 Genome 页面退出建议单独实施和验收：

```text
先统计并确认旧入口依赖
再添加 /genome-card redirect
最后清理旧组件与测试
```

不建议将旧 Genome 页面删除与 Assembly 详情页首发绑定在同一提交中。

---

## 9. 最终验收口径

```text
✓ Assembly 页面正式替代占位页
✓ 页面包含基本信息、Assembly Statistics、Annotation、Related assemblies
✓ 不再使用 Revision history 文案
✓ Related assemblies 表示当前 Accession 下的全部 Assembly
✓ Related Files 表示当前 Accession 范围内的全部相关文件
✓ 下载只针对当前 Assembly 的主基因组 FASTA
✓ Annotation 只显示当前 Assembly 的 Annotation
✓ 不新增 AssemblyRevision、Chromosome 或 AssemblySequence
✓ 公共序列化逻辑由 Accession 与 Assembly 接口复用
✓ 统计字段具有类型和范围校验
✓ API 权限策略前后端一致
✓ 前后端测试、构建和 Django 测试通过
```

完成以上修订后，该方案可以作为 Assembly 页面第一版的正式开发依据。
