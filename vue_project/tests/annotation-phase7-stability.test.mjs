import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'

const view = readFileSync(resolve(process.cwd(), 'src/views/AnnotationView.vue'), 'utf8')

test('Annotation Phase 7 cancels superseded hierarchy, metadata, table, and chart requests', () => {
  for (const controller of [
    'hierarchyController',
    'optionsController',
    'annotationDataController',
    'visualizationController'
  ]) {
    assert.match(view, new RegExp(`let ${controller} = null`))
  }
  assert.match(view, /currentController\?\.abort\(\)/)
  assert.ok((view.match(/signal: controller\.signal/g) || []).length >= 5)
  assert.match(view, /isCanceledRequest\(error\)/)
})

test('Annotation Phase 7 prevents stale route work from replacing current URL state', () => {
  assert.match(view, /let routeRequestToken = 0/)
  assert.match(view, /const syncRouteContext = async \(requestToken\)/)
  assert.match(view, /requestToken !== routeRequestToken/)
  assert.match(view, /const requestToken = routeRequestToken \+ 1/)
})

test('Annotation Phase 7 releases requests, timers, SVG content, and tooltip nodes on unmount', () => {
  assert.match(view, /onBeforeUnmount\(\(\) => \{/)
  assert.match(view, /componentDisposed = true/)
  assert.match(view, /organismsController\?\.abort\(\)/)
  assert.match(view, /visualizationController\?\.abort\(\)/)
  assert.match(view, /stopChange\(\)/)
  assert.match(view, /d3\.selectAll\('\.annotation-tooltip'\)\.remove\(\)/)
  assert.match(view, /d3\.select\(annotationContainer\.value\)\.selectAll\('\*'\)\.remove\(\)/)
})

test('Annotation Phase 7 clears pending loading states when context or view is cleared', () => {
  assert.match(view, /annotationDataController\?\.abort\(\);[\s\S]*loadingAnnotation\.value = false/)
  assert.match(view, /visualizationController\?\.abort\(\);[\s\S]*loadingVisualization\.value = false/)
  assert.match(view, /const handleViewModeChange = async[\s\S]*visualizationController\?\.abort\(\)/)
})

test('Annotation Phase 7 removes visualization debug logging from production code', () => {
  assert.doesNotMatch(view, /console\.log\(/)
})
