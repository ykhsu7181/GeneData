# GeneData 导航栏重构修订意见

## 1. 总体结论

原方案整体可行，以下边界合理：

- 一级导航收敛为少量核心入口。
- Assembly 使用独立路由，不复用 Genome 页面。
- Tools 只退出顶部导航，不删除功能和路由。
- 首页 Accession 搜索继续直达详情。
- `/raw-data` 保持原路由，避免破坏已有链接。

正式实施前建议完成以下修订。

---

## 2. 必须修订项

### 2.1 谨慎设置 Assembly 一级占位入口

一级导航应代表核心且可用的功能。当前方案中的 Assembly 页面只有：

```text
This module is under development.
```

建议二选一：

1. Assembly 至少具备基础列表、搜索或详情入口后，再作为一级导航；
2. 短期先放入 More，功能可用后再提升为一级入口。

如果 Assembly 已确定为近期交付的核心模块，可以保留原方案，但应明确占位期限和后续负责人。

### 2.2 导航配置必须只有一个数据源

当前 `TopNavBar.vue` 在组件内维护 `primaryNavItems`，下拉菜单则来自 `topNavConfig.mjs`，存在双重配置。

建议统一为：

```js
export const topNavItems = [
  { key: 'home', labelKey: 'nav.home', path: '/dashboard' },
  { key: 'accession', labelKey: 'nav.accession', path: '/accession-card' },
  { key: 'assembly', labelKey: 'nav.assembly', path: '/assembly' },
  {
    key: 'data',
    labelKey: 'nav.data',
    path: '/data-overview',
    children: [/* ... */]
  },
  {
    key: 'more',
    labelKey: 'nav.more',
    children: [/* ... */]
  }
]
```

`TopNavBar.vue` 根据 `children` 统一渲染普通入口或下拉菜单，不再单独硬编码一级菜单。

### 2.3 下拉菜单不能只依赖 hover

Data 和 More 必须支持：

- 鼠标点击；
- 键盘操作；
- 触屏设备；
- 可见的焦点状态。

建议使用 click 触发。Data 可以采用“主按钮跳转、箭头展开”，More 整体作为菜单按钮，并设置合适的 `aria-haspopup` 等属性。

### 2.4 补齐所有现有路由的 Active Group

原方案尚未明确以下路由：

```text
/data
/data-chart
/transcriptome
/placeholder
```

建议：

```text
/data
/data-chart
→ Data

/transcriptome
→ More

/placeholder
→ 无 active，或根据实际来源确定

隐藏的 Tools 路由
→ 保持可直接访问，但不高亮一级导航
```

---

## 3. 命名修订建议

### 3.1 Research Group Data 需确认语义

当前 `/raw-data` 页面实际展示原始测序数据、文件路径与校验状态。

`Research Group Data` 容易被理解为课题组全部数据。更准确的名称是：

```text
Research Group Raw Data
课题组原始数据
```

如果产品决定继续使用 `Research Group Data`，页面副标题应明确当前范围仅为原始测序文件。

建议只调整：

- 导航名称；
- 页面主标题；
- 页面副标题；
- 面包屑。

文件列表、详情和错误提示中的“原始数据文件”仍可保留，不需要机械替换所有业务术语。

### 3.2 More 的信息架构需产品确认

Genome、Annotation、Transcriptome 都是重要数据类型。将它们放入 More 会降低可发现性。

该设计适合以下前提：

- Accession、Assembly、Data 是当前最核心入口；
- Genome、Annotation、Transcriptome 主要作为二级资源页面；
- 用户仍能通过搜索、详情页和 More 到达这些页面。

建议根据真实使用频率确认最终层级。

---

## 4. 搜索行为修订

导航重组不代表业务搜索入口需要删除。

建议继续保留：

```text
genome       → /genome-card
annotation   → /annotation
transcriptome → /transcriptome-overview
codon        → /codon-card
core/variable → /core-variable-blocks
```

这样即使 Tools 不在顶部显示，原功能仍可通过搜索和直接链接使用。

Assembly 当前只是占位页时，不建议增加：

```text
assembly → /assembly
```

否则用户搜索数据资源时会进入无业务能力的页面。等 Assembly 页面具备实际能力后再增加搜索映射。

首页搜索 Accession 继续保持：

```text
IR64 → /accession-card?accession=IR64
```

顶部 Accession 导航仍进入：

```text
/accession-card
```

两者职责不应合并。

---

## 5. 推荐测试补充

除原方案已有测试外，增加以下覆盖：

- 中英文 locale 均包含新增导航 key；
- `TopNavBar.vue` 不再维护第二份一级导航配置；
- Data 和 More 支持点击、键盘及触屏展开；
- `/data`、`/data-chart`、`/transcriptome` 的 active group 正确；
- Tools 隐藏后，相关路由仍可直接访问；
- Assembly 占位页不发起无效 API 请求；
- 移动端导航不存在横向溢出；
- `/raw-data` 改名后，路由、API 和内部业务字段保持不变；
- 首页 Accession 搜索和顶部 Accession 入口行为不同且均正确。

---

## 6. 推荐实施顺序

建议压缩为三个提交：

### Commit 1

```text
feat(nav): add assembly route and navigation model
```

- 确认 Assembly 是否进入一级导航；
- 新增 Assembly 页面和路由；
- 建立单一导航配置源；
- 更新 Active Group。

### Commit 2

```text
refactor(nav): simplify portal navigation and data naming
```

- 重构 TopNavBar；
- Data、More 支持点击和键盘；
- Tools 退出顶部导航；
- 调整 i18n；
- 调整 Research Group Data 页面文案。

### Commit 3

```text
test(nav): cover portal navigation routes and interactions
```

- 更新导航结构和 active 测试；
- 增加 Assembly 路由测试；
- 增加搜索和隐藏 Tools 路由回归测试。

---

## 7. 修订后验收标准

```text
✓ 导航结构只有一个配置源
✓ 一级导航顺序符合最终产品决定
✓ Assembly 使用独立路由，不复用 GenomeCard
✓ 不向用户暴露长期无功能的一级入口
✓ Data 与 More 支持鼠标、键盘和触屏操作
✓ 所有主要现有路由均有明确的 active 规则
✓ Tools 不在顶部显示，但相关路由和功能仍保留
✓ Research Group Data 名称与实际数据范围一致
✓ 首页 Accession 搜索继续直达详情
✓ 中英文导航文案完整
✓ 移动端导航无明显溢出
✓ npm run build 和 npm test 通过
✓ 主要页面回归正常
```

结论：原方案技术上可以实施，但应先确定 Assembly 占位入口的产品策略，并完成单一导航配置、交互可访问性和遗漏路由归属三项修订。
