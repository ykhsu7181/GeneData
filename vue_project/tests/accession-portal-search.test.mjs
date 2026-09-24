import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const searchSource = readFileSync(
  join(process.cwd(), 'src', 'components', 'accession', 'AccessionSearchPanel.vue'),
  'utf8'
)
const headerSource = readFileSync(
  join(process.cwd(), 'src', 'components', 'accession', 'AccessionPortalHeader.vue'),
  'utf8'
)

test('accession portal header keeps only shared navigation and the translated title', () => {
  assert.match(headerSource, /<router-link to="\/">/)
  assert.match(headerSource, /page\.accessionPortal\.title/)
  assert.doesNotMatch(headerSource, /page\.accessionPortal\.subtitle|<p>/)
  assert.doesNotMatch(headerSource, /TopNavBar/)
})

test('portal search enforces the approved request contract', () => {
  assert.doesNotMatch(searchSource, /<h2[^>]*>\{\{ \$t\('page\.accessionPortal\.searchTitle'\) \}\}<\/h2>/)
  assert.match(searchSource, /<section class="search-panel" :aria-label="\$t\('page\.accessionPortal\.searchTitle'\)">/)
  assert.match(searchSource, /const DEBOUNCE_MS = 275/)
  assert.match(searchSource, /const MIN_SEARCH_LENGTH = 2/)
  assert.match(searchSource, /params: \{ search: keyword, limit: 20 \}/)
  assert.match(searchSource, /new AbortController\(\)/)
  assert.match(searchSource, /sequence !== requestSequence/)
  assert.match(searchSource, /onBeforeUnmount/)
  assert.doesNotMatch(searchSource, /query\/organisms\/\?search=/)
})

test('portal search does not render search examples', () => {
  assert.doesNotMatch(searchSource, /class="examples"|const examples|useExample/)
})

test('portal suggestions expose combobox and keyboard semantics', () => {
  assert.match(searchSource, /role="combobox"/)
  assert.match(searchSource, /role="listbox"/)
  assert.match(searchSource, /role="option"/)
  assert.match(searchSource, /event\.key === 'ArrowDown'/)
  assert.match(searchSource, /event\.key === 'ArrowUp'/)
  assert.match(searchSource, /event\.key === 'Escape'/)
  assert.match(searchSource, /event\.key === 'Enter'/)
})
