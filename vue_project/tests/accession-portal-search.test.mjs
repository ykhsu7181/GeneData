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

test('accession portal header uses the shared navigation and translated portal copy', () => {
  assert.match(headerSource, /<router-link to="\/">/)
  assert.match(headerSource, /page\.accessionPortal\.title/)
  assert.match(headerSource, /page\.accessionPortal\.subtitle/)
  assert.doesNotMatch(headerSource, /TopNavBar/)
})

test('portal search enforces the approved request contract', () => {
  assert.match(searchSource, /const DEBOUNCE_MS = 275/)
  assert.match(searchSource, /const MIN_SEARCH_LENGTH = 2/)
  assert.match(searchSource, /params: \{ search: keyword, limit: 20 \}/)
  assert.match(searchSource, /new AbortController\(\)/)
  assert.match(searchSource, /sequence !== requestSequence/)
  assert.match(searchSource, /onBeforeUnmount/)
  assert.doesNotMatch(searchSource, /query\/organisms\/\?search=/)
})

test('portal search distinguishes accession and query examples', () => {
  assert.match(searchSource, /label: '02428', value: '02428', type: 'accession'/)
  assert.match(searchSource, /label: 'Oryza sativa', value: 'Oryza sativa', type: 'query'/)
  assert.match(searchSource, /if \(example\.type === 'accession'\)/)
  assert.match(searchSource, /await fetchSuggestions\(example\.value\)/)
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
