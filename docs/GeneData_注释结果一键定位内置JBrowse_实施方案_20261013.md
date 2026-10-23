# GeneData：从注释结果一键定位到内置 JBrowse 实施方案

> 编写日期：2026-10-13
>
> 状态：阶段 A 已通过；阶段 B 的代码与开发验证已完成，但生产 Assembly 93/1400 的映射回填仍待部署环境执行；阶段 C 的前端代码及开发环境真实页面联调已完成；阶段 D 的开发环境回归已通过。阶段 E-0 已完成代码边界、回归、候选 SHA 清单、生产门禁和独立实施提交 `0cb0fb4`，下一步从最终提交的干净 worktree 生成并校验正式发布包；生产验证未执行。详见 [阶段 A 核对记录](GeneData_注释结果一键定位内置JBrowse_阶段A核对记录_20261013.md)、[阶段 B 实施记录](GeneData_注释结果一键定位内置JBrowse_阶段B实施记录_20261014.md)、[阶段 C 实施记录](GeneData_注释结果一键定位内置JBrowse_阶段C实施记录_20261014.md)、[阶段 D 实施记录](GeneData_注释结果一键定位内置JBrowse_阶段D实施记录_20261014.md)和 [阶段 E-0 收口记录](GeneData_注释结果一键定位内置JBrowse_阶段E0生产发布前收口记录_20261014.md)。

## 1. 目标与边界

在注释结果表中，用户点击某条特征的“在基因组浏览器中查看”，进入同一 Assembly、同一 Annotation 的内置 JBrowse 2，并定位到该特征的序列和坐标区间；原有参考序列与注释轨道保持可见，用户可返回原筛选/分页上下文。

首期只支持**有注释结果索引且 JBrowse 状态为 `ready`** 的记录。`reference_only` 组装没有对应注释轨道，不提供该按钮；序列不匹配等未就绪组装保持禁用，不通过此功能绕过预检。暂不实现按基因名称全文检索、自动打开特征详情弹窗、跨组装坐标转换，也不修改原始 FASTA/GFF。

本轮生产验收记录为：574 条新建浏览器组装中 482 条 `ready`、92 条 `reference_only`，另有 IR64 已 `ready`；32 条因 `seqid_mismatch` 暂缓。Django 注释特征索引的 517/517 `ready` **不等于**这些组装的 JBrowse 全部就绪。上述数字是历史基线，不是本功能的验收结果；详见 [本轮部署验收总结](GeneData_JBrowse2生产部署本轮验收总结_20261013.md)。

## 2. 现有实现与关键风险

| 层面 | 当前实现 | 本功能需要补充 |
| --- | --- | --- |
| 注释结果 | `AnnotationView.vue` 调用 `/files/query/annotation-data/`；结果含 `seqid/start/end`，页面已有 Assembly、Annotation、筛选和分页上下文 | 行级入口和可定位状态；结果需有可回查的特征 ID |
| Django 索引 | 阶段 B 已让 `serialize_feature` 返回 `feature_id`，并新增当前索引版本、refName 映射及可信定位接口 | 阶段 C 使用定位接口返回值，不信任前端表格中的 `seqid/start/end`；生产环境仍需先回填映射资产 |
| 浏览器入口 | Vue 路由 `/assembly/:assemblyId/browser`；`GenomeBrowserView.vue` 根据 `annotation_id` 获取状态和配置，并在 iframe 中加载 `/jbrowse2/?config=...` | 接收受校验的定位参数，并同时用于 iframe 与“新窗口打开” |
| JBrowse 索引 | 构建时依据 FASTA 头的 `OriSeqID=` 将 GFF `seqid` 映射为 FASTA 标题第一个空白分隔 token，再写入压缩 GFF3；该 token 同时是 `.fai` 第一列和 JBrowse `refName` | 定位必须使用这个 **JBrowse refName**，不能直接把注释表的原始 `seqid` 拼入 URL，也不能把 `OriSeqID` 误当成最终 refName |

例如原始 GFF 的序列名可与 FASTA 主 ID 不同，而浏览器轨道已采用主 ID。若仅用 `row.seqid + ':' + row.start + '-' + row.end`，有些组装会跳到不存在的序列，或出现空轨道。项目现有通用 FASTA 解析器把 `OriSeqID` 称作 canonical ID，而 JBrowse 构建服务的目标名称是 FASTA 标题第一 token；两者语义相反，实现时不得直接复用前者作为浏览器 refName。另需防止坐标越界、Annotation 与 Assembly 错配、旧特征 ID 对应重建后的不同索引，以及 `return_to` 的站外跳转。

