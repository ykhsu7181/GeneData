import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const readSource = (relativePath) => readFileSync(join(process.cwd(), 'src', ...relativePath), 'utf8')
const portalSource = readSource(['views', 'AssemblyPortalView.vue'])
const drawerSource = readSource(['components', 'assembly', 'AssemblyRecentDrawer.vue'])

test('Assembly portal final accessibility names search, list state, actions, and empty recovery', () => {
  assert.match(portalSource, /role="search"/)
  assert.match(portalSource, /:aria-busy="String\(loading\)"/)
  assert.match(portalSource, /aria-live="polite"/)
  assert.doesNotMatch(portalSource, /page\.assembly\.searchExample|class="examples"/)
  assert.match(portalSource, /:aria-label="\$t\('page\.assembly\.openAssembly'/)
  assert.match(portalSource, /:aria-label="\$t\('page\.assembly\.openAccession'/)
  assert.match(portalSource, /<template #empty>/)
  assert.match(portalSource, /role="status"/)
  assert.match(portalSource, /page\.assembly\.clearSearch/)
  assert.match(portalSource, /aria-haspopup="dialog"/)
  assert.match(portalSource, /page\.assembly\.chooseColumns/)
  assert.match(portalSource, /role="group"/)
})

test('Assembly recent drawer final accessibility supports named drawer actions and focus restoration', () => {
  assert.match(portalSource, /drawerTrigger\?\.focus\?\.\(\)/)
  assert.match(drawerSource, /:aria-label="\$t\('page\.assembly\.viewAllRecent'\)"/)
  assert.match(drawerSource, /role="list"/)
  assert.match(drawerSource, /role="listitem"/)
  assert.match(drawerSource, /page\.assembly\.removeRecent/)
  assert.match(drawerSource, /:aria-label="\$t\('page\.assembly\.clearAll'\)"/)
})
