import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const mapSource = readFileSync(
  join(process.cwd(), 'src', 'components', 'accession', 'AccessionDistributionMap.vue'),
  'utf8'
)
const cardSource = readFileSync(join(process.cwd(), 'src', 'views', 'AccessionCard.vue'), 'utf8')

test('distribution map validates coordinates including zero and boundaries', () => {
  assert.match(mapSource, /longitude !== null/)
  assert.match(mapSource, /latitude !== null/)
  assert.match(mapSource, /Number\.isFinite\(longitude\)/)
  assert.match(mapSource, /longitude >= -180/)
  assert.match(mapSource, /longitude <= 180/)
  assert.match(mapSource, /latitude >= -90/)
  assert.match(mapSource, /latitude <= 90/)
  assert.doesNotMatch(mapSource, /if \(longitude && latitude\)/)
})

test('distribution map uses 2 degree grid aggregation and last legal boundary buckets', () => {
  assert.match(mapSource, /const GRID_SIZE = 2/)
  assert.match(mapSource, /Math\.ceil\(360 \/ GRID_SIZE\) - 1/)
  assert.match(mapSource, /Math\.ceil\(180 \/ GRID_SIZE\) - 1/)
  assert.match(mapSource, /Math\.min\(maxGridX, Math\.floor\(\(item\.longitude \+ 180\) \/ GRID_SIZE\)\)/)
  assert.match(mapSource, /Math\.min\(maxGridY, Math\.floor\(\(item\.latitude \+ 90\) \/ GRID_SIZE\)\)/)
  assert.match(mapSource, /accessions\.reduce\(\(sum, item\) => sum \+ item\.longitude/)
})

test('distribution map routes single points and opens cluster drawer for groups', () => {
  assert.match(mapSource, /if \(cluster\.count === 1\)/)
  assert.match(mapSource, /emit\('select', cluster\.accessions\[0\]\.accession\)/)
  assert.match(mapSource, /emit\('select-cluster', cluster\.accessions\)/)
  assert.match(cardSource, /@select-cluster="openClusterDrawer"/)
  assert.match(cardSource, /drawerMode\.value = 'cluster'/)
})

test('distribution map reports mapped accessions and cleans up echarts lifecycle', () => {
  assert.match(mapSource, /mappedAccessions/)
  assert.match(mapSource, /totalAccessions/)
  assert.match(mapSource, /mappedOfTotal/)
  assert.match(mapSource, /role="img"/)
  assert.match(mapSource, /page\.accessionPortal\.mapAriaLabel/)
  assert.match(mapSource, /aria-live="polite"/)
  assert.match(mapSource, /echarts\.registerMap\('world', worldMapData\)/)
  assert.match(mapSource, /mapInstance\.on\('click', handleMapClick\)/)
  assert.match(mapSource, /mapInstance\.off\('click', handleMapClick\)/)
  assert.match(mapSource, /window\.removeEventListener\('resize', resizeMap\)/)
  assert.match(mapSource, /mapInstance\.dispose\(\)/)
})
