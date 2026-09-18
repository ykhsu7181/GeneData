# GeneData Accession 一级页面最终实施方案

## 1. 文档状态

本文档整合以下内容形成单一实施依据：

- 原 Accession 一级页面实施方案；
- 实施方案修订意见；
- 修订版方案评审反馈。

评审结论：

> 方案通过，可以进入开发。实施、测试与验收均以本文档为准。

本轮目标：

```text
Accession 一级页
= 搜索入口
+ 最近浏览
+ 收藏
+ 地理分布
```

页面结构：

```text
Accession
├── Search Accession
├── Recently Viewed
├── My Favorites
└── Geographic Distribution
```

Accession Detail 继续负责单个材料的完整数据展示，包括 Basic Information、Datasets、Samples、Assembly、Annotation 和 Related Files。

---

## 2. 实施边界

### 2.1 现有基础

当前开发分支：

```text
feat/homepage-portal-redesign
```

现有前端能力：

```text
/accession-card
/accession-card?accession=02428
/accession-map
AccessionDetailTableView
recent_accessions localStorage
ECharts
worldMapData.js
AccessionMapView
CompactAccessionMap
```

现有后端接口：

```text
/files/query/organisms/
/files/query/sub-populations/
/files/query/supplementary-data/
```

### 2.2 本轮不实施

```text
新的搜索结果一级路由
/accession/:id 强制迁移
format=summary
portal-summary API
服务端地图聚合
Favorite 数据库模型
Recent 数据库模型
新的地图框架
sqrt(count) 连续 bubble size
```

本轮不重构：

```text
Accession Detail tabs
Assembly Detail
Annotation
Data Overview
Raw Data
Transcriptome
```

---

## 3. 路由策略

保持现有 canonical URL：

```text
/accession-card
→ Accession Portal

/accession-card?accession=<ACCESSION>
→ Accession Detail
```

统一导航：

```js
router.push({
  name: 'accession-card',
  query: { accession }
})
```

本轮不新增 `/accession-search-result`，也不要求将详情地址迁移到 `/accession/:id`。

---

## 4. 页面结构与组件职责

桌面端布局：

```text
Home / Accession

Accession
Search and explore accessions, revisit recent records,
and browse collection geography.

┌────────────────────────────────────────────────────┐
│ Search Accession                                   │
│ Search accession / species / variety ...  Search  │
│ Examples: 02428 IR64 Oryza sativa japonica        │
└────────────────────────────────────────────────────┘

┌────────────────────────┐ ┌────────────────────────┐
│ Recently Viewed        │ │ My Favorites           │
│               View All│ │               View All│
└────────────────────────┘ └────────────────────────┘

┌────────────────────────────────────────────────────┐
│ Geographic Distribution            View Full Map → │
│                         MAP                        │
│ 1–10  11–50  51–100  >100       Mapped 520 of 633│
└────────────────────────────────────────────────────┘
```

推荐组件结构：

```text
vue_project/src/components/accession/
├── AccessionPortalHeader.vue
├── AccessionSearchPanel.vue
├── RecentAccessions.vue
├── FavoriteAccessions.vue
├── AccessionDistributionMap.vue
├── AccessionListDrawer.vue
├── AssemblyVersionTable.vue
├── AnnotationVersionTable.vue
└── CompactAccessionMap.vue

vue_project/src/services/
└── accessionPreferences.js
```

如果 `AccessionPortalHeader.vue` 最终只有少量静态结构且无复用价值，可以保留在 `AccessionCard.vue` 内；不得为了形式上的组件化增加无意义抽象。

`AccessionCard.vue` 负责：

```text
Portal / Detail route 状态判断
Portal 子组件组织
统一 openAccession()
Portal metadata 加载
区域状态协调
Drawer mode 切换
```

不再负责：

```text
搜索请求细节
localStorage 读写细节
地图绘制和聚合细节
```

建议模板：

