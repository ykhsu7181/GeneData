# GeneData Accession 一级页面实施方案修订意见

## 1. 评审结论

原实施方案整体方向合理，产品定位、页面信息架构、路由复用、组件拆分及技术选型与当前项目基本匹配，建议结论为：

> 修改后实施。

以下内容可按原方案保留：

- `/accession-card` 同时承担 Accession 一级入口页和 Accession 详情页，不新增搜索结果一级路由。
- 一级页面包含 Search Accession、Recently Viewed、My Favorites、Geographic Distribution。
- 移除当前未真正参与后端查询的 Species、Subpopulation、Location 筛选项。
- Recent 和 Favorites 统一通过独立 service 管理，不在多个 Vue 组件内直接操作 `localStorage`。
- 地图继续复用 ECharts、`worldMapData` 和现有地图组件能力，不引入 Mapbox 或 Leaflet。
- 本轮不重构 Accession Detail、Assembly、Annotation、Data Overview、Raw Data、Transcriptome。

实施前应补充搜索接口约束、地图聚合交互、批量数据性能边界和本地数据迁移规则。

---

## 2. 必须修订项

### 2.1 搜索接口增加结果上限、排序和请求控制

当前 `GET /files/query/organisms/?search=` 返回字符串数组。扩展为 species、scientific name、common name、Chinese name 和 subpopulation 搜索后，一个关键词可能命中大量 accession。

后端要求：

```text
GET /files/query/organisms/?search=<keyword>&limit=20
```

- `limit` 默认 20，最大 50。
- 空关键词不返回全库；返回空数组，或仅返回有限的推荐项。
- 搜索结果去重。
- 排序优先级为：

```text
accession 精确匹配
→ accession 前缀匹配
→ accession 包含匹配
→ species/subpopulation 匹配
→ accession 字典序
```

- 对 `search` 做长度限制，例如最大 100 个字符。
- 保持默认响应结构为字符串数组，避免影响现有调用方。

建议查询逻辑：

```python
queryset = (
    Accession.objects
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

前端要求：

- 用户输入至少 2 个字符后再发起远程搜索。
- 增加 250–300ms debounce。
- 新请求发出时取消旧请求，或通过请求序号丢弃过期响应。
- 清空输入后不自动请求全部 accession。
- 请求失败时保留 Examples 和已有选项，不影响用户继续操作。

### 2.2 明确搜索候选项的展示能力

第一版可以继续返回：

```json
["02428", "IR64", "C7"]
```

此时远程候选项只展示 accession，不承诺在下拉框中展示 species 和 subpopulation。

如果后续需要展示：

```text
02428 · Oryza sativa · GJ
```

则增加兼容参数，例如：

```text
GET /files/query/organisms/?search=oryza&limit=20&format=summary
```

结构化响应示例：

```json
[
  {
    "accession": "02428",
    "scientific_name": "Oryza sativa",
    "sub_population": "GJ"
  }
]
```

不得直接改变现有接口的默认响应结构。

### 2.3 supplementary-data 避免 N+1 查询

为 `supplementary-data` 增加 species 元数据时，查询必须使用：

```python
Accession.objects.select_related("species").order_by("accession")
```

返回字段建议为：

```json
{
  "02428": {
    "species_code": "ORYZA_SATIVA",
    "scientific_name": "Oryza sativa",
    "chinese_name": "水稻",
    "common_name": "Rice",
    "sub_population": "GJ",
    "country": "China",
    "region": "Jiangsu",
    "longitude": 118.76,
    "latitude": 32.06
  }
}
```

如果 Accession Portal 不使用 `seq_data`，则不应仅为本页面继续传输该字段。若现有其他调用方依赖该字段，可暂时保留，并在后续版本通过 `fields` 参数或独立接口收敛响应。

后端测试中应增加查询数量断言，防止加入 species 字段后出现每条 accession 一次额外查询的问题。

### 2.4 明确全量接口的规模边界

当前约数百条 accession 时，可以由一次 `supplementary-data` 请求同时服务 Recent、Favorites 和 Map，以降低第一版实施复杂度。

但该策略必须定义演进条件：

- 记录数或响应体达到约定阈值后，不再向一级页面传输全部 accession 明细。
- 地图数据改为服务端聚合结果。
- Recent/Favorites 元信息改为 accession 批量查询。
- 可新增 `portal-summary` 或使用 `fields`、`accessions` 参数，而不是坚持永不新增 Portal API。

建议在开发或测试环境记录响应条数、响应体大小和接口耗时，作为后续拆分依据。

### 2.5 完善地图聚合点交互

地图仍可使用 `2° × 2°` 网格进行第一版视觉聚合，但必须定义聚合点点击行为：

```text
count === 1
→ 直接进入对应 Accession Detail

