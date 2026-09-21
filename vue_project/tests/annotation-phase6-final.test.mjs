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

test('Annotation Phase 6 names every search control and its narrow-screen scroll region', () => {
  for (const key of [
    'accessionFieldLabel',
    'assemblyFieldLabel',
    'annotationFieldLabel',
    'chromosomeFieldLabel',
    'featureFieldLabel'
  ]) {
    assert.match(searchPanel, new RegExp(`page\\.annotation\\.${key}`))
  }
  assert.match(searchPanel, /class="search-scroll"[\s\S]*tabindex="0"/)
  assert.match(searchPanel, /page\.annotation\.horizontalScrollHint/)
  assert.match(searchPanel, /:aria-pressed="viewMode === 'table'"/)
  assert.match(searchPanel, /:aria-pressed="viewMode === 'chart'"/)
})

test('Annotation Phase 6 exposes semantic statistics and named async result states', () => {
  assert.match(summaryBar, /<dl[\s\S]*<dt>[\s\S]*<dd>/)
  assert.match(summaryBar, /:aria-busy="String\(loading\)"/)
  assert.match(view, /role="region"/)
  assert.match(view, /:aria-busy="String\(loading \|\| loadingAnnotation \|\| loadingVisualization\)"/)
  assert.match(view, /role="status" aria-live="polite"/)
  assert.match(view, /:aria-label="\$t\('page\.annotation\.tableTitle'\)"/)
  assert.match(view, /:aria-label="\$t\('page\.annotation\.paginationLabel'\)"/)
})

test('Annotation Phase 6 keeps recoverable table and visualization errors visible', () => {
  assert.match(view, /const dataErrorKey = ref\(''\)/)
  assert.match(view, /const visualizationErrorKey = ref\(''\)/)
  assert.match(view, /dataErrorKey\.value = 'page\.annotation\.dataLoadFailed'/)
  assert.match(view, /visualizationErrorKey\.value = 'page\.annotation\.visualizationLoadFailed'/)
  assert.match(view, /v-if="viewMode === 'table' && dataErrorKey"[\s\S]*fetchAnnotationData/)
  assert.match(view, /v-else-if="visualizationErrorKey"[\s\S]*fetchVisualizationData/)
})

test('Annotation visualization controls and chart have accessible names', () => {
  assert.match(view, /page\.annotation\.featureControlsLabel/)
  assert.match(view, /page\.annotation\.decreaseRowLength/)
  assert.match(view, /page\.annotation\.rowLengthInputLabel/)
  assert.match(view, /page\.annotation\.increaseRowLength/)
  assert.match(view, /role="img"[\s\S]*page\.annotation\.visualizationLabel/)
})