```vue
<template>
  <div class="accession-portal">
    <template v-if="!routeAccession">
      <AccessionPortalHeader />

      <AccessionSearchPanel @select="openAccession" />

      <div class="shortcut-grid">
        <RecentAccessions
          :items="recentItems"
          @select="openAccession"
          @view-all="openRecentDrawer"
        />

        <FavoriteAccessions
          :items="favoriteItems"
          @select="openAccession"
          @view-all="openFavoriteDrawer"
        />
      </div>

      <AccessionDistributionMap
        :items="geoItems"
        @select="openAccession"
        @select-cluster="openClusterDrawer"
      />

      <AccessionListDrawer />
    </template>

    <AccessionDetailTableView v-else embedded />
  </div>
</template>
```

---

## 5. Search Accession

### 5.1 搜索范围

支持：

```text
Accession
Species code
Scientific name
Chinese name
Common name
Subpopulation
```

一级页移除旧的 Species、Subpopulation、Location 和 Refresh 控件，仅保留搜索输入、Search 按钮和 Examples。

### 5.2 接口契约

继续使用：

```text
GET /files/query/organisms/?search=<keyword>&limit=20
```

默认响应保持字符串数组：

```json
["02428", "IR64", "C7"]
```

兼容规则：

```text
有 search
→ 多字段搜索
→ limit 默认 20，最大 50

无 search
→ 暂时保持旧接口全量返回行为
→ 避免破坏 Home 或其他旧调用方
```

Portal 自身必须保证：

```text
输入为空 → 不发送请求
输入少于 2 个字符 → 不发送请求
```

### 5.3 参数校验

后端固定规则：

```text
search
→ trim 前后空白
→ 最大长度 100
→ 超过 100 返回 HTTP 400
→ error code: invalid_search

limit
→ 缺失时使用 20
→ 非整数或小于 1 返回 HTTP 400
→ 大于 50 时钳制为 50
```

建议错误结构：

```json
{
  "error": "search must not exceed 100 characters",
  "code": "invalid_search"
}
```

### 5.4 查询与排序

建议查询：

```python
queryset = (
    Accession.objects
    .select_related("species")
    .filter(
        Q(accession__icontains=search)
        | Q(species__species_code__icontains=search)
        | Q(species__scientific_name__icontains=search)
        | Q(species__chinese_name__icontains=search)
        | Q(species__common_name__icontains=search)
        | Q(sub_population__icontains=search)
    )
    .distinct()
)
```

使用 `Case/When` 计算 rank，并按以下优先级排序：

```text
1. accession 精确匹配
2. accession 前缀匹配
3. accession 包含匹配
4. species/subpopulation 匹配
5. accession 字典序
```

第一版候选项只展示 accession，不实现结构化 summary 响应。

### 5.5 前端请求控制

必须实现：

```text
250–300ms debounce
少于 2 个字符不请求
清空输入不请求
新请求发出后取消旧请求，或忽略旧响应
页面卸载时取消或忽略未完成请求
```

可使用 `AbortController` 或 request sequence id。搜索失败时保留 Examples 和已有选项，只显示轻量错误，不影响页面其他区域。

### 5.6 Examples 行为

Examples 必须配置类型，不能把 species 或 subpopulation 当成某个 accession 直接跳转：

```js
[
  { label: '02428', type: 'accession', value: '02428' },
  { label: 'IR64', type: 'accession', value: 'IR64' },
  { label: 'Oryza sativa', type: 'query', value: 'Oryza sativa' },
  { label: 'japonica', type: 'query', value: 'japonica' }
]
```

交互：

```text
type=accession
→ 直接进入对应 Accession Detail

type=query
→ 填入搜索框
→ 立即执行远程搜索
→ 用户从候选结果中选择 accession
```

---

## 6. Recently Viewed

### 6.1 存储与迁移

新 key：

```text
recent_accessions_v2
```

旧 key：

```text
recent_accessions
```

新结构：

```json
[
  {
    "accession": "02428",
    "viewed_at": "2026-09-17T03:30:00.000Z"
  }
]
```

迁移规则：

- 旧字符串转换为 `{ accession, viewed_at: null }`。
- 过滤空值、非法对象和非字符串 accession。
- 按 accession 去重并保留第一次出现的顺序。
- 成功规范化后写入 `recent_accessions_v2`，以后优先读取 v2。
- 旧记录没有时间时显示 `—`，不得显示为 Just now。
- 时间统一存储为 UTC ISO 8601，显示时使用浏览器本地时区。