count > 1
→ 打开 Popover、Dialog 或 Drawer 显示 accession 列表
→ 用户选择具体 accession 后进入详情
```

不得在聚合点包含多条记录时任意打开第一条 accession。

Tooltip 规则：

- 单点显示 accession、scientific name、subpopulation、country 和坐标。
- 聚合点显示区域或坐标范围、总数及前 5 条 accession。
- 超过 5 条时显示“另有 N 条”。

坐标校验：

```text
longitude != null
latitude != null
-180 <= longitude <= 180
-90 <= latitude <= 90
```

注意：经纬度 `0` 是合法值，不能使用 `if (longitude && latitude)` 判断。

网格计算还应明确：

- 经纬度落在网格边界时的归属规则。
- `180/-180` 附近数据的处理方式。
- 聚合点坐标使用网格中心还是成员坐标平均值。

Bubble 大小可暂时保持四档，但建议最终使用带上下限的连续函数，例如 `sqrt(count)`，减少 10/11、50/51 等边界处的突变。

### 2.6 完善 Recent 数据升级和容错

建议将新结构使用版本化 key：

```text
recent_accessions_v2
```

保留对旧 key 的一次性迁移：

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
- 过滤空值、非字符串 accession、非法对象和重复 accession。
- 保留原有顺序。
- 成功写入新 key 后继续从新 key 读取。
- 旧数据没有时间时显示 `—`，不得显示成“刚刚”。
- 时间统一存 UTC ISO 8601，显示时按浏览器本地时区格式化。
- 同一 accession 再次访问时更新时间并移动到首位。
- 明确最大保留 20 条，一级页面只展示前 5 条。
- JSON 解析或 `localStorage` 写入失败时返回安全默认值，不阻断详情页。

如需支持多标签页同步，应监听浏览器 `storage` 事件。

### 2.7 Recent 应在详情成功加载后记录

推荐记录时机：

```text
Accession Detail API 成功返回
→ recordRecentAccession(accession)
```

这样不存在的 accession、接口失败或错误跳转不会出现在 Recently Viewed 中。

如果产品最终决定记录“最近点击”而非“最近成功浏览”，则可以在跳转时记录，但需要在产品语义和测试中明确。

### 2.8 固化 View All 交互

不再保留“Drawer 或 Dialog”这种实施时待定描述。建议统一使用 Drawer：

- Recently Viewed 和 My Favorites 复用同一个列表 Drawer 容器。
- 桌面端宽度约 480–560px。
- 移动端宽度 100%。
- Recent 支持删除单条和清空全部。
- Favorites 支持在 Drawer 内取消收藏。
- 关闭后焦点返回触发按钮。
- 支持 Esc 关闭及完整键盘操作。

---

## 3. Favorites 修订要求

Favorites 第一版继续使用：

```text
favorite_accessions_v1
```

数据结构：

```json
[
  {
    "accession": "02428",
    "created_at": "2026-09-17T02:00:00.000Z"
  }
]
```

补充规则：

- accession 唯一，不允许重复收藏。
- 收藏时间存 UTC ISO 8601。
- 非法 localStorage 数据自动忽略。
- 写入失败只提示收藏未保存，不影响详情页其他功能。
- Portal 与 Detail 在同一标签页内应立即同步。
- 多标签页同步可通过 `storage` 事件实现。
- 收藏按钮必须具有明确的 `aria-label` 和选中状态。
- 不应仅通过星标颜色表达收藏状态，还应提供文本或可访问名称。

详情页入口状态：

```text
☆ Favorite
★ Favorited
```

---

## 4. 前端组件结构修订

推荐结构：

```text
vue_project/src/components/accession/
├── AccessionPortalHeader.vue
├── AccessionSearchPanel.vue
├── RecentAccessions.vue
├── FavoriteAccessions.vue
├── AccessionDistributionMap.vue
├── AccessionListDrawer.vue
└── CompactAccessionMap.vue

