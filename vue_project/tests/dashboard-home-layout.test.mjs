import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const dashboardPath = join(process.cwd(), 'src', 'views', 'DashboardHomeView.vue')
const source = readFileSync(dashboardPath, 'utf8')

test('dashboard home removes distribution overview lead copy', () => {
  assert.doesNotMatch(source, /分布概览/)
  assert.doesNotMatch(source, /Distribution insights/i)
  assert.doesNotMatch(source, /section-lead/)
  assert.doesNotMatch(source, /lead-description/)
})

test('dashboard home keeps distribution panels and geo map after removing lead copy', () => {
  assert.match(source, /<DistributionPanel/)
  assert.match(source, /<GeoMapPanel/)
})

test('dashboard content only overlaps the hero slightly on desktop', () => {
  assert.match(source, /\.dashboard-overlap\s*{[\s\S]*?margin-top:\s*-28px;/)
  assert.match(
    source,
    /@media\s*\(max-width:\s*960px\)[\s\S]*?\.dashboard-overlap\s*{[\s\S]*?margin-top:\s*0;/
  )
  assert.doesNotMatch(source, /margin-top:\s*-78px;/)
  assert.doesNotMatch(source, /margin-top:\s*-48px;/)
})

test('dashboard home places data resources beside subpopulation and recent updates below geo map', () => {
  assert.match(source, /<DataResourceSummary/)
  assert.match(source, /class="resource-distribution-row"/)
  assert.match(source, /title="亚群分布"[\s\S]*?:items="dashboard\.sub_population_distribution"/)
  assert.doesNotMatch(source, /title="群体分组"/)
  assert.match(
    source,
    /<section class="dashboard-map-section">[\s\S]*?<GeoMapPanel[\s\S]*?<RecentUpdatesBar/
  )
})

test('dashboard home hides dataset type and file role distribution modules', () => {
  assert.doesNotMatch(source, /数据集类型分布/)
  assert.doesNotMatch(source, /文件角色分布/)
  assert.doesNotMatch(source, /dashboard\.dataset_type_summary/)
  assert.doesNotMatch(source, /dashboard\.file_role_summary/)
})

test('dashboard home does not show a large featured species lead title', () => {
  const speciesGridPath = join(process.cwd(), 'src', 'components', 'SpeciesCardGrid.vue')
  const speciesGridSource = readFileSync(speciesGridPath, 'utf8')

  assert.doesNotMatch(speciesGridSource, /Featured species/i)
  assert.doesNotMatch(speciesGridSource, /重点物种卡片/)
})

test('species cards keep a compact dashboard proportion', () => {
  const speciesGridPath = join(process.cwd(), 'src', 'components', 'SpeciesCardGrid.vue')
  const speciesGridSource = readFileSync(speciesGridPath, 'utf8')

  assert.match(speciesGridSource, /\.species-grid\s*{[\s\S]*?gap:\s*18px;/)
  assert.match(speciesGridSource, /grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(220px,\s*280px\)\);/)
  assert.match(speciesGridSource, /\.card-cover\s*{[\s\S]*?min-height:\s*56px;/)
  assert.match(speciesGridSource, /\.card-float-mark\s*{[\s\S]*?width:\s*34px;[\s\S]*?height:\s*34px;/)
  assert.match(speciesGridSource, /\.card-body\s*{[\s\S]*?padding:\s*18px 14px 10px;/)
  assert.doesNotMatch(speciesGridSource, /metrics-row/)
  assert.doesNotMatch(speciesGridSource, /metric-item/)
  assert.doesNotMatch(speciesGridSource, /材料数|样本数|数据集数/)
})