### 6.2 记录时机

仅在 Accession 主详情或基本信息接口首次成功返回后记录：

```text
进入 route accession
→ 主详情请求成功
→ recordRecentAccession(accession)
```

不得在点击 Search、Example 或执行 `router.push()` 时提前记录。

同一个 route accession 生命周期只记录一次；route accession 改变后可以记录新 accession。Assembly、Annotation 等子请求成功不得重复触发记录。

### 6.3 展示规则

```text
最大保留 20 条
Portal 展示前 5 条
同一 accession 唯一
再次成功访问时更新时间并移动到首位
```

展示字段：

```text
Accession
Scientific name
Subpopulation
Viewed
```

---

## 7. My Favorites

第一版使用 localStorage：

```text
favorite_accessions_v1
```

结构：

```json
[
  {
    "accession": "02428",
    "created_at": "2026-09-17T02:00:00.000Z"
  }
]
```

规则：

```text
accession 唯一
created_at 使用 UTC ISO 8601
非法数据忽略
写入失败不阻断详情页
Portal/Detail 同一标签页即时同步
```

多标签页可通过 `storage` 事件同步，但不作为阻塞上线条件。

在 `AccessionDetailTableView.vue` 标题区增加：

```text
☆ Favorite
★ Favorited
```

按钮必须具备 `aria-label` 和 `aria-pressed`，且不能只依赖星标颜色表达状态。

Portal 中 Recent 和 Favorites 保持相同卡片高度；Recent 固定显示 5 条，Favorites 超出固定高度后纵向滚动。

---

## 8. Preferences Service

新增：

```text
vue_project/src/services/accessionPreferences.js
```

建议接口：

```js
getRecentAccessions()
recordRecentAccession(accession)
clearRecentAccessions()
removeRecentAccession(accession)

getFavoriteAccessions()
isFavoriteAccession(accession)
toggleFavoriteAccession(accession)
removeFavoriteAccession(accession)
```

统一处理：

```text
Migration
Validation
Dedupe
UTC timestamp
JSON parse error
非数组数据
Storage quota
SecurityError
```

读取失败返回安全默认值 `[]`；写入失败返回明确结果并显示轻量提示，不阻断导航或详情页。Vue 组件不得散落直接调用 `localStorage.getItem()` 和 `localStorage.setItem()`。

---

## 9. Portal Metadata 与后端性能

Recent、Favorites 和 Map 第一版统一加载：

```text
GET /files/query/supplementary-data/
```

不得为 5 条 Recent 发起 5 个 summary 请求。

接口增加：

```text
species_code
scientific_name
chinese_name
common_name
```

保留现有字段以兼容旧调用方：

```text
sub_population
seq_data
country
region
longitude
latitude
```

查询必须使用：

```python
Accession.objects.select_related("species").order_by("accession")
```

species 为空时，species metadata 返回 `null`，不得抛出异常。测试必须包含查询数量断言，防止 N+1。

当前数百条 accession 时允许一次返回全量 supplementary data。开发和测试环境应关注：

```text
记录数
响应体大小
接口耗时
```

当达到数千/上万条、响应达到明显 MB 级或延迟不可接受时，再拆分为服务端地图聚合、Recent/Favorites 批量 metadata 或 `portal-summary`、`fields/accessions` 参数。

---

## 10. Geographic Distribution

### 10.1 技术选型

新增：

```text
vue_project/src/components/accession/AccessionDistributionMap.vue
```

继续使用 ECharts 和 `worldMapData.js`，不引入 Leaflet、Mapbox 或 Google Maps。

### 10.2 坐标校验

参与地图的数据必须满足：

```text
longitude != null
latitude != null
Number.isFinite(longitude)
Number.isFinite(latitude)
-180 <= longitude <= 180
-90 <= latitude <= 90
```

`0` 是合法经纬度，不得使用 `if (longitude && latitude)` 判断。

### 10.3 网格聚合

第一版使用 `2° × 2°` 网格：

