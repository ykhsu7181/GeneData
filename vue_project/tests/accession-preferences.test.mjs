import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const source = readFileSync(
  join(process.cwd(), 'src', 'services', 'accessionPreferences.js'),
  'utf8'
)
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`

class MemoryStorage {
  constructor(initial = {}) {
    this.values = new Map(Object.entries(initial))
  }

  getItem(key) {
    return this.values.has(key) ? this.values.get(key) : null
  }

  setItem(key, value) {
    this.values.set(key, String(value))
  }
}

const loadService = async (storage) => {
  globalThis.localStorage = storage
  return import(`${moduleUrl}#${Math.random()}`)
}

test('migrates legacy recent accessions, removes invalid duplicates, and preserves order', async () => {
  const storage = new MemoryStorage({
    recent_accessions: JSON.stringify([' 02428 ', '', 'IR64', '02428', null, 42])
  })
  const service = await loadService(storage)

  assert.deepEqual(service.getRecentAccessions(), [
    { accession: '02428', viewed_at: null },
    { accession: 'IR64', viewed_at: null }
  ])
  assert.deepEqual(JSON.parse(storage.getItem('recent_accessions_v2')), [
    { accession: '02428', viewed_at: null },
    { accession: 'IR64', viewed_at: null }
  ])
})

test('records recent accessions once, moves revisits first, and caps the list at 20', async () => {
  const storage = new MemoryStorage()
  const service = await loadService(storage)

  for (let index = 0; index < 22; index += 1) {
    assert.equal(service.recordRecentAccession(`ACC${index}`).persisted, true)
  }
  const revisit = service.recordRecentAccession('ACC10')

  assert.equal(revisit.items.length, 20)
  assert.equal(revisit.items[0].accession, 'ACC10')
  assert.equal(revisit.items.filter((item) => item.accession === 'ACC10').length, 1)
  assert.match(revisit.items[0].viewed_at, /^\d{4}-\d{2}-\d{2}T/)
})

test('toggles favorites without duplicates and keeps UTC timestamps', async () => {
  const storage = new MemoryStorage()
  const service = await loadService(storage)

  const added = service.toggleFavoriteAccession(' IR64 ')
  assert.equal(added.persisted, true)
  assert.equal(added.isFavorite, true)
  assert.match(added.items[0].created_at, /Z$/)
  assert.equal(service.isFavoriteAccession('IR64'), true)

  const removed = service.toggleFavoriteAccession('IR64')
  assert.equal(removed.isFavorite, false)
  assert.deepEqual(removed.items, [])
})

test('handles malformed data and unavailable storage without throwing', async () => {
  const malformed = await loadService(new MemoryStorage({
    recent_accessions_v2: '{broken',
    favorite_accessions_v1: JSON.stringify({ accession: 'IR64' })
  }))
  assert.deepEqual(malformed.getRecentAccessions(), [])
  assert.deepEqual(malformed.getFavoriteAccessions(), [])

  const failingStorage = {
    getItem() { throw new DOMException('blocked', 'SecurityError') },
    setItem() { throw new DOMException('blocked', 'SecurityError') }
  }
  const unavailable = await loadService(failingStorage)
  assert.deepEqual(unavailable.getRecentAccessions(), [])
  assert.equal(unavailable.recordRecentAccession('IR64').persisted, false)
  assert.equal(unavailable.toggleFavoriteAccession('IR64').persisted, false)
})

test('detail page records successful summaries and exposes an accessible favorite control', () => {
  const detailSource = readFileSync(
    join(process.cwd(), 'src', 'views', 'AccessionDetailTableView.vue'),
    'utf8'
  )

  assert.match(detailSource, /if \(!response\.data\?\.success\) throw/)
  assert.match(detailSource, /recordRecentAccession\(loadedAccession\)/)
  assert.match(detailSource, /recordedRouteAccession\.value !== requestedAccession/)
  assert.match(detailSource, /:aria-pressed="favorite"/)
  assert.match(detailSource, /toggleFavoriteAccession\(currentAccession\)/)
})
