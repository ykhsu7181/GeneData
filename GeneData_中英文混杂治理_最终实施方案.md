# GeneData 中英文混杂治理最终实施方案

## 1. 改造目标

在不修改后端 API、数据库字段、枚举值和路由的前提下，实现门户及业务页面的完整中英文切换，消除无意义的双语并排和硬编码 UI 文案。

## 2. 语言与术语规则

### 2.1 必须随语言切换

页面标题、按钮、提示、状态、空状态、Toast、面包屑、筛选项、表头和分页文案统一通过 `vue-i18n` 输出。

### 2.2 保留英文或原值

- 品牌：`GeneData`。
- 科研标识及缩写：`Accession`、`BioProject`、`BioSample`、`Experiment`、`Run`、`MD5`、`FASTA`、`GFF/GFF3`、`CDS`、`RNA-seq`。
- 物种学名、数据库版本、样本编号和接口返回的真实数据值。
- 首页四项统计名称固定为：`Assemblies / Species / Annotations / Accessions`。
- 沿用已确认的一级导航：中文模式仍显示 `首页 / Accession / Assembly / Data / More`；下拉项及说明文案正常本地化。

### 2.3 禁止形式

- 不再显示“课题组原始数据 Research Group Raw Data”等同义双语标题。
- 同一字段不得混用“品种 / 材料 / 生物体”；搜索及数据标识统一使用 `Accession`，普通分类名称使用“物种 / Species”。
- 数据库原始枚举只做显示映射，不修改传输值。

## 3. i18n 架构

将现有单文件语言包拆分为：

```text
vue_project/src/i18n/
├── index.js
└── locales/
    ├── zh-CN.js
    └── en-US.js
```

- `index.js` 只负责初始化，继续使用现有 locale ID：`zh`、`en`，避免影响 `App.vue` 的切换与持久化逻辑。
- 语言包按 `common / messages / nav / page / footer / status` 分组。
- JS 中的 tabs、统计卡片和状态列表使用 `labelKey`，或在 `computed()` 中调用 `t()`，保证切换语言后立即更新。
- 根组件通过 `el-config-provider` 同步切换 Element Plus 的中英文 locale。
- 迁移期间暂保留 `fallbackLocale: 'zh'`；中英文 key 完全对齐后关闭跨语言回退，防止英文页面静默显示中文。
- 后端错误原文只用于日志；界面显示本地化通用错误或基于稳定错误码的映射。

## 4. 三阶段实施

### 阶段一：基础设施、导航与首页

- 拆分语言包，建立术语表及中英文 key 完整性测试。
- 接入 Element Plus 动态 locale。
- 改造 `TopNavBar.vue`、`HomeHero.vue`、`FeaturedAccessions.vue`、`HomeStatsBar.vue`、`AssemblyView.vue`。
- 保持 `GeneData`、一级导航英文术语及首页四项统计名称不变。

### 阶段二：核心数据流程

- 改造 `AccessionCard.vue`、`AccessionDetailTableView.vue`、`DataOverviewView.vue`、`RawDataView.vue`。
- tabs、summaryCards、筛选项、表头、状态、空状态和 Toast 全部响应语言切换。
- 删除 Data Overview 与 Raw Data 页面中的双语并排文案。
- 保留现有请求参数、API 地址、下载地址及状态原值。

### 阶段三：全站收尾

- 改造 `GenomeCard.vue`、`AnnotationView.vue`、`TranscriptomeOverviewView.vue`。
- 补齐 Login、Admin 及隐藏 Tools 页面，达到全站验收标准。
- 清理未使用 key，执行硬编码检查、自动测试、构建和人工双向切换验收。

每个阶段独立提交；阶段二完成后可先验收公开主流程，阶段三完成后再宣告全站治理完成。

## 5. 测试方案

新增：

```text
vue_project/tests/i18n-locale-parity.test.mjs
vue_project/tests/i18n-key-reference.test.mjs
vue_project/tests/i18n-hardcoded-ui.test.mjs
```

- `locale-parity`：递归验证中文和英文 key 完全一致。
- `key-reference`：检查代码引用的静态 `$t()` / `t()` key 均存在。
- `hardcoded-ui`：只扫描 Vue 模板文本、placeholder、title、label、Toast 和确认框；允许品牌、科研缩写、CSS、SVG、注释、测试数据及 API 路径。
- 更新现有源码测试，避免其继续断言旧硬编码文案。
- 当前项目没有 Vue Test Utils，运行时切换先采用人工验收；如后续引入组件测试依赖，再补充自动交互测试。

执行：

```text
npm test
npm run build
变更范围 ESLint
```

项目原有 `npm run lint` 测试目录配置问题不纳入本次业务改造，单独修复后再恢复全量 lint 门禁。

## 6. 验收标准

- 中文与英文语言包 key 完全一致，引用 key 均存在。
- 切换语言无需刷新；标题、按钮、tabs、统计卡片、表头、状态、空状态和 Toast 立即更新。
- Element Plus 内置组件语言与当前界面一致。
- 中文模式无无意义的英文操作文案，英文模式无中文 UI 文案。
- 固定品牌、科研术语、首页统计名称和真实数据值保持原样。
- 页面不再并排显示同义中英文标题或表头。
- API、路由、请求字段、下载行为和数据库枚举不变。
- `npm test`、`npm run build` 和变更范围 ESLint 通过。
- 桌面端与移动端主要流程人工验收通过。

## 7. 明确不做

- 不翻译后端存储的数据内容和物种学名。
- 不修改 API 契约、数据库结构或枚举值。
- 不借本次改造调整导航结构、业务流程或页面视觉布局。
- 不在同一提交中同时进行无关功能重构。
