# Dashboard Home Visual Refinement Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the dashboard homepage to a high-fidelity portal layout with full-page vertical scrolling, sticky top navigation, a hero section closer to the target mockup, richer species cards, polished distribution panels, and a refined geo map section without changing backend data contracts.

**Architecture:** Keep `/gd/api/warehouse/dashboard/` as the only homepage data source and concentrate changes in the Vue app shell plus homepage-only components. Reuse current dashboard payload fields for sub-population and geo distribution, rename the misleading XI module to a neutral grouping module at the view layer, and preserve existing business routes and DataFile-only download/query paths.

**Tech Stack:** Vue 3, Vue Router 4, Element Plus, ECharts, Axios, Vue CLI, ESLint

---

## File Structure

**Frontend shell**

- Modify: `vue_project/src/App.vue`
  - Own the global page shell, sticky header offset, full-page scroll behavior, and dashboard-vs-business-page content width rules.

- Modify: `vue_project/src/components/TopNavBar.vue`
  - Own sticky top nav styling, brand treatment, active state visuals, mobile wrapping, and portal-style navigation polish.

**Homepage presentation**

- Modify: `vue_project/src/views/DashboardHomeView.vue`
  - Own the homepage section order, renamed right-side grouping panel, loading/error/empty states, and section wrappers.

- Modify: `vue_project/src/components/DashboardHero.vue`
  - Own the hero background, headline/subtitle, search layout, hot keywords, and summary cards.

- Modify: `vue_project/src/components/SpeciesCardGrid.vue`
  - Own the image-style species cards, top banner/cover treatment, metric layout, and hover interactions.

- Modify: `vue_project/src/components/DistributionPanel.vue`
  - Own the paired distribution card shell, chart/legend ratio, neutral grouping display, and polished total chip layout.

- Modify: `vue_project/src/components/GeoMapPanel.vue`
  - Own the map container styling, legend cards, tooltip emphasis, and target-mockup panel structure.

**Data and routing contracts**

- Read only: `vue_project/src/services/dashboard.js`
- Read only: `vue_project/src/config/dashboardSearch.js`
- Read only: `django2/files/services/dashboard_service.py`

**Verification**

- Use existing commands only:
  - `npm run lint`
  - `npm run build`

---

### Task 1: Fix the App Shell for Full-Page Scroll and Sticky Portal Layout

**Files:**
- Modify: `vue_project/src/App.vue`
- Modify: `vue_project/src/components/TopNavBar.vue`

- [ ] **Step 1: Capture the failing layout behavior before editing**

Run:

```bash
cd vue_project
npm run build
```

Expected:

- Build succeeds
- Current homepage still uses a narrow centered content well
- Full-page portal scrolling and top spacing are not yet tuned to the new design target

- [ ] **Step 2: Update `App.vue` so dashboard pages can use a wider portal canvas and full-page vertical scroll**

Add a route-aware shell branch like:

```vue
<template>
  <div class="app-shell">
    <router-view v-if="isStandaloneRoute" />

    <div v-else :class="['layout-shell', { 'is-dashboard-route': isDashboardRoute }]">
      <TopNavBar
        :current-language="currentLanguage"
        @language-change="handleLanguageChange"
        @logout="handleLogout"
      />

      <main :class="['layout-main', { 'layout-main-dashboard': isDashboardRoute }]">
        <router-view />
      </main>

      <footer class="layout-footer">
        {{ $t('footer.version') }}
      </footer>
    </div>
  </div>
</template>
```

Add the computed flag:

```js
const isDashboardRoute = computed(() => route.path === '/' || route.path === '/dashboard')
```

Replace the shell CSS with a version that preserves natural document scrolling:

```css
.app-shell,
.layout-shell {
  min-height: 100vh;
}

.layout-shell {
  display: flex;
  flex-direction: column;
}

.layout-main {
  flex: 1;
  width: min(1480px, calc(100% - 40px));
  margin: 0 auto;
  padding: 28px 0 36px;
}

.layout-main-dashboard {
  width: min(1680px, calc(100% - 32px));
  padding: 0 0 48px;
}
```