## 3. 建议的最小闭环

### 3.1 服务端坐标解析

1. `serialize_feature` 增加只读字段 `feature_id`，不改变既有字段；查询接口仍按现有分页返回。
2. 新增只读接口，建议 `GET /gd/api/files/assemblies/<assembly_id>/annotations/<annotation_id>/features/<feature_id>/jbrowse-location/`。参数都是正整数；客户端不提交 `seqid/start/end` 作为可信定位依据。
3. 服务端沿用现有可见 Assembly 的查询规则，确认 Annotation 属于该 Assembly；复用现有 JBrowse 状态判定，要求**指定 Annotation** 为 `ready`，而非只检查该 Assembly 的默认注释。
4. 复用注释源文件与 `AnnotationFeatureIndex` 的 `ready`/新鲜度检查，并确认 `feature.feature_index_id` 正是该 Annotation 当前的索引。响应同时带不可变的 `feature_index_version`（可由索引 ID、`indexed_at` 和源文件指纹组成）；索引重建后旧 `feature_id` 或旧版本无效时返回明确错误，不跳转到相似特征。
5. 把特征的原始 `seqid` 按固定方向解析为当前 FASTA 标题第一 token：`原始 GFF seqid/OriSeqID -> FASTA 第一 token -> .fai 第一列/JBrowse refName`。使用当前 `.fai` 校验序列存在以及 `1 <= start <= end <= sequence_length`。别名缺失、歧义、映射过期或坐标越界均停止定位，不猜测映射。
6. 区分特征精确区间和浏览器视野区间。保留 `feature_start`、`feature_end`；用于浏览器的 `view_start`、`view_end` 默认向两侧扩展 `max(特征长度 × 20%, 500 bp)`，并裁剪到 `[1, sequence_length]`，避免短 exon/CDS 被放大到失去上下文。首期仍不承诺自动选中特征。
7. 成功时返回最小 JSON，例如 `assembly_id`、`annotation_id`、`feature_id`、`feature_index_version`、`ref_name`、`feature_start`、`feature_end`、`view_start`、`view_end`、`loc`、JBrowse `assembly_name` 与 `track_id`。只返回公开数据标识和坐标，不暴露服务器文件路径。
8. 固定错误语义：非法 ID/参数返回 `400`；对象不可见、不存在或层级错配统一返回 `404`，不得借响应差异枚举其他上下文的特征；别名歧义或索引版本冲突返回 `409`；坐标/别名无法定位返回 `422`；依赖索引或映射未就绪、已过期返回 `503`。前端按错误代码展示可理解的提示，不解析英文错误字符串。

### 3.2 refName 映射资产与生命周期

1. 映射是 **Assembly 级衍生资产**，推荐角色固定为 `jbrowse_refname_aliases`，通过 `FileRelation(related_type=assembly)` 管理；映射文件不加入公开浏览器资源白名单，也不直接返回给前端。
2. 映射方向固定为 `原始 GFF seqid/OriSeqID -> FASTA 标题第一 token`。每条记录保存别名、目标 refName 和状态；一个别名对应多个 refName 时显式保存为歧义，禁止以后写值覆盖以前写值。
3. 映射 JSON 至少记录 schema/解析算法版本、Assembly ID、FASTA DataFile ID/大小/mtime/MD5、FAI DataFile ID/大小/mtime/MD5、生成时间和歧义统计。FASTA、FAI、文件关系或解析算法版本任一变化，映射立即判为过期。
4. 把当前 JBrowse 构建服务中的别名解析抽成共享的 `reference_name` 服务，由索引构建、映射回填和定位接口共同调用；不得直接把现有 `parse_sequence_id()`/`build_sequence_aliases()` 的 OriSeqID 输出当成 JBrowse refName，也不得维护两套映射算法。
5. 映射必须先写临时文件、完整校验后原子替换并注册关系。不能取得可信映射时，入口禁用或解析失败，绝不退回“原始名称直接拼 URL”。
6. 已建成的组装提供独立的可断点、限速回填命令：只读扫描 FASTA 头并核对现有 `.fai`，生成映射，不重建 GFF/Tabix、不修改源文件。报告逐项记录成功、跳过、歧义、过期和失败原因。

### 3.3 前端交互、路由与固定版兼容

