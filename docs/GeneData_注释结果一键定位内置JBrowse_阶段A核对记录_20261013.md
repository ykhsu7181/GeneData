# GeneData：从注释结果一键定位内置 JBrowse 阶段 A 核对记录

> 核对日期：2026-10-13
> 结论：**阶段 A 通过，可以进入阶段 B。** 选定固定版兼容方案为 `config + assembly + loc + tracks`。
> 操作边界：本次只读核对生产 API、浏览器资源和既有衍生文件；未修改生产数据库、文件关系、JBrowse 配置或原始 FASTA/GFF。

## 1. 固定版本与试点对象

生产 `/jbrowse2/version.txt` 返回 `4.3.0`。两个试点组合在 2026-10-13 复核时均为 `ready`：

| 试点 | Assembly | Annotation | JBrowse assembly | 注释轨道 |
| --- | ---: | ---: | --- | --- |
| W2275 | 93 | 93 | `assembly-93` | `annotation-93-features` |
| IR64 | 1400 | 697 | `assembly-1400` | `annotation-697-features` |

状态与配置分别来自现有只读接口：

- `/gd/api/files/assemblies/<assembly_id>/jbrowse-status/`
- `/gd/api/files/assemblies/<assembly_id>/jbrowse-config/`

## 2. 数据配对与 refName 核对

### 2.1 W2275（Assembly 93 / Annotation 93）

选取注释查询结果中的一条可见基因：

- 原始 GFF 记录：`chr1:46518902-46519297`，`ID=evm.TU.W2275_009.1`，负链；
- FASTA 第一条标题：`>GWHESLA00000001 ... OriSeqID=chr1 Len=46528754`；
- FAI 第一列及长度：`GWHESLA00000001`、`46528754`；
- 当前 JBrowse 压缩 GFF3 中同一 ID 的记录位于 `GWHESLA00000001:46518902-46519297`，仅命中 1 条；
- 采用 500 bp 最小边距后，试点视野为 `GWHESLA00000001:46518402-46519797`。

因此映射方向得到实物验证：

`原始 GFF seqid/OriSeqID chr1 -> FASTA 第一 token GWHESLA00000001 -> FAI/JBrowse refName GWHESLA00000001`

不存在一对多配对歧义，且坐标位于 FAI 长度范围内。

### 2.2 IR64（Assembly 1400 / Annotation 697）

选取注释查询结果中的一条可见基因：

- 原始 GFF 记录：`Chr01:39050008-39051201`，`ID=gene:OsIR64_01g0040650`，正链；
- FASTA 第一条标题：`>Chr01`；
- FAI 第一列及长度：`Chr01`、`44350042`；
- 当前 JBrowse 压缩 GFF3 中同一 ID 保持为 `Chr01:39050008-39051201`；
- 采用 500 bp 最小边距后，试点视野为 `Chr01:39049508-39051701`。

IR64 是原始 `seqid` 与 JBrowse refName 相同的对照样本，同样无歧义且未越界。

## 3. 当前衍生资产与传输能力

| 试点 | FASTA | FAI | GFF3.gz | TBI |
| --- | --- | --- | --- | --- |
| W2275 | DataFile 1468，418,243,111 B | 2382，5,640 B | 2383，4,146,173 B | 2384，79,306 B |
| IR64 | DataFile 1143，393,143,971 B | 2379，362 B | 2380，10,352,611 B | 2381，73,678 B |

两个 GFF3 浏览器资产的字节范围请求均返回 HTTP `206` 和 `Content-Range`。这证明当前生产交付路径满足 JBrowse 随机访问的基础条件；本次没有重新生成或替换任何索引。

## 4. JBrowse 4.3.0 URL 兼容矩阵

使用本机已安装的 Edge 154 无头模式，直接加载生产 `/jbrowse2/` 与生产动态配置。浏览器连接器当时没有可用浏览器表面，因此使用 Chrome DevTools Protocol 读取渲染后的页面文本作为替代证据。

| 方案 | 固定版结果 | 判定 |
| --- | --- | --- |
| `config + loc + extendSession=true` | W2275 页面没有启动线性基因组视图，只显示 “Select a view to launch”；未出现目标 refName、坐标、轨道或目标基因 | **不采用** |
| `config + assembly + loc + tracks` | W2275 显示 `GWHESLA00000001`、约 46,518,000–46,519,600 的刻度、`W2275 genome annotation` 轨道及 `W2275_009.1`；IR64 显示 `Chr01`、约 39,049,600–39,051,600 的刻度、`IR64 annotation` 轨道及 `gene:OsIR64_01g0040650` | **通过并选定** |
| 后端改写 `defaultSession.init.loc` | 未执行 | 方案二已通过，无需进入兜底方案 |

选定的 URL 结构为：

```text
/jbrowse2/?config=<URL 编码的当前 Assembly 动态配置 URL>
  &assembly=<解析接口返回的 assembly_name>
  &loc=<URL 编码的 ref_name:view_start-view_end>
  &tracks=<解析接口返回的 track_id>
```

实现时必须逐项使用 `URLSearchParams`/等价 API 编码，不手工拼接未编码值。iframe 与“新窗口打开”必须共用同一 URL 构造函数。

## 5. 阶段 A 门禁结论

| 门禁 | 结果 |
| --- | --- |
| IR64 和 Assembly 93 各找到一条生产可见特征 | 通过 |
| 核对原始 GFF、FASTA 第一 token、OriSeqID、FAI 与当前 JBrowse GFF | 通过 |
| W2275 的名称转换方向明确且无歧义 | 通过 |
| 两个试点的配置、参考序列和指定注释轨道均为 `ready` | 通过 |
| 在 JBrowse Web 4.3.0 选定能保留轨道的定位 URL | 通过：`config + assembly + loc + tracks` |

阶段 A 因而标记为完成。下一步进入阶段 B，但仍须按实施方案新增服务端可信坐标解析、索引版本校验和 Assembly 级 refName 映射资产；本次人工核对结果不能替代这些运行时防护。

## 6. 尚未完成的事项

- 当前注释查询响应仍没有 `feature_id`，这与阶段 B 开发前状态一致。
- 尚未增加坐标解析 API、共享 refName 服务、映射资产或回填命令。
- 尚未执行阶段 B/C/D 的后端与前端自动化测试。
- 尚未验证未来实现中的返回路径校验、请求取消、缓存失效及索引重建行为。

以上事项不属于阶段 A 通过条件，不应被表述为已经验证。