```js
const GRID_SIZE = 2
const maxGridX = Math.ceil(360 / GRID_SIZE) - 1
const maxGridY = Math.ceil(180 / GRID_SIZE) - 1

const gridX = Math.min(
  maxGridX,
  Math.floor((longitude + 180) / GRID_SIZE)
)

const gridY = Math.min(
  maxGridY,
  Math.floor((latitude + 90) / GRID_SIZE)
)
```

这样 `longitude === 180` 和 `latitude === 90` 会归入最后一个合法网格。聚合点坐标使用成员真实坐标平均值，不修改数据库原始坐标。

### 10.4 Bubble 大小

第一版保持四档：

```js
if (count <= 10) return 8
if (count <= 50) return 13
if (count <= 100) return 18
return 24
```

连续 `sqrt(count)` 缩放不纳入本轮。

### 10.5 点击与 Tooltip

点击规则：

```text
count === 1
→ 直接进入 Accession Detail

count > 1
→ 打开 cluster Drawer
→ 展示该 cluster 的 accession 列表
→ 用户选择具体 accession 后进入详情
```

禁止聚合点自动打开第一条 accession。

单点 Tooltip：

```text
02428
Oryza sativa
GJ
China
32.06, 118.76
```

聚合 Tooltip 最多显示前 5 条，并显示 `+N more`。

### 10.6 地图统计口径

定义：

```text
totalAccessions
→ supplementary-data 中去重后的全部 accession 数

mappedAccessions
→ 通过有效性校验并参与地图聚合的 accession 数
```

地图底部显示：

```text
Mapped {mappedAccessions} of {totalAccessions} accessions
```

要求：

```text
每个 accession 最多计数一次
所有 cluster count 之和等于 mappedAccessions
非法坐标不计入 mappedAccessions
```

### 10.7 完整地图与生命周期

标题右侧增加 `View Full Map →`，跳转 `/accession-map`。

组件卸载时必须：

```text
dispose ECharts
remove resize listener
cleanup ECharts event handlers
取消或忽略未完成请求
```

---

## 11. 统一 Drawer

新增 `AccessionListDrawer.vue`，通过 mode 复用：

```text
recent
favorites
cluster
```

规格：

```text
桌面宽度约 520px
移动端宽度 100%
支持 Esc 关闭
关闭后焦点返回触发按钮
完整键盘操作
```

Recent Drawer 支持删除单条和清空全部；Favorites Drawer 支持取消收藏；Cluster Drawer 支持选择 accession 进入详情。

---

## 12. Loading、Empty 与 Error

Search、Recent、Favorites 和 Map 分别管理状态。

```text
Search error
→ 保留 Examples 和已有选项

Recent/Favorites metadata error
→ 仍显示 accession
→ 其他字段显示 —

Map loading
→ 固定高度 skeleton/loading

Map empty
→ 暂无可展示的地理数据

Map error
→ 地图数据加载失败 + Retry
```

Map 错误不得阻断 Search。共享 metadata 请求失败时，Recent/Favorites 必须退化为仅显示本地保存的 accession，而不是整块失败；Retry 只重试 metadata/map 区域。

---

## 13. 视觉、响应式与可访问性

附件 HTML/CSS 只作为布局、颜色、间距、宽度、视觉层级和响应式参考，不得原样嵌入 Vue。

实施要求：

- TopNav 使用现有公共组件。
- 地图使用真实 ECharts，不使用参考 HTML 中的静态 SVG。
- 只有确实实现地图缩放时才展示 `+/-` 控件。
- 长 accession、scientific name 和 subpopulation 使用 ellipsis，并提供 `title` 或 tooltip。
- Accession 列在所有断点始终可见。
- 小屏幕下 Recent/Favorites 上下排列。
- 极小屏幕可隐藏 Species、Subpopulation、Viewed 等次要列。
- 地图使用固定或最小高度，避免加载时布局抖动。
- DNA/chromosome 装饰设置 `aria-hidden="true"` 和 `pointer-events: none`，不进入焦点序列。
- 后续可抽取 `PortalBackgroundDecor.vue` 供 Home、Accession 和 Assembly 复用。

---

## 14. i18n

修改：

```text
vue_project/src/i18n/locales/zh-CN.js
vue_project/src/i18n/locales/en-US.js
```

至少增加：