vue_project/src/services/
└── accessionPreferences.js
```

`AccessionCard.vue` 只负责：

- 根据 route query 判断 Portal 或 Detail 状态。
- 组织 Portal 子组件。
- 提供统一 `openAccession()` 导航。
- 协调 Portal 数据加载和局部错误状态。

建议结构：

```vue
<template>
  <div class="accession-portal">
    <template v-if="!routeAccession">
      <AccessionPortalHeader />

      <AccessionSearchPanel
        @select="openAccession"
      />

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
        @select-cluster="openClusterList"
      />

      <AccessionListDrawer />
    </template>

    <AccessionDetailTableView
      v-else
      embedded
    />
  </div>
</template>
```

---

## 5. 视觉稿实施说明

附件中的 HTML/CSS 仅作为布局、颜色、间距和响应式参考，不应整体复制进 Vue 项目。

实施约束：

- 顶部导航继续使用项目现有 TopNav，不在 Accession 页面重复实现。
- HTML 中的静态 SVG 地图只用于示意，实际使用 ECharts 世界地图。
- 只有在地图确实支持缩放时才展示 `+/-` 控件。
- Geographic Distribution 标题区增加 `View Full Map →`，跳转 `/accession-map`。
- Recently Viewed 和 Favorites 的列布局需处理长 accession、长学名和中文名称。
- 文本溢出使用 ellipsis，并通过 `title` 或 tooltip 提供完整内容。
- 小屏幕下 Recent/Favorites 上下排列。
- 极小屏幕下可以隐藏次要列，但 accession 必须始终可见。
- Favorites 可以内部纵向滚动，但两张快捷卡片应使用统一高度 token。
- DNA、chromosome 等背景装饰应复用公共组件或统一 CSS，不复制多套 SVG。
- 装饰元素使用 `aria-hidden="true"`，不得进入键盘焦点序列。

---

## 6. Loading、Empty 与 Error 修订

每个区域独立管理状态：

```text
Search error
Recent empty/error
Favorites empty/error
Map loading/empty/error
```

要求：

- Map 加载失败不得影响 Search、Recent 和 Favorites。
- metadata 获取失败时，Recent/Favorites 仍显示 accession，缺失字段显示 `—`。
- Search 请求失败时显示轻量错误提示，并保留 Examples。
- 页面初次加载地图时显示 skeleton 或固定高度 loading，避免布局跳动。
- Retry 只重试失败区域。
- Empty、Error 和 Loading 文案全部进入 i18n。

---

## 7. 补充测试要求

### 7.1 Backend

在原测试清单基础上增加：

```text
✓ query_organisms 默认 limit 生效
✓ query_organisms 不允许超过最大 limit
✓ 空 search 不返回全量 accession
✓ accession 精确匹配排在首位
✓ accession 前缀匹配优先于 species 匹配
✓ species/subpopulation 搜索结果去重
✓ 超长 search 得到明确处理
✓ supplementary-data 返回新增 species metadata
✓ species 为空时返回 null，不抛出异常
✓ supplementary-data 使用 select_related，无 N+1 查询
```

### 7.2 Frontend

在原测试清单基础上增加：

```text
✓ 少于 2 个字符不发送远程搜索
✓ 搜索 debounce 生效
✓ 旧请求不会覆盖新请求结果
✓ 清空输入不会请求全量 accession
✓ 搜索失败后 Examples 仍可使用

✓ localStorage JSON 损坏时安全降级
✓ localStorage 非数组值安全降级
✓ Recent 混合新旧结构可迁移
✓ Recent 旧数据的时间显示为 —
✓ localStorage 写入失败不阻断导航
✓ 详情加载失败不写入 Recent
✓ Favorites 在 Portal/Detail 之间即时同步

✓ longitude/latitude 为 0 时仍显示地图点
✓ 越界经纬度不会显示
✓ 聚合点 count=1 时直接导航
✓ 聚合点 count>1 时打开列表
✓ 聚合点不会任意跳转第一条 accession
✓ View Full Map 跳转 /accession-map

