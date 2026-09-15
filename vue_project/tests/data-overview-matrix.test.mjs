import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const repoRoot = process.cwd()
const viewPath = resolve(repoRoot, 'src/views/DataOverviewView.vue')
const source = readFileSync(viewPath, 'utf8')

assert.match(source, /query\/data-overview\//, 'DataOverviewView should use the new data overview endpoint')
assert.match(source, /query\/data-overview-files\//, 'DataOverviewView should load drawer files from the new endpoint')
assert.match(source, /page\.dataOverview\.matrixView/, 'matrix view tab should be localized')
assert.match(source, /page\.dataOverview\.detailView/, 'detail view tab should be localized')
assert.match(source, /page\.dataOverview\.fileStatistics/, 'matrix header should use localized file statistics copy')
assert.doesNotMatch(source, /数据类型（点击单元格查看文件）/, 'matrix header should not use technical cell-click copy')
assert.match(source, /page\.accessionDetail\.viewFiles/, 'detail rows should provide a localized view files action')
assert.match(source, /page\.dataOverview\.comingSoon/, 'population data without real data should render as localized building state')
assert.match(source, /DataFile/, 'download/file drawer copy should refer to DataFile')
assert.match(source, /selectedSpecies/, 'DataOverviewView should expose a species filter')
assert.match(source, /params\.species/, 'DataOverviewView should submit species filters to the API')
assert.match(source, /categoryLabel\(row\.category\)/, 'category labels should use locale-aware display values')
assert.doesNotMatch(source, /category\.en_label\s*}}/, 'matrix headers must not render bilingual category labels')
assert.match(source, /\.summary-card\s*\{[\s\S]*?min-height:\s*78px/, 'summary cards should match accession detail card height')
assert.match(source, /\.summary-icon\s*\{[\s\S]*?width:\s*38px[\s\S]*?height:\s*38px/, 'summary icons should match accession detail size')
assert.match(source, /\.summary-label\s*\{[\s\S]*?font-size:\s*12px/, 'summary labels should match accession detail font size')
assert.match(source, /\.summary-value\s*\{[\s\S]*?font-size:\s*21px/, 'summary numbers should match accession detail font size')
assert.doesNotMatch(source, /genome-files/, 'DataOverviewView must not reference old genome-files URLs')
assert.doesNotMatch(source, /legacy_genomefile/, 'DataOverviewView must not reference legacy source names')
assert.doesNotMatch(source, /organism_fallback/, 'DataOverviewView must not reference organism fallback')

console.log('data-overview matrix source checks passed')