- [ ] **Step 3: Update `TopNavBar.vue` to behave like a true sticky portal header**

Keep the existing route logic, but revise the header wrapper and nav styles toward:

```css
.top-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 24px;
  padding: 12px 32px;
  background: linear-gradient(180deg, rgba(5, 33, 78, 0.98), rgba(7, 24, 58, 0.96));
  box-shadow: 0 14px 30px rgba(4, 16, 40, 0.28);
  backdrop-filter: blur(14px);
}

.nav-link.is-active {
  background: linear-gradient(135deg, #1d4ed8, #2563eb);
  color: #fff;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.28);
}
```

Preserve:

- existing paths
- tools dropdown
- language change event
- logout event

- [ ] **Step 4: Run lint to confirm the shell refactor is clean**

Run:

```bash
cd vue_project
npm run lint
```

Expected:

- PASS
- No new lint errors in `App.vue` or `TopNavBar.vue`

- [ ] **Step 5: Commit the shell/layout task**

```bash
git add vue_project/src/App.vue vue_project/src/components/TopNavBar.vue
git commit -m "feat: refine dashboard shell and sticky portal nav"
```

### Task 2: Rebuild the Hero Section to Match the Portal-Style Target

**Files:**
- Modify: `vue_project/src/components/DashboardHero.vue`
- Modify: `vue_project/src/views/DashboardHomeView.vue`

- [ ] **Step 1: Lock the hero copy and summary-card structure before styling**

Keep the existing props and events:

```js
props: {
  summary: { type: Object, default: () => ({}) },
  hotKeywords: { type: Array, default: () => [] }
},
emits: ['search', 'keyword-click']
```

Keep the summary metrics mapped to:

```js
const summaryCards = computed(() => [
  { key: 'species', label: '物种数', value: props.summary.species_count || 0 },
  { key: 'accession', label: '材料数', value: props.summary.accession_count || 0 },
  { key: 'sample', label: '样本数', value: props.summary.sample_count || 0 },
  { key: 'file', label: '文件数', value: props.summary.datafile_count || 0 },
  { key: 'size', label: '数据量', value: props.summary.total_size_display || '0 B' }
])
```

- [ ] **Step 2: Rewrite the hero template for a target-like large visual header**

Replace the current section with a structure like:

```vue
<section class="hero-panel">
  <div class="hero-backdrop"></div>

  <div class="hero-content">
    <div class="hero-copy">
      <p class="eyebrow">Gene Data Warehouse</p>
      <h1>基因数据仓库首页</h1>
      <p class="hero-subtitle">
        快速检索与浏览，探索作物种基因数据结果
      </p>

      <div class="hero-search">
        <!-- existing el-input + button -->
      </div>

      <div class="hot-keywords">
        <span class="hot-label">热门搜索:</span>
        <!-- existing keyword loop -->
      </div>
    </div>

    <div class="hero-summary">
      <!-- existing summary cards -->
    </div>
  </div>
</section>
```

- [ ] **Step 3: Add the higher-fidelity hero styling**

Use a layered hero style like:

```css
.hero-panel {
  position: relative;
  min-height: 540px;
  padding: 88px 64px 56px;
  border-radius: 0 0 32px 32px;
  overflow: hidden;
  background:
    linear-gradient(rgba(8, 24, 40, 0.38), rgba(8, 24, 40, 0.42)),
    linear-gradient(120deg, #527d18 0%, #9aa63d 28%, #436b12 56%, #8b7a16 100%);
}

.hero-content {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.75fr);
  gap: 32px;
  align-items: center;
}

.hero-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  margin-top: 28px;
}
```

Style the search box and button as prominent homepage controls instead of admin-form controls.

- [ ] **Step 4: Add a dashboard-level loading and error wrapper in `DashboardHomeView.vue`**

Introduce state:

```js
const isLoading = ref(true)
const loadError = ref('')
```

Wrap the fetch:

```js
const loadDashboard = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    dashboard.value = await fetchDashboardData()
  } catch (error) {
    console.error('Failed to load dashboard data', error)
    loadError.value = '首页统计加载失败，请稍后重试。'
    ElMessage.error(loadError.value)
  } finally {
    isLoading.value = false
  }
}
```

