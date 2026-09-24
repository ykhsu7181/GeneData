import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const readSource = (relativePath) => readFileSync(join(process.cwd(), 'src', ...relativePath), 'utf8')
const cardSource = readSource(['views', 'AccessionCard.vue'])
const recentSource = readSource(['components', 'accession', 'RecentAccessions.vue'])
const favoriteSource = readSource(['components', 'accession', 'FavoriteAccessions.vue'])
const drawerSource = readSource(['components', 'accession', 'AccessionListDrawer.vue'])

test('accession portal composes recent favorites and one shared drawer', () => {
  assert.match(cardSource, /<RecentAccessions/)
  assert.match(cardSource, /<FavoriteAccessions/)
  assert.match(cardSource, /<AccessionListDrawer/)
  assert.match(cardSource, /openDrawer\('recent', \$event\)/)
  assert.match(cardSource, /openDrawer\('favorites', \$event\)/)
  assert.match(cardSource, /drawerMode\.value === 'favorites'/)
})

test('portal hydrates preferences with one supplementary metadata request', () => {
  assert.match(cardSource, /getRecentAccessions\(\)/)
  assert.match(cardSource, /getFavoriteAccessions\(\)/)
  assert.match(cardSource, /\/files\/query\/supplementary-data\//)
  assert.match(cardSource, /metadata\.value\[item\.accession\]/)
  assert.match(cardSource, /new AbortController\(\)/)
  assert.doesNotMatch(cardSource, /\/files\/accessions\/\$\{item\.accession\}/)
})

test('recent and favorites preserve accessions when metadata is missing', () => {
  assert.match(recentSource, /item\.scientific_name \|\| '—'/)
  assert.match(favoriteSource, /item\.scientific_name \|\| '—'/)
  assert.match(recentSource, /items\.slice\(0, 5\)/)
  assert.match(favoriteSource, /max-height:190px/)
  assert.match(favoriteSource, /overflow-y:auto/)
  assert.match(recentSource, /import \{ Clock \} from '@element-plus\/icons-vue'/)
  assert.match(favoriteSource, /import \{ StarFilled \} from '@element-plus\/icons-vue'/)
  assert.match(drawerSource, /import \{ Delete \} from '@element-plus\/icons-vue'/)
})

test('shared drawer supports recent and favorite modes with focus restoration', () => {
  assert.match(drawerSource, /recent:/)
  assert.match(drawerSource, /favorites:/)
  assert.match(drawerSource, /@closed="\$emit\('closed'\)"/)
  assert.match(cardSource, /drawerTrigger\?\.focus\?\.\(\)/)
  assert.match(drawerSource, /mode === 'recent'/)
  assert.match(drawerSource, /@click="\$emit\('clear'\)"/)
})

test('preference removal keeps failed writes visible to the user', () => {
  assert.match(cardSource, /removeFavoriteAccession\(accession\)/)
  assert.match(cardSource, /removeRecentAccession\(accession\)/)
  assert.match(cardSource, /clearRecentAccessions\(\)/)
  assert.match(cardSource, /if \(!result\.persisted\) showStorageError\(\)/)
})