1. 注释表增加操作列。对当前选中的 Assembly/Annotation 请求一次浏览器状态，缓存键必须为 `assembly_id + annotation_id`；切换上下文时取消旧请求并防止旧响应覆盖新状态，不按行发状态请求。`ready` 时允许点击，其他状态隐藏/禁用并说明原因。图形视图不在首期范围内。
2. 点击后调用上述解析接口。成功才跳转 `assembly-browser`，路由查询保留 `annotation_id`、解析后的规范 `loc`，以及指向当前注释页筛选/分页状态的 `return_to`；请求期间显示加载态，阻止重复点击。失败留在原页。
3. `GenomeBrowserView.vue` 仅在当前 Assembly/Annotation 状态 `ready` 且 `loc` 格式可接受时生成定位 URL。同一 URL 用于 iframe 和“新窗口打开”；若无 `loc`，现有 Assembly 详情入口行为不变。
4. 在编码前用项目固定的 JBrowse Web 4.3.0 完成 URL 参数兼容矩阵，不把最新版文档能力直接视为固定版能力。按顺序验证并记录：① `config + loc + extendSession=true` 是否在 `defaultSession` 上导航并保留注释轨道；② 若①不支持，显式使用解析接口返回的 `assembly_name`、`track_id` 组合 `config + assembly + loc + tracks`；③ 若②仍不稳定，由后端生成带目标 `defaultSession.init.loc` 的受校验动态配置。必须选定一个在 4.3.0 上实测通过的方案后才进入前端批量开发。
5. 建立前端共享的内部路径校验器供 Annotation 和 GenomeBrowser 页面复用。只允许明确的本应用路由；拒绝 `//host`、协议/主机、反斜杠、控制字符、重复解码后变成站外地址的值以及不在白名单中的路径。浏览器页不可把任意外部 URL 作为 `return_to`。
6. 生成可分享的坐标 URL 时使用规范 `loc` 与 Assembly/Annotation ID，不以可能随注释索引重建而变化的 `feature_id` 作为长期链接标识。此 URL 表示**定位区域**，不承诺自动选中某条特征；直接打开分享 URL 时仍需完成状态检查和 `loc` 长度/格式限制。

