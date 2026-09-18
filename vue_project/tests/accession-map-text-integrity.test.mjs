import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const source = readFileSync(resolve('src/views/AccessionMapView.vue'), 'utf8')
const serviceSource = readFileSync(resolve('src/services/accessionGeography.mjs'), 'utf8')
const zhSource = readFileSync(resolve('src/i18n/locales/zh-CN.js'), 'utf8')
const enSource = readFileSync(resolve('src/i18n/locales/en-US.js'), 'utf8')

test('detailed map uses the shared geographic contract and 2 degree clusters', () => {
  assert.match(source, /normalizeGeographicItems\(supplementaryData\.value\)/)
  assert.match(source, /buildGeographicMetrics\(geographicItems\.value\)/)
  assert.match(source, /filterGeographicItems\(geographicItems\.value/)
  assert.match(source, /aggregateGeographicItems\(filteredData\.value, GEOGRAPHIC_GRID_SIZE\)/)
  assert.match(source, /getGeographicViewport\(filteredData\.value\)/)
  assert.match(serviceSource, /GEOGRAPHIC_GRID_SIZE = 2/)
  assert.match(source, /getGeographicClusterColor\(cluster\.count\)/)
  assert.match(source, /label: \{ show: false \}/)
  assert.doesNotMatch(source, /formatter: \(\{ data \}\) => data\.cluster\.count/)
})

test('detailed map filters are shareable through the route query', () => {
  assert.match(source, /parseAccessionMapQuery\(route\.query\)/)
  assert.match(source, /serializeAccessionMapQuery\(/)
  assert.match(source, /router\.replace\(\{ name: 'accession-map', query \}\)/)
  assert.match(source, /const resetFilters = async/)
})

test('detailed map opens a cluster drawer before accession navigation', () => {
  assert.match(source, /<AccessionListDrawer/)
  assert.match(source, /mode="cluster"/)
  assert.match(source, /if \(data\?\.cluster\) openCluster\(data\.cluster\)/)
  assert.match(source, /@change="openClusterByKey"/)
  assert.match(source, /const clusterOptions = computed/)
  assert.match(source, /return_to: returnTo/)
})

test('detailed map provides loading, error, empty, keyboard, and responsive states', () => {
  assert.match(source, /role="status"/)
  assert.match(source, /role="alert"/)
  assert.match(source, /role="img"/)
  assert.match(source, /tabindex="0"/)
  assert.match(source, /aria-live="polite"/)
  assert.match(source, /ResizeObserver/)
  assert.match(source, /clamp\(460px, 62vh, 680px\)/)
  assert.match(source, /@media \(max-width: 640px\)/)
  assert.match(source, /prefers-reduced-motion: reduce/)
  assert.match(source, /animation: !reducedMotion/)
  assert.match(source, /resizeObserver\?\.disconnect\(\)/)
  assert.match(source, /mapInstance\.value\.dispose\(\)/)
})

test('detailed map has complete Chinese and English interaction copy', () => {
  for (const key of [
    'backToOverview',
    'resultSummary',
    'fitDataView',
    'globalView',
    'loadFailed',
    'noResults',
    'clusterTooltip',
    'gridNotice'
  ]) {
    assert.match(zhSource, new RegExp(`${key}:`))
    assert.match(enSource, new RegExp(`${key}:`))
  }
})
