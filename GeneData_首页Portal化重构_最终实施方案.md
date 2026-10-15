# GeneData 首页 Portal 化重构最终实施方案

## 1. 目标

将首页从重型 Dashboard 改造为轻量数据仓库 Portal，保留：

- 全局顶部导航
- GeneData 主视觉与统一搜索
- Featured Accessions
- 核心统计栏

首页彻底移除：

- 物种卡片、资源概览、亚群分布、地理地图、最近更新
- 首页 ECharts、GeoJSON 和 IntersectionObserver 懒加载逻辑
- 对应的无用 Dashboard 聚合查询

本次不调整认证策略，`/dashboard` 继续要求登录；不新建 Statistics、Help、About 空壳页面。

---

## 2. 最终结构

```text
App.vue
├── TopNavBar.vue                 # 全局导航，调整为 Portal 风格
├── DashboardHomeView.vue
│   ├── HomeHero.vue             # 标题、搜索、Examples、装饰 SVG
│   ├── FeaturedAccessions.vue   # 推荐 Accession
│   └── HomeStatsBar.vue         # 核心统计
└── Footer
```

参考模板 `index.html` 和 `styles.css` 仅用于移植结构、样式参数和 SVG，不直接嵌入 Vue，也不复制 `body`、`table`、`button` 等全局样式。

---

## 3. 前端实施

### 3.1 全局导航

继续使用 `App.vue` 中的 `TopNavBar.vue`，不在首页重复创建导航栏。

导航映射：

```text
Home       → /dashboard
Search     → /accession-card
Downloads  → /raw-data
```

保留语言切换、当前用户和退出登录功能，并将视觉调整为参考图的白色 Portal 风格。

### 3.2 HomeHero.vue

包含：

```text
GeneData
Genomic Data Warehouse
Explore · Discover · Utilize Genomic Resources
统一搜索框
Examples
DNA、植物、染色体、数据网络等装饰 SVG
```

搜索要求：

- 继续复用 `resolveDashboardSearch()`，但先审计其对 `hot_keywords`、`species_cards` 的依赖。
- 点击按钮和 Enter 共用一个 `handleSearch()`。
- 输入先执行 `trim()`，空值不跳转。
- Examples 也调用同一个搜索方法。
- Dashboard API 失败时，搜索仍可使用。

若当前系统无法真正支持 gene/species/keyword 跨模块检索，应调整 placeholder；后续再单独建设统一搜索 API。

### 3.3 FeaturedAccessions.vue

第一阶段使用 `Featured Accessions`，避免把配置名单描述为真实热门排名。

展示字段：

```text
Accession | Species | Common Name | Assembly | Annotation
```

点击 Accession：

```js
router.push({
  name: 'accession-card',
  query: { accession: item.accession }
})
```

`View All` 跳转 `/accession-card`。

### 3.4 HomeStatsBar.vue

首页直接显示以下四项，不使用 `Genomes` 标签：

```text
Assemblies
Species
Annotations
Accessions
```

对应统计口径：

```python
assembly_count = Assembly.objects.count()
species_count = Species.objects.count()
annotation_count = Annotation.objects.count()
accession_count = Accession.objects.count()
```

加载阶段显示 `—`，不要用 `0` 冒充已加载结果；真实值为零时正常显示 `0`。

### 3.5 DashboardHomeView.vue

重写后只保留：

```text
loadDashboard()
handleSearch()
handleAccessionSelect()
handleViewAllAccessions()
```

删除旧组件 import、异步图表组件、懒加载 ref、observer 和相关方法。

Hero 与搜索立即显示；推荐列表和统计栏分别处理 loading、empty、error 状态。API 失败不应替换整个首页。

### 3.6 响应式与可访问性

- ≥ 1400px：显示完整装饰。
- 900–1399px：装饰外移并降低透明度。
- < 900px：隐藏复杂装饰。
- 移动端推荐表格改为卡片或精简列，避免仅依赖横向滚动。
- 控件最小点击高度 44px。
- 装饰 SVG 设置 `aria-hidden="true"`、`pointer-events: none`。
- SVG gradient/mask ID 使用组件前缀。
- 保留键盘焦点，并支持 `prefers-reduced-motion`。

---

## 4. Dashboard API

### 4.1 最终响应

```json
{
  "summary": {
    "assembly_count": 100,
    "species_count": 50,
    "annotation_count": 1000000,
    "accession_count": 500
  },
  "featured_accessions": [
    {
      "accession": "IR64",
      "species_scientific_name": "Oryza sativa",
      "species_common_name": "Rice",
      "assembly": "IRGSP-1.0",
      "annotation": "v1.0"
    }
  ]
}
```

首页显示名称固定为 `Assemblies`，对应 `assembly_count = Assembly.objects.count()`，不再使用 `Genomes` 表述。

### 4.2 Featured 数据来源

第一阶段在 Django settings 中维护推荐 Accession 顺序，后端只返回数据库中真实存在的记录。后续可增加 `is_featured`、`featured_order`，有真实访问统计后再升级为 Popular Accessions。

