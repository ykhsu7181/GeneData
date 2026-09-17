import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const readSource = (relativePath) => readFileSync(join(process.cwd(), 'src', ...relativePath), 'utf8')
const drawerSource = readSource(['components', 'accession', 'AccessionListDrawer.vue'])
const mapSource = readSource(['components', 'accession', 'AccessionDistributionMap.vue'])
const cardSource = readSource(['views', 'AccessionCard.vue'])

test('final portal accessibility keeps map and drawer states named', () => {
  assert.match(mapSource, /role="img"/)
  assert.match(mapSource, /mapAriaLabel/)
  assert.match(mapSource, /aria-live="polite"/)
  assert.match(drawerSource, /noClusterAccessions/)
  assert.match(drawerSource, /:aria-label="\$t\('page\.accessionPortal\.removeItem'/)
})

test('final portal cleanup keeps focus and cancels metadata requests', () => {
  assert.match(cardSource, /drawerTrigger\?\.focus\?\.\(\)/)
  assert.match(cardSource, /metadataController\?\.abort\(\)/)
  assert.match(cardSource, /onBeforeUnmount/)
  assert.match(mapSource, /window\.removeEventListener\('resize', resizeMap\)/)
  assert.match(mapSource, /mapInstance\.dispose\(\)/)
})
