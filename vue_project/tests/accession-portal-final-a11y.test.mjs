import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const readSource = (relativePath) => readFileSync(join(process.cwd(), 'src', ...relativePath), 'utf8')
const drawerSource = readSource(['components', 'accession', 'AccessionListDrawer.vue'])
const clusterPanelSource = readSource(['components', 'accession', 'AccessionClusterPanel.vue'])
const mapSource = readSource(['components', 'accession', 'AccessionDistributionMap.vue'])
const cardSource = readSource(['views', 'AccessionCard.vue'])
const detailSource = readSource(['views', 'AccessionDetailTableView.vue'])

test('final portal accessibility keeps map and drawer states named', () => {
  assert.match(mapSource, /role="img"/)
  assert.match(mapSource, /mapAriaLabel/)
  assert.doesNotMatch(mapSource, /class="map-summary"/)
  assert.match(clusterPanelSource, /role="dialog"/)
  assert.match(clusterPanelSource, /common\.close/)
  assert.match(drawerSource, /:aria-label="\$t\('page\.accessionPortal\.removeItem'/)
})

test('final portal cleanup keeps focus and cancels metadata requests', () => {
  assert.match(cardSource, /drawerTrigger\?\.focus\?\.\(\)/)
  assert.match(cardSource, /metadataController\?\.abort\(\)/)
  assert.match(cardSource, /onBeforeUnmount/)
  assert.match(mapSource, /window\.removeEventListener\('resize', resizeMap\)/)
  assert.match(mapSource, /mapInstance\.dispose\(\)/)
})

test('accession detail exposes contextual return and accessible async states', () => {
  assert.doesNotMatch(detailSource, /class="context-back"|parentReturnLabel/)
  assert.match(detailSource, /role="status" aria-live="polite"/)
  assert.match(detailSource, /role="alert"/)
  assert.match(detailSource, /:aria-current="activeTab === tab\.key \? 'page' : undefined"/)
  assert.match(detailSource, /:aria-label="\$t\('page\.accessionDetail\.searchPlaceholder'\)"/)
  assert.match(detailSource, /<StarFilled v-if="favorite"/)
})