Assembly 和 Annotation 优先取 `is_default=True`；无默认记录时按模型排序取第一条。

显示值回退规则：

```text
Assembly:
display_name → assembly_name → assembly_code → name → "-"

Annotation:
annotation_version → release_version → annotation_name
→ annotation_code → name → "-"
```

查询使用 `select_related`/`Prefetch`，避免 N+1。

### 4.3 Service 与缓存

`dashboard_views.py` 继续只负责 HTTP、缓存和 Response；查询逻辑保留在 `dashboard_service.py`。

最终：

```python
def build_dashboard_payload():
    return {
        "summary": _build_summary(),
        "featured_accessions": _build_featured_accessions(),
    }
```

缓存键由：

```python
warehouse_dashboard_payload_v1
```

升级为：

```python
warehouse_dashboard_payload_v2
```

推荐配置发生变化时应主动清除缓存。

### 4.4 兼容迁移

先新增新字段并暂时保留旧字段；新首页和测试稳定后，再删除旧 API 字段及以下聚合逻辑：

```text
species_cards
sub_population_distribution
xi_distribution
dataset_type_summary
file_role_summary
resource_summary
recent_updates
geo_distribution
hot_keywords
```

---

## 5. 文件变更

| 文件 | 操作 |
|---|---|
| `vue_project/src/views/DashboardHomeView.vue` | 重写 |
| `vue_project/src/components/TopNavBar.vue` | 调整 Portal 视觉 |
| `vue_project/src/components/HomeHero.vue` | 新增 |
| `vue_project/src/components/FeaturedAccessions.vue` | 新增 |
| `vue_project/src/components/HomeStatsBar.vue` | 新增 |
| `vue_project/src/services/dashboard.js` | 精简数据结构 |
| `django2/files/services/dashboard_service.py` | 新增新字段后分阶段精简 |
| `django2/files/dashboard_views.py` | 保持薄层，升级缓存键 |
| 首页前后端测试 | 重写或补充 |
| API 文档 | 更新 |

旧组件在确认无运行时引用后删除：

```text
DashboardHero.vue
SpeciesCardGrid.vue
DistributionPanel.vue
GeoMapPanel.vue
DataResourceSummary.vue
RecentUpdatesBar.vue
```

删除前必须使用 `rg` 审计 `src` 和 `tests`。不因首页重构直接删除全项目仍使用的 ECharts 依赖。

---

## 6. 实施顺序

1. 建立分支，运行前端 build/test/lint 和 Django check/test，记录基线。
2. 后端新增 `summary` 新字段和 `featured_accessions`，升级缓存键，暂时保留旧字段。
3. 新增 `HomeHero`、`FeaturedAccessions`、`HomeStatsBar`。
4. 重写 `DashboardHomeView.vue`，移除旧首页运行链路。
5. 调整全局 `TopNavBar.vue` 视觉。
6. 更新搜索、路由、加载状态和响应式行为测试。
7. 完成引用审计后，删除旧组件、旧字段和旧聚合函数。
8. 执行完整前后端回归并更新 API 文档。

建议按以上步骤拆分提交，避免把视觉替换、API 破坏性变更和旧代码删除放在同一个提交中。

---

## 7. 测试重点

前端：

- 首页存在三个新组件，不再引用旧 Dashboard 组件和 IntersectionObserver。
- Search、Enter、Examples 均使用统一搜索逻辑。
- 空输入不跳转；Accession 使用 `query.accession`。
- API 失败时搜索仍可用。
- `null` 显示 `—`，真实 `0` 显示 `0`。
- 375px、768px、1440px 下无明显溢出或遮挡。

后端：

- summary 统计正确。
- 配置中不存在的 Accession 自动忽略。
- 推荐顺序稳定。
- 默认 Assembly/Annotation 及回退逻辑正确。
- 空数据库和缺失关联数据不报错。
- 查询数量稳定，无 N+1。
- 缓存使用新版本键。

旧测试中直接读取旧组件的断言应同步迁移，尤其是 `raw-data-page.test.mjs` 对 `DataResourceSummary.vue` 的依赖。

---

## 8. 验收标准

```text
✓ 首页视觉与参考图整体一致
✓ 全局导航无重复，并保留现有用户功能
✓ 搜索、Examples、Accession 和 View All 跳转正确
✓ 统计和 Featured Accessions 来自真实数据库
✓ 首页不加载 ECharts、GeoJSON 或旧懒加载逻辑
✓ Dashboard API 最终仅返回首页所需数据
✓ 移动端无明显溢出，键盘操作可用
✓ npm run build / test / lint 通过
✓ python manage.py check 和相关 Django 测试通过
✓ Accession、Raw Data、Genome、Annotation 页面回归正常
```

本次重构的核心原则是：首页只承担数据仓库入口职责，在不改变认证和既有业务页面的前提下，降低首屏负担和维护复杂度。