Render:

```vue
<div class="dashboard-home">
  <DashboardHero ... />
  <div v-if="loadError" class="dashboard-error">{{ loadError }}</div>
  <template v-else>
    <!-- remaining sections -->
  </template>
</div>
```

- [ ] **Step 5: Run lint and commit the hero task**

```bash
cd vue_project
npm run lint
git add vue_project/src/components/DashboardHero.vue vue_project/src/views/DashboardHomeView.vue
git commit -m "feat: redesign dashboard hero and homepage load states"
```

### Task 3: Upgrade Species Cards to a Portal Card Gallery

**Files:**
- Modify: `vue_project/src/components/SpeciesCardGrid.vue`
- Modify: `vue_project/src/views/DashboardHomeView.vue`

- [ ] **Step 1: Keep the current card data contract and cap the homepage feature count**

Retain:

```js
const featuredSpeciesCards = computed(() => dashboard.value.species_cards.slice(0, 4))
```

Do not introduce new backend fields in this phase.

- [ ] **Step 2: Replace the species-card markup with a mockup-aligned media card**

Rewrite the card article like:

```vue
<article
  v-for="card in cards"
  :key="card.species_id"
  class="species-card"
  :style="{ '--card-accent': card.accent_color || '#1d4ed8' }"
  @click="$emit('select', card)">
  <div class="card-cover">
    <div class="card-overlay"></div>
    <div class="card-badge">{{ card.species_code }}</div>
  </div>

  <div class="card-body">
    <div class="card-title">
      <h3>{{ card.name_cn }}</h3>
      <p>{{ card.latin_name }}</p>
    </div>

    <div class="metrics-row">
      <div class="metric-item">
        <span>材料数</span>
        <strong>{{ formatNumber(card.accession_count) }}</strong>
      </div>
      <div class="metric-item">
        <span>样本数</span>
        <strong>{{ formatNumber(card.sample_count) }}</strong>
      </div>
      <div class="metric-item">
        <span>数据集数</span>
        <strong>{{ formatNumber(card.dataset_count) }}</strong>
      </div>
    </div>
  </div>
</article>
```

- [ ] **Step 3: Replace the flat metric grid styling with cover-image portal card styling**

Use styles like:

```css
.card-cover {
  position: relative;
  min-height: 128px;
  background:
    linear-gradient(rgba(15, 23, 42, 0.15), rgba(15, 23, 42, 0.22)),
    linear-gradient(135deg, color-mix(in srgb, var(--card-accent) 48%, #1e293b), #84cc16);
}

.species-card {
  border-radius: 26px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.1);
}

.species-card::after {
  content: '';
  display: block;
  height: 4px;
  background: var(--card-accent);
}
```

Keep metrics to three core values for visual parity with the target layout.

- [ ] **Step 4: Add a loading skeleton path for empty dashboards**

In `DashboardHomeView.vue`, render a lightweight skeleton block while loading:

```vue
<section v-if="isLoading" class="dashboard-skeleton-grid">
  <div v-for="index in 4" :key="index" class="dashboard-skeleton-card"></div>
</section>
<section v-else class="dashboard-section">
  <SpeciesCardGrid :cards="featuredSpeciesCards" @select="handleSpeciesSelect" />
</section>
```

Add CSS:

```css
.dashboard-skeleton-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 22px;
}

.dashboard-skeleton-card {
  min-height: 260px;
  border-radius: 28px;
  background: linear-gradient(90deg, #e2e8f0 25%, #f8fafc 37%, #e2e8f0 63%);
  background-size: 400% 100%;
  animation: dashboardShimmer 1.4s ease infinite;
}
```

- [ ] **Step 5: Run lint and commit the species-card task**

```bash
cd vue_project
npm run lint
git add vue_project/src/components/SpeciesCardGrid.vue vue_project/src/views/DashboardHomeView.vue
git commit -m "feat: restyle dashboard species cards"
```

### Task 4: Polish Distribution Panels and Rename the Misleading XI Module