JBrowse 官方文档支持 `loc` 坐标参数，并说明单独使用 `loc` 会开启新会话；`extendSession=true` 可在 `defaultSession` 上导航。文档当前内容可能晚于项目部署的 JBrowse Web 4.3.0，因此上述组合必须在**项目实际固定版本**上实测，不能仅凭最新文档判定已兼容。参考：[URL 参数](https://jbrowse.org/jb2/docs/urlparams/)、[Assembly 序列名别名配置](https://jbrowse.org/jb2/docs/config_guides/assemblies/)。首期由后端解析到规范名，不依赖额外启用 JBrowse `refNameAliases`。

## 4. 分阶段实施与门禁

| 阶段 | 工作 | 通过条件 |
| --- | --- | --- |
| A：试点核对（已通过） | 已固定 IR64（Assembly 1400 / Annotation 697）与 W2275（Assembly 93 / Annotation 93），核对原始 GFF `seqid`、FASTA 第一 token、OriSeqID、`.fai`、当前 JBrowse 状态及部署版本；完成 4.3.0 URL 参数兼容矩阵 | 已找到各一条可见特征；Assembly 93 的 `OriSeqID -> FASTA 第一 token` 映射无歧义；已选定 `config + assembly + loc + tracks`。证据见 [阶段 A 核对记录](GeneData_注释结果一键定位内置JBrowse_阶段A核对记录_20261013.md) |
| B：后端（开发验证通过，生产试点待回填） | 已增加 `feature_id`/索引版本、共享 refName 服务、Assembly 级映射资产、坐标解析 API 和可恢复回填命令；本地试点物理文件环境与生产不一致，未执行生产 `--apply` | 自动化测试已覆盖正确配对、错误配对、过期、歧义、越界、索引重建、映射方向和固定错误码；生产 Assembly 93/1400 的 dry-run、apply 和接口实测仍是关闭阶段 B 的门禁。详见 [阶段 B 实施记录](GeneData_注释结果一键定位内置JBrowse_阶段B实施记录_20261014.md) |
| C：前端（开发环境通过，生产待验证） | 已增加行级按钮、按 Assembly/Annotation 组合缓存的状态门禁、请求取消和防旧响应污染、可信定位 API 调用、路由传参、固定版 JBrowse selected-mode URL、共享返回路径校验及中英文文案 | 开发 Assembly 131 / Annotation 131 已从真实注释表进入 JBrowse，定位、轨道、新窗口入口和返回上下文均通过；生产 IR64/Assembly 1400 与 W2275/Assembly 93 仍待验证。详见 [阶段 C 实施记录](GeneData_注释结果一键定位内置JBrowse_阶段C实施记录_20261014.md) |
| D：回归（开发环境已通过，生产待验证） | 已完成 Django 跨接口集成回归、完整后端/前端测试、lint/build、独立 `location_ready` 门禁，以及开发环境固定版 JBrowse 与 Network 检查 | 开发环境四类资产均返回真实 206 Range；目标基因和正确 Annotation 轨道可见；返回原筛选上下文通过。生产环境未触碰，不能据此宣称生产可用 |
| E-0：发布前收口（实施提交完成，正式包待生成） | 已固定 27 个候选代码文件、排除无关脏文件、复跑完整回归、生成提交前 SHA 清单、定义生产 dry-run/apply/回滚门禁，并创建推送实施提交 `0cb0fb4` | 从最终提交的干净 detached worktree 重新测试、打包并独立校验；提交前快照不得部署。详见 [阶段 E-0 收口记录](GeneData_注释结果一键定位内置JBrowse_阶段E0生产发布前收口记录_20261014.md) |
| E-1：生产试点与扩展 | 先对 Assembly 1400/93 做只读核对和映射 dry-run；通过后逐个 apply 和全链路验收，再考虑批量处理其他 `ready` 组装 | 只对映射已验证且状态 `ready` 的组合放行；保留失败清单、断点、页面/Range 证据和回滚材料 |

建议自动化测试位置：`django2/files/tests/api/`、`django2/files/tests/unit/` 及 `vue_project/tests/`。`serialize_feature` 增加字段后需提升 `annotation-data` 缓存键版本或在发布时定向清理旧缓存，避免旧缓存短期缺少 `feature_id`；前端对无 `feature_id` 的行失败关闭。前端现有脚本为 `npm run test`、`npm run lint`、`npm run build`；后端按项目现有测试设置执行，勿把本地通过等同于生产已通过。

验收用例至少包含：

- IR64：普通序列名，点击后定位区间及上下文边距正确，参考序列和注释轨道可见。
- Assembly 93：原始 GFF `seqid` 按固定方向经 `OriSeqID` 映射为 FASTA 第一 token，且该值存在于 `.fai` 第一列；轨道中的该特征在目标区间出现。
- 注释属于其他 Assembly、特征属于其他 Annotation、索引已重建/过期：拒绝定位。
- 别名缺失或歧义、坐标为 0/负数/反向/超出 `.fai` 长度：拒绝定位。
- `reference_only` 样本 1248 和暂缓样本 1216：不出现可用的一键定位入口；原有浏览器状态提示保持正确。
- 无定位参数的原浏览器入口、4.3.0 选定定位 URL、iframe 与新窗口 URL、返回原注释页筛选和分页、站外 `return_to` 注入、旧状态请求覆盖新上下文：均通过回归。

生产发布前保留现有数据库/部署备份，先发布代码与试点映射，再逐批回填其余 `ready` 组装；记录每批成功、跳过、失败及原因。不得用本功能发布顺带修改 32 条暂缓组装的文件配对或强行构建索引。回滚优先关闭前端入口并回退代码/新映射引用，原始数据及已有 JBrowse 索引保持不动；如涉及数据库迁移，需另备可执行的迁移回退说明。

## 5. 完成定义与当前状态

“完成”指代码和自动化测试通过，映射方向及过期机制有测试，项目固定版 JBrowse 4.3.0 的 IR64/Assembly 93 试点通过，生产配置/状态/定位轨道/返回路径均有证据，扩展批次与例外数量可追溯。只看到页面跳到某个区间，**不等于**已验证正确 Annotation 轨道与目标特征。

截至 2026-10-14，阶段 A 已完成。阶段 B 已完成后端代码和开发环境验证，但尚差生产 Assembly 93/1400 的映射 `--apply` 与接口实测门禁。阶段 C 与阶段 D 已在开发环境完成。阶段 D 新增 `location_ready/location_status`，将 JBrowse 轨道就绪与一键定位就绪分开：refName 映射或注释特征索引缺失/过期时，轨道浏览能力不被错误降级，但行级定位入口保持禁用；同时增加查询→状态→定位→配置→受保护资产的集成用例。当前 Django 397 项测试通过（2 项跳过），Vue 173/173、lint、构建和 migration 检查通过。WSL2 恢复后，本地 Assembly 131 / Annotation 131 已完成真实映射回填；状态为 `ready`、`annotation_ready=true`、`location_ready=true`，四类资产 Range 请求均为 206。从注释表点击真实 `feature_id=1` 后，JBrowse 4.3.0 在 `Chr07:25730449-25731775` 显示 `IR64 annotation` 轨道和目标基因，返回时恢复原筛选 URL。生产环境未执行任何回填或联调，因此功能仍不能标记为生产可用。
