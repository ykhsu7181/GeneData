# GeneData 导航栏重构最终实施方案

## 1. 目标结构

```text
Home       → /dashboard
Accession  → /accession-card
Assembly   → /assembly
Data
├── Data Overview            → /data-overview
└── Research Group Raw Data  → /raw-data
More
├── Genome                   → /genome-card
├── Annotation               → /annotation
└── Transcriptome            → /transcriptome-overview
```

约束：

- Assembly 保留一级入口，当前仅提供独立占位页，不调用 API、不展示伪数据，也不加入首页搜索映射。
- Tools 仅从顶部导航隐藏，相关页面、路由、API、搜索映射和 i18n key 继续保留。
- `/raw-data` 只修改对外名称和说明，不修改路由、API 或业务字段。
- 首页搜索 Accession 继续使用 `/accession-card?accession=<value>`。

## 2. 第一阶段：路由与统一导航模型

- 新增 `AssemblyView.vue` 和受认证保护的 `/assembly` 路由。
- `topNavConfig.mjs` 成为唯一导航结构数据源。
- `TopNavBar.vue` 不再维护 `primaryNavItems`。
- Active Group：

```text
Home:      /dashboard
Accession: /accession-card, /accession-detail, /accession-map
Assembly:  /assembly
Data:      /data, /data-chart, /data-overview, /raw-data
More:      /genome-card, /annotation, /annotation-card,
           /transcriptome, /transcriptome-overview
```

Tools 和 `/placeholder` 不设置一级 active。

## 3. 第二阶段：导航交互与命名

- TopNavBar 根据 `children` 统一渲染普通入口或下拉菜单。
- Data 主按钮进入 `/data-overview`，独立箭头展开菜单。
- More 为纯菜单入口。
- Data、More 使用 click 触发，支持键盘和触屏，并提供 `aria-haspopup`、`aria-expanded` 与可见焦点。
- 中英文新增 `assembly`、`data`、`more`、`researchGroupRawData`。
- `/raw-data` 页面标题改为“课题组原始数据 Research Group Raw Data”，同步更新面包屑和副标题。

## 4. 第三阶段：测试与回归

- 测试五个一级入口、两个下拉菜单及顺序。
- 测试单一配置源和所有 Active Group。
- 测试隐藏 Tools 后相关路由仍存在。
- 测试 Assembly 路由受认证保护、页面无 API 和伪数据。
- 测试首页 Accession 搜索与顶部 Accession 入口职责不同。
- 测试 `/raw-data` 路由/API 不变，仅更新对外文案。
- 执行 `npm run build`、`npm test` 和变更范围 ESLint。

## 5. 验收标准

```text
✓ 一级导航为 Home / Accession / Assembly / Data / More
✓ 导航结构只有一个配置源
✓ Assembly 使用独立 /assembly 占位页且不请求 API
✓ Data / More 支持鼠标、键盘和触屏
✓ Active Group 覆盖所有约定路由
✓ Tools 隐藏但功能和路由保留
✓ /raw-data 显示 Research Group Raw Data，路由和 API 不变
✓ 首页 Accession 搜索继续直达详情
✓ 中英文文案完整
✓ 移动端无页面级横向溢出
✓ 构建与测试通过
```