**Files:**
- Modify: `vue_project/src/views/DashboardHomeView.vue`
- Modify: `vue_project/src/components/DistributionPanel.vue`

- [ ] **Step 1: Rename the right-side XI panel at the view layer without changing backend payload keys**

In `DashboardHomeView.vue`, change the second distribution panel block from:

```vue
<DistributionPanel
  title="XI 组分布"
  kicker="XI groups"
  :items="dashboard.xi_distribution"
  value-key="accession_count"
  empty-text="暂无 XI 组统计数据"
/>
```

to:

```vue
<DistributionPanel
  title="群体分组"
  kicker="Grouping summary"
  :items="dashboard.xi_distribution"
  value-key="accession_count"
  empty-text="暂无群体分组统计数据"
/>
```

- [ ] **Step 2: Rebuild the distribution panel header and body to match the target card format**

Replace the distribution panel template body with:

```vue
<section class="distribution-panel">
  <div class="panel-header">
    <div class="panel-heading">
      <p class="panel-kicker">{{ kicker }}</p>
      <h3>{{ title }}</h3>
    </div>
    <div class="panel-switches">
      <button class="switch-chip is-active">图表</button>
      <button class="switch-chip">卡片</button>
    </div>
  </div>

  <div v-if="items.length" class="panel-body">
    <aside class="panel-stat-card">
      <span>总计</span>
      <strong>{{ totalValueLabel }}</strong>
    </aside>
    <div ref="chartRef" class="chart-box"></div>
    <div class="legend-list">
      <!-- existing legend rows -->
    </div>
  </div>

  <div v-else class="panel-empty">{{ emptyText }}</div>
</section>
```

- [ ] **Step 3: Tighten chart sizing and panel styling**

Use styles like:

```css
.panel-body {
  display: grid;
  grid-template-columns: 180px minmax(220px, 1fr) minmax(220px, 0.95fr);
  gap: 18px;
  align-items: center;
  margin-top: 18px;
}

.panel-stat-card {
  display: grid;
  place-items: center;
  min-height: 160px;
  border-radius: 22px;
  background: linear-gradient(180deg, #f8fbff, #eef6ff);
}

.chart-box {
  width: 100%;
  height: 280px;
}
```

Keep the existing ECharts data mapping intact.

- [ ] **Step 4: Add dashboard-level skeleton support for the distribution row**

In `DashboardHomeView.vue`:

```vue
<section v-if="isLoading" class="distribution-grid">
  <div class="panel-skeleton"></div>
  <div class="panel-skeleton"></div>
</section>
<section v-else class="distribution-grid">
  <!-- two distribution panels -->
</section>
```

Add:

```css
.panel-skeleton {
  min-height: 360px;
  border-radius: 26px;
  background: linear-gradient(90deg, #e2e8f0 25%, #f8fafc 37%, #e2e8f0 63%);
  background-size: 400% 100%;
  animation: dashboardShimmer 1.4s ease infinite;
}
```

- [ ] **Step 5: Run lint and commit the panel task**

```bash
cd vue_project
npm run lint
git add vue_project/src/views/DashboardHomeView.vue vue_project/src/components/DistributionPanel.vue
git commit -m "feat: refine dashboard distribution panels"
```

### Task 5: Refine the Geo Map Panel and Final Dashboard Page Composition

**Files:**
- Modify: `vue_project/src/components/GeoMapPanel.vue`
- Modify: `vue_project/src/views/DashboardHomeView.vue`

- [ ] **Step 1: Keep geo data reuse limited to safe homepage fields**

Continue consuming:

```js
<GeoMapPanel
  :points="dashboard.geo_distribution"
  @select="handleGeoSelect"
/>
```

Do not add any new API calls or introduce `GenomeFile`-related metrics.

- [ ] **Step 2: Remove dataset count emphasis from the map tooltip and legend cards**

Change tooltip output from:

```js
dataset: ${params.data.dataset_count}
```

to:

```js
地区: ${params.data.name}<br/>
材料数: ${params.data.accession_count}<br/>
样本数: ${params.data.sample_count}
```

Keep `dataset_count` in the payload if needed for future work, but do not foreground it in homepage UI.