```text
page.accessionPortal.title
page.accessionPortal.subtitle
page.accessionPortal.searchTitle
page.accessionPortal.searchPlaceholder
page.accessionPortal.examples
page.accessionPortal.searchError
page.accessionPortal.recent
page.accessionPortal.favorites
page.accessionPortal.geographicDistribution
page.accessionPortal.viewAll
page.accessionPortal.viewFullMap
page.accessionPortal.noRecent
page.accessionPortal.noFavorites
page.accessionPortal.mapEmpty
page.accessionPortal.mapError
page.accessionPortal.favorite
page.accessionPortal.favorited
page.accessionPortal.unfavorite
page.accessionPortal.totalAccessions
page.accessionPortal.mappedAccessions
page.accessionPortal.moreItems
page.accessionPortal.clearAll
page.accessionPortal.remove
page.accessionPortal.retry
```

相对时间应使用现有 i18n 体系或 `Intl.RelativeTimeFormat`，旧数据的 `viewed_at: null` 始终显示 `—`。

---

## 15. 修改范围

后端主要修改：

```text
django2/files/query_views.py
django2/files/tests/api/
```

前端修改：

```text
vue_project/src/views/AccessionCard.vue
vue_project/src/views/AccessionDetailTableView.vue
vue_project/src/i18n/locales/zh-CN.js
vue_project/src/i18n/locales/en-US.js
vue_project/tests/
```

前端新增：

```text
vue_project/src/components/accession/AccessionPortalHeader.vue（按实际复用价值决定）
vue_project/src/components/accession/AccessionSearchPanel.vue
vue_project/src/components/accession/RecentAccessions.vue
vue_project/src/components/accession/FavoriteAccessions.vue
vue_project/src/components/accession/AccessionDistributionMap.vue
vue_project/src/components/accession/AccessionListDrawer.vue
vue_project/src/services/accessionPreferences.js
```

---

## 16. 实施阶段

### Phase 0 — 契约确认

编码前固定：

```text
有 search：limit 默认 20、最大 50
无 search：保持旧接口行为
search/limit 非法参数处理
Examples 的 accession/query 两种行为
Recent 由主详情首次成功触发
Map count=1 进入详情，count>1 打开 Drawer
地图显示 Mapped X of Y
```

### Phase 1 — Preferences

实现 `accessionPreferences.js`、Recent v2 迁移、Favorites、校验、去重、UTC 时间和 storage error 处理，并先完成单元测试。

随后在 Detail 增加 Favorite/Favorited，并在主详情首次成功后记录 Recent。

### Phase 2 — Backend Search and Metadata

实现多字段搜索、limit、rank、参数校验、species metadata、`select_related` 及后端测试。

### Phase 3 — Portal Core and Search

实现 Portal 布局、SearchPanel、Examples 分类行为、debounce、stale request protection 及搜索状态。

### Phase 4 — Recent, Favorites and Drawer

实现两个快捷卡片、统一 Drawer、删除/清空/取消收藏及 Portal/Detail 同步。

### Phase 5 — Geographic Distribution

实现坐标校验、2° 聚合、bubble、tooltip、统计口径、单点导航、cluster Drawer、Full Map 和独立状态。

### Phase 6 — UI, i18n, Accessibility and Regression

完成中英文、响应式、文本溢出、ARIA、键盘、焦点恢复、资源清理和全流程回归。

---

## 17. 测试要求

### 17.1 Backend

```text
✓ 有 search 时默认 limit=20
✓ limit>50 时按 50 执行
✓ limit 非整数或小于 1 返回 400
✓ search trim 正常
✓ search 超过 100 字符返回 400 + invalid_search
✓ 无 search 保持旧兼容行为
✓ accession 精确匹配排第一
✓ accession 前缀优先于 accession 包含
✓ accession 匹配优先于 species/subpopulation
✓ species code/scientific/chinese/common name 搜索正确
✓ subpopulation 搜索正确
✓ 搜索结果去重
✓ supplementary-data 返回 species metadata
✓ species 为 null 时字段返回 null
✓ supplementary-data 使用 select_related
✓ supplementary-data 无 N+1
```

### 17.2 Search