✓ Drawer 支持 Esc 关闭
✓ Drawer 关闭后焦点回到 View All
✓ 收藏按钮具有可访问名称和状态
✓ 装饰元素不进入焦点序列
✓ 页面卸载后地图实例和监听器被清理
✓ 页面卸载后未完成搜索请求被取消或忽略
```

---

## 8. 修订后的实施阶段

### Phase 0 — 契约确认

先确定：

- 搜索接口的 `limit`、空搜索、排序和兼容响应规则。
- Recent 的准确记录时机。
- 聚合点多 accession 时的列表交互。
- supplementary-data 第一版允许使用的规模范围。

### Phase 1 — Preferences

实现：

- `accessionPreferences.js`
- Recent v1 → v2 数据迁移
- Favorites v1
- 数据校验、去重、时间更新和 localStorage 容错
- Preferences 单元测试

随后在 `AccessionDetailTableView.vue` 增加收藏入口，并在详情成功加载后记录 Recent。

### Phase 2 — Backend Search and Metadata

实现：

- `query_organisms()` 多字段搜索。
- limit、排序、去重和空关键词约束。
- `query_supplementary_data()` 增加 species metadata。
- `select_related("species")`。
- 后端功能及查询数量测试。

### Phase 3 — Portal and Search

实现：

- `AccessionPortalHeader.vue`
- `AccessionSearchPanel.vue`
- Portal 主布局
- debounce、取消过期请求、Examples 和搜索错误状态

### Phase 4 — Recent and Favorites

实现：

- `RecentAccessions.vue`
- `FavoriteAccessions.vue`
- `AccessionListDrawer.vue`
- Portal/Detail 状态同步
- 空状态、滚动和响应式布局

### Phase 5 — Geographic Distribution

实现：

- `AccessionDistributionMap.vue`
- 坐标校验
- 网格聚合和 bubble size
- 单点及聚合 tooltip
- 单点导航和聚合列表
- View Full Map
- 独立 loading、empty、error 和 retry

### Phase 6 — UI、i18n、Accessibility and Regression

完成：

- 中英文文案。
- 响应式和文本溢出处理。
- 键盘操作、焦点恢复和 ARIA 状态。
- API、Preferences、组件及路由回归测试。
- 地图实例、事件监听器和请求清理检查。

---

## 9. 修订后的验收标准

最终必须满足：

```text
✓ /accession-card 无 query 时显示正式 Portal
✓ /accession-card?accession=02428 继续显示原详情页
✓ 不新增 accession-search-result 一级路由

✓ Search 支持 accession、species 和 subpopulation
✓ Search 有结果上限、明确排序和请求防抖
✓ 空搜索不拉取全量 accession
✓ 旧搜索接口默认 response shape 不变

✓ Recent 使用版本化 localStorage 并兼容旧数据
✓ Recent 在详情成功加载后记录
✓ Recent 不重复、再次访问置顶并更新时间
✓ Favorites 使用 localStorage 且可添加、取消和刷新保留
✓ Preferences 读写错误不影响主流程

✓ Recent/Favorites 元数据不产生逐条 API 请求
✓ supplementary-data 增加 species metadata 时无 N+1 查询

✓ 地图只使用有效经纬度，0 坐标有效
✓ 地图复用 ECharts/worldMapData
✓ 单记录点可以进入详情
✓ 多记录聚合点先展示列表，不任意跳转
✓ Map 失败不影响其他区域
✓ View Full Map 跳转 /accession-map

✓ View All 使用统一 Drawer
✓ 中英文、移动端和键盘操作正常
✓ 装饰元素不影响可访问性
✓ Accession Detail、Assembly、Annotation 等现有链路不受影响
```

---

## 10. 最终建议

原方案无需推倒重写。完成本修订意见中的必须项后，即可作为正式开发依据。

其中最优先解决的四项是：

1. 搜索结果上限、排序、debounce 和过期请求处理。
2. supplementary-data 的 `select_related("species")` 与规模边界。
3. Recent 数据迁移、容错和准确记录时机。
4. 地图聚合点包含多条 accession 时的交互规则。

这些问题如果在编码前确定，可以显著降低接口返工、前端状态不一致和数据量增长后的性能风险。