- [ ] **Step 3: Rebuild the geo panel shell to match the target layout**

Use a structure like:

```vue
<section class="geo-panel">
  <div class="geo-header">
    <div>
      <p class="geo-kicker">Geographic distribution</p>
      <h3>地理分布</h3>
    </div>
    <div class="geo-scale-legend">
      <span>1 - 10</span>
      <span>11 - 50</span>
      <span>51 - 100</span>
      <span>101 - 500</span>
      <span>>500</span>
    </div>
  </div>

  <div v-if="points.length" class="geo-layout">
    <div ref="mapRef" class="geo-map"></div>
    <div class="geo-legend">
      <!-- existing top-point cards -->
    </div>
  </div>
</section>
```

Use map shell styling like:

```css
.geo-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.85fr);
  gap: 18px;
}

.geo-map {
  height: 500px;
  border-radius: 24px;
  background: linear-gradient(180deg, #edf5ff, #f8fbff);
}
```

- [ ] **Step 4: Finalize dashboard page spacing, section widths, and shared shimmer animation**

In `DashboardHomeView.vue`, replace the root styles with:

```css
.dashboard-home {
  display: grid;
  gap: 28px;
  padding-bottom: 24px;
}

.dashboard-section,
.distribution-grid {
  width: min(1480px, calc(100% - 32px));
  margin: 0 auto;
  display: grid;
  gap: 22px;
}

@keyframes dashboardShimmer {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
```

This keeps the hero full-width while the content below is neatly constrained.

- [ ] **Step 5: Run the full frontend verification and commit**

```bash
cd vue_project
npm run lint
npm run build
git add vue_project/src/components/GeoMapPanel.vue vue_project/src/views/DashboardHomeView.vue
git commit -m "feat: finalize dashboard map panel and page composition"
```

Expected:

- `npm run lint` passes
- `npm run build` passes
- No `/genome-files/` link is introduced by the dashboard homepage

### Task 6: End-to-End Review and Acceptance Sweep

**Files:**
- Review only: `vue_project/src/App.vue`
- Review only: `vue_project/src/components/TopNavBar.vue`
- Review only: `vue_project/src/components/DashboardHero.vue`
- Review only: `vue_project/src/components/SpeciesCardGrid.vue`
- Review only: `vue_project/src/components/DistributionPanel.vue`
- Review only: `vue_project/src/components/GeoMapPanel.vue`
- Review only: `vue_project/src/views/DashboardHomeView.vue`

- [ ] **Step 1: Run the final frontend checks**

```bash
cd vue_project
npm run lint
npm run build
```

Expected:

- PASS
- Only existing bundle-size warnings are acceptable

- [ ] **Step 2: Run targeted backend safety checks to ensure the dashboard API contract still exists**

```bash
cd ../django2
python manage.py test files.tests.test_dashboard_api files.tests.test_new_query_entrypoints --keepdb -v 2
python manage.py check
python manage.py makemigrations files --check --dry-run
```

Expected:

- Dashboard API tests pass
- Django system check passes
- `No changes detected`

- [ ] **Step 3: Perform a manual acceptance sweep in the browser**

Check:

```text
1. /dashboard can scroll vertically as a full page
2. Top navigation stays sticky during scroll
3. Hero visually reads like a portal header, not an admin card
4. Species cards show three core metrics and portal-style media treatment
5. Left chart uses sub_population_distribution
6. Right chart title is neutral and does not claim “XI 群分布”
7. Geo panel renders map points and region legend cards
8. Existing routes /data-overview, /accession-card, /annotation still open normally
9. No business UI on the dashboard shows /genome-files/ downloads
```

- [ ] **Step 4: Commit the final acceptance sweep notes**

```bash
git add vue_project/src/App.vue vue_project/src/components/TopNavBar.vue vue_project/src/components/DashboardHero.vue vue_project/src/components/SpeciesCardGrid.vue vue_project/src/components/DistributionPanel.vue vue_project/src/components/GeoMapPanel.vue vue_project/src/views/DashboardHomeView.vue
git commit -m "chore: complete dashboard homepage visual refinement"
```