```text
✓ 少于 2 个字符不请求
✓ debounce 生效
✓ 新请求不会被旧响应覆盖
✓ 清空输入不请求全量
✓ 请求错误不影响 Examples
✓ accession Example 直接进入详情
✓ query Example 填充并执行搜索，不直接导航
✓ 页面卸载后未完成请求被取消或忽略
```

### 17.3 Preferences and Detail

```text
✓ 损坏 JSON 和非数组数据安全降级
✓ recent_accessions 正确迁移到 v2
✓ Recent 过滤非法项并去重
✓ 再次访问置顶并更新时间
✓ 旧 Recent 时间显示 —
✓ 最大保留 20 条
✓ 主详情成功只记录一次
✓ 详情失败不写 Recent
✓ 子模块成功不重复写 Recent
✓ route accession 改变后记录新 accession
✓ Favorite 不重复、可取消、刷新后保留
✓ storage 写入失败不阻断主流程
```

### 17.4 Map

```text
✓ longitude/latitude 为 0 时有效
✓ 非有限值和越界坐标被过滤
✓ 180/90 进入最后合法网格
✓ count=1 直接导航
✓ count>1 打开 cluster Drawer
✓ cluster 不自动进入第一条
✓ tooltip 显示前 5 条和 +N more
✓ mappedAccessions 不包含非法坐标
✓ 同一 accession 只计数一次
✓ cluster count 之和等于 mappedAccessions
✓ View Full Map 跳转 /accession-map
✓ Map 失败不影响其他区域
✓ 卸载时 ECharts、listener 和 handler 被清理
```

### 17.5 Drawer and Accessibility

```text
✓ 三种 mode 正确展示
✓ Esc 关闭
✓ 关闭后焦点返回触发按钮
✓ Favorite button 有 aria-label 和 aria-pressed
✓ 装饰元素 aria-hidden 且不进入焦点序列
✓ 键盘可完成选择、收藏、取消和关闭操作
```

---

## 18. 最终验收标准

```text
✓ /accession-card 显示正式 Portal
✓ /accession-card?accession=02428 继续显示现有详情
✓ 不新增搜索结果一级路由

✓ Portal 包含 Search、Recent、Favorites、Map
✓ 旧筛选控件从一级页移除
✓ Search 支持 accession/species/subpopulation
✓ Search 具备 limit、排序、debounce 和 stale request 保护
✓ Portal 空输入不请求全量数据
✓ 无 search 的共享接口旧行为保持兼容
✓ Examples 两种行为无歧义

✓ Recent 使用 v2 key 并兼容迁移
✓ Recent 仅在主详情首次成功后记录
✓ Favorites 可在 Detail 添加和取消
✓ Preferences 错误不影响主流程

✓ Recent/Favorites metadata 无逐条 HTTP 请求
✓ supplementary-data 无 ORM N+1
✓ View All 使用统一 Drawer

✓ 地图复用 ECharts/worldMapData
✓ 零坐标合法，非法坐标被过滤
✓ 多记录 cluster 不随机跳转
✓ 地图正确显示 Mapped X of Y
✓ cluster count 合计与 mappedAccessions 一致
✓ View Full Map 跳转 /accession-map
✓ Map 失败不影响 Search/Recent/Favorites 基本可用性

✓ 中英文、响应式、键盘、焦点和 ARIA 正常
✓ 页面卸载后无残留地图实例、事件监听或过期请求
✓ Accession Detail、Assembly、Annotation 等现有链路不受影响
```

---

## 19. Commit 建议

```text
1. feat(accession): add portal preferences service
2. feat(accession): enhance accession search metadata
3. feat(accession): add accession portal search shell
4. feat(accession): add recent favorites and drawer
5. feat(accession): add geographic distribution overview
6. test(accession): harden portal interactions
```

每个提交均应包含对应测试，避免把全部测试集中到最后才补充。

---

## 20. 最终用户路径

```text
Top Nav
↓
Accession Portal
↓
Search / Recent / Favorites / Map
↓
选择具体 accession
↓
Accession Detail
↓
Assembly / Annotation / Related Data
```

完成后，Accession 一级页面从“搜索加空状态”升级为“搜索入口、个人快捷访问和地理发现入口”，同时保持现有详情与下游资源链路兼容。
