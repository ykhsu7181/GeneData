import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const mapSource = readFileSync(
  join(process.cwd(), 'src', 'components', 'accession', 'AccessionDistributionMap.vue'),
  'utf8'
)
const cardSource = readFileSync(join(process.cwd(), 'src', 'views', 'AccessionCard.vue'), 'utf8')
const serviceSource = readFileSync(join(process.cwd(), 'src', 'services', 'accessionGeography.mjs'), 'utf8')

test('distribution map validates coordinates including zero and boundaries', () => {
  assert.match(mapSource, /buildGeographicMetrics\(props\.items\)/)
  assert.match(serviceSource, /normalizedLongitude >= -180/)
  assert.match(serviceSource, /normalizedLongitude <= 180/)
  assert.match(serviceSource, /normalizedLatitude >= -90/)
  assert.match(serviceSource, /normalizedLatitude <= 90/)
  assert.doesNotMatch(serviceSource, /if \(longitude && latitude\)/)
})

test('distribution map uses 2 degree grid aggregation and last legal boundary buckets', () => {
  assert.match(serviceSource, /GEOGRAPHIC_GRID_SIZE = 2/)
  assert.match(serviceSource, /Math\.ceil\(360 \/ normalizedGridSize\) - 1/)
  assert.match(serviceSource, /Math\.ceil\(180 \/ normalizedGridSize\) - 1/)
  assert.match(mapSource, /aggregateGeographicItems\(props\.items, GEOGRAPHIC_GRID_SIZE\)/)
})

test('overview bubbles and legend use shared count colors', () => {
  assert.match(mapSource, /getGeographicClusterColor\(cluster\.count\)/)
  assert.match(mapSource, /label: \{ show: false \}/)
  assert.doesNotMatch(mapSource, /String\(params\.data\.cluster\.count\)/)
  assert.match(mapSource, /cluster-single/)
  assert.match(mapSource, /cluster-very-large/)
  assert.match(mapSource, /cluster-extreme/)
})

test('distribution map opens an in-map cluster panel before navigating', () => {
  assert.match(mapSource, /<AccessionClusterPanel/)
  assert.match(mapSource, /clusterPanelItems\.value = \[\.\.\.cluster\.accessions\]/)
  assert.match(cardSource, /@select-accession="openAccession"/)
  assert.doesNotMatch(cardSource, /openClusterDrawer|drawerMode\.value = 'cluster'/)
})

test('distribution map keeps accessible counts and cleans up echarts lifecycle', () => {
  assert.match(mapSource, /mappedAccessions/)
  assert.match(mapSource, /totalAccessions/)
  assert.doesNotMatch(mapSource, /mappedOfTotal|regionCount|unmappedCount|class="map-summary"/)
  assert.match(mapSource, /role="img"/)
  assert.match(mapSource, /page\.accessionPortal\.mapAriaLabel/)
  assert.match(mapSource, /echarts\.registerMap\('world', worldMapData\)/)
  assert.match(mapSource, /mapInstance\.on\('click', handleMapClick\)/)
  assert.match(mapSource, /mapInstance\.off\('click', handleMapClick\)/)
  assert.match(mapSource, /window\.removeEventListener\('resize', resizeMap\)/)
  assert.match(mapSource, /mapInstance\.dispose\(\)/)
})

test('distribution overview keeps a compact heading and supports data and global views', () => {
  assert.doesNotMatch(mapSource, /page\.accessionPortal\.mapDescription/)
  assert.match(mapSource, /getTopGeographicRegions\(props\.items\)/)
  assert.match(mapSource, /getGeographicViewport\(props\.items\)/)
  assert.match(mapSource, /center: dataViewport\.value\.center/)
  assert.match(mapSource, /label: \{ show: false \}/)
  assert.match(mapSource, /const resetDataView = \(\) =>/)
  assert.match(mapSource, /const resetGlobalView = \(\) =>/)
  assert.match(mapSource, /center: \[0, 15\], zoom: 1\.05/)
  assert.match(mapSource, /class="full-map-link"/)
})
