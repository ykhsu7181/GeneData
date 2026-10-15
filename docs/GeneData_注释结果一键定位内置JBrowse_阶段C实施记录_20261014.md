# GeneData：从注释结果一键定位内置 JBrowse 阶段 C 实施记录

> 实施日期：2026-10-14
> 结论：**阶段 C 的前端代码与开发环境自动化验证已经完成；生产试点浏览器联调尚未完成。** 生产 Assembly 93/1400 的 refName 映射回填仍是前置门禁，因此当前实现保持失败关闭，不能标记为生产可用。

## 1. 已实现内容

### 1.1 注释表行级入口

- `AnnotationView.vue` 增加固定在表格右侧的“在基因组浏览器中查看”操作列。
- 入口只在当前 Assembly/Annotation 的 JBrowse 状态为 `ready`、`annotation_ready=true`、`location_ready=true` 且该行有合法 `feature_id` 时启用。`location_ready` 由阶段 D 增补，用于区分“轨道可浏览”和“特征可定位”。
- 状态按 `Assembly ID:Annotation ID` 缓存；普通筛选、分页和路由恢复复用缓存，用户主动刷新时才强制重查。
- 上下文切换及组件卸载会取消状态请求和定位请求；请求令牌与上下文键共同阻止旧响应污染新上下文。

### 1.2 可信定位和失败关闭

点击入口后调用：

```text
GET /gd/api/files/assemblies/<assembly_id>/annotations/<annotation_id>/features/<feature_id>/jbrowse-location/
```

前端不使用表格中的 `seqid/start/end` 自行拼接坐标，而是校验响应中的 Assembly、Annotation、Feature 归属及规范 `loc`。后端返回 404、409、422、503 或无效响应时留在原页，并按稳定错误码显示本地化提示。

### 1.3 路由和固定版 JBrowse URL

成功定位后进入：

```text
/assembly/<assembly_id>/browser
  ?annotation_id=<annotation_id>
  &loc=<refName:start-end>
  &return_to=<原注释页内部路径>
```

有合法 `loc` 时，JBrowse 4.3.0 使用阶段 A 选定的 selected-mode 参数：

```text
/jbrowse2/?config=<config URL>&assembly=<assembly name>&loc=<location>&tracks=<track ids>
```

iframe 的 `src` 与“在新窗口打开”的 `href` 直接共用同一个计算结果。没有 `loc` 的既有浏览器入口仍只传 `config`，保持原行为。

### 1.4 返回路径安全

新增共享工具 `src/utils/internalNavigation.js`，由注释页和浏览器页共同使用。允许的返回目标仅包括：

- `/annotation`、`/annotation-card`；
- `/assembly/<正整数 ID>`；
- 上述路径自身的查询参数。

外部 URL、协议相对 URL、反斜杠、控制字符、片段、非白名单路径以及一次或多次编码后变成危险形式的值均被拒绝。拒绝后浏览器页回退到当前 Assembly 详情页。

## 2. 代码范围

- `vue_project/src/views/AnnotationView.vue`
- `vue_project/src/views/GenomeBrowserView.vue`
- `vue_project/src/utils/internalNavigation.js`
- `vue_project/src/utils/jbrowseNavigation.js`
- `vue_project/src/i18n/locales/zh-CN.js`
- `vue_project/src/i18n/locales/en-US.js`
- `vue_project/tests/jbrowse-one-click-stage-c.test.mjs`
- `vue_project/tests/genome-browser-stage5.test.mjs`
- `vue_project/tests/annotation-accession-sync.test.mjs`

## 3. 自动化验证结果

```text
npm test
173 tests passed, 0 failed

npm run lint
通过，无 ESLint 错误

npm run build
退出码 0，生产构建完成
```

构建仍报告项目既有的 bundle/entrypoint 体积警告；本轮没有把性能拆包扩展到阶段 C 范围之外。

新增回归覆盖：

- 行级入口、`feature_id` 和可信定位接口；
- Assembly/Annotation 组合缓存、请求取消及旧响应隔离；
- `config + assembly + loc + tracks` 的精确生成；
- iframe 与新窗口共用 URL，无定位参数时保持 config-only；
- 坐标、正整数 ID、track/assembly 标识校验；
- 内部返回路径白名单及多次编码攻击样例；
- 阶段 C 中英文文案一致性。

## 4. 开发环境联调结论与生产门禁

阶段 D 已在本地开发数据 Assembly 131 / Annotation 131 上完成真实页面联调：从注释表首行点击后定位到 `Chr07:25730449-25731775`，JBrowse 4.3.0 同时显示 `IR64 annotation` 轨道与目标基因；新窗口入口使用与 iframe 相同的初始 URL，返回后原 `accession/assembly/annotation/chromosome` 查询上下文完整恢复。四类受保护资产的真实 Range 请求也均返回 206。具体证据见 [阶段 D 实施记录](GeneData_注释结果一键定位内置JBrowse_阶段D实施记录_20261014.md)。

本地 Assembly ID 和物理文件关系不能代表生产，因此以下生产门禁仍未完成：

1. 生产 Assembly 1400 和 93 的 refName 映射 dry-run、apply 与指纹核对；
2. 两个生产试点各取真实 `feature_id` 调用定位 API；
3. IR64 定位到阶段 A 固定的 `Chr01` 特征、W2275 定位到 `GWHESLA00000001`；
4. 两个生产试点的目标区间、正确 Annotation 轨道、四类 206 Range 请求和返回上下文均通过。

未就绪组合的按钮保持禁用是预期行为；开发环境通过不能替代上述生产证据。
