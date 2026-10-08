import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const view = readFileSync(resolve(process.cwd(), 'src/views/AnnotationView.vue'), 'utf8')
const searchPanel = readFileSync(
  resolve(process.cwd(), 'src/components/annotation/AnnotationSearchPanel.vue'),
  'utf8'
)
const summaryBar = readFileSync(
  resolve(process.cwd(), 'src/components/annotation/AnnotationSummaryBar.vue'),
  'utf8'
)

test('Annotation Phase 4 uses the portal hero, search panel, summary and result card hierarchy', () => {
  assert.match(view, /class="annotation-hero"/)
  assert.match(view, /<AnnotationSearchPanel/)
  assert.match(view, /<AnnotationSummaryBar/)
  assert.match(view, /class="data-card-header"/)
  assert.match(view, /page\.annotation\.tableTitle/)
  assert.match(view, /page\.annotation\.resultCount/)
})

test('Annotation search keeps all five selectors and search action in one desktop row', () => {
  const order = [
    'field-accession',
    'field-assembly',
    'field-annotation',
    'field-chromosome',
    'field-feature',
    'submit-button'
  ].map(token => searchPanel.indexOf(token))
  assert.ok(order.every(index => index >= 0))
  assert.deepEqual(order, [...order].sort((a, b) => a - b))
  assert.match(searchPanel, /grid-template-columns:\s*minmax\(160px,[\s\S]*110px;/)
  assert.match(searchPanel, /\.search-scroll \{[\s\S]*?overflow-x: auto;/)
  assert.match(searchPanel, /scrollbar-width: none;/)
  assert.match(searchPanel, /min-width: 1100px;/)
})

test('Annotation search separates context and view actions from the single-row query controls', () => {
  assert.match(searchPanel, /class="search-footer"/)
  assert.match(searchPanel, /page\.annotation\.currentData/)
  assert.match(searchPanel, /\$emit\('reset'\)/)
  assert.match(searchPanel, /\$emit\('view-change', 'table'\)/)
  assert.match(searchPanel, /\$emit\('view-change', 'chart'\)/)
})

test('Annotation summary shows the full unfiltered metadata contract', () => {
  assert.match(summaryBar, /summary\?\.total_features/)
  assert.match(summaryBar, /summary\?\.chromosome_count/)
  assert.match(summaryBar, /summary\?\.feature_type_count/)
  assert.match(view, /:summary="annotationStatistics"/)
})

test('Annotation Phase 4 preserves the existing table columns and pagination', () => {
  for (const property of ['seqid', 'feature', 'start', 'end', 'length', 'strand', 'source', 'score']) {
    assert.match(view, new RegExp(`el-table-column prop="${property}"`))
  }
  assert.match(view, /<el-pagination/)
  assert.match(view, /:page-sizes="\[20, 50, 100, 200\]"/)
})
