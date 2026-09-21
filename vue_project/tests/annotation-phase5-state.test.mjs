import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const view = readFileSync(resolve(process.cwd(), 'src/views/AnnotationView.vue'), 'utf8')
const searchPanel = readFileSync(
  resolve(process.cwd(), 'src/components/annotation/AnnotationSearchPanel.vue'),
  'utf8'
)

test('Annotation URL includes every restorable interaction state with compact defaults', () => {
  for (const key of ['chromosome', 'feature', 'view', 'page', 'page_size']) {
    assert.match(view, new RegExp(`query\\.${key}`))
  }
  assert.match(view, /featureType && featureType !== 'all'/)
  assert.match(view, /view === 'chart'/)
  assert.match(view, /Number\(page\) > 1/)
  assert.match(view, /Number\(queryPageSize\) !== 50/)
})

test('Annotation restores filters, view and pagination from browser history', () => {
  assert.match(view, /requestedChromosome = normalizeQueryValue\(route\.query\.chromosome\)/)
  assert.match(view, /requestedFeatureType = normalizeQueryValue\(route\.query\.feature\) \|\| 'all'/)
  assert.match(view, /requestedViewMode = normalizeViewMode\(route\.query\.view\)/)
  assert.match(view, /requestedPage = normalizePositiveInteger\(route\.query\.page, 1\)/)
  assert.match(view, /requestedPageSize = normalizePageSize\(route\.query\.page_size\)/)
  assert.match(view, /route\.query\.chromosome,[\s\S]*route\.query\.page_size/)
})

test('Annotation uses history pushes for user actions and replacements for canonical correction', () => {
  assert.match(view, /const replaceRouteQuery = query => writeRouteQuery\(query, \{ replace: true \}\)/)
  assert.match(view, /const pushRouteQuery = query => writeRouteQuery\(query, \{ replace: false \}\)/)
  assert.match(view, /handleChromosomeChange[\s\S]*await pushRouteQuery\(buildCurrentRouteQuery\(\)\)/)
  assert.match(view, /handleViewModeChange[\s\S]*await pushRouteQuery\(buildCurrentRouteQuery\(\)\)/)
  assert.match(view, /reconcileRouteFilters[\s\S]*await replaceRouteQuery\(buildCurrentRouteQuery\(\)\)/)
})

test('Annotation preserves its validated Assembly return context across filter changes', () => {
  assert.match(view, /from: normalizeQueryValue\(route\.query\.from\)/)
  assert.match(view, /returnTo: route\.query\.return_to/)
  assert.match(view, /if \(annotationReturnPath\.value\) \{\s*router\.push\(annotationReturnPath\.value\)/)
})

test('Annotation keeps the search controls in one scrollable row at narrow widths', () => {
  assert.match(searchPanel, /\.search-scroll \{ overflow-x: auto;/)
  assert.match(searchPanel, /\.search-grid \{[\s\S]*min-width: 1100px;/)
  assert.doesNotMatch(searchPanel, /\.search-grid[\s\S]{0,240}flex-wrap/)
})
