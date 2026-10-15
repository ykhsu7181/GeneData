import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import test from 'node:test'

const source = readFileSync(
  join(process.cwd(), 'src', 'services', 'assemblyPreferences.js'),
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

test('normalizes recent assemblies, removes invalid duplicates, and preserves order', async () => {
  const storage = new MemoryStorage({
    genedata_recent_assemblies_v1: JSON.stringify([
      { id: 2, accession: ' 02428 ', assembly: ' default ', viewed_at: '2026-09-17T06:00:00Z' },
      { id: 0, accession: 'bad', assembly: 'bad' },
      { id: 1, accession: 'IR64', assembly: 'v2-polish', viewed_at: 'broken' },
      { id: 2, accession: 'duplicate', assembly: 'duplicate' },
      null
    ])
  })
  const service = await loadService(storage)

  assert.deepEqual(service.getRecentAssemblies(), [
    {
      id: 2,
      accession: '02428',
      assembly: 'default',
      assembly_accession: '',
      species: '',
      viewed_at: '2026-09-17T06:00:00.000Z'
    },
    {
      id: 1,
      accession: 'IR64',
      assembly: 'v2-polish',
      assembly_accession: '',
      species: '',
      viewed_at: null
    }
  ])
})

test('records assemblies once, moves revisits first, and caps the list at 10', async () => {
  const storage = new MemoryStorage()
  const service = await loadService(storage)

  for (let index = 1; index <= 12; index += 1) {
    assert.equal(service.recordRecentAssembly({
      id: index,
      accession: `ACC${index}`,
      assembly: `asm-${index}`,
      assembly_accession: `GCA_${index}`,
      species: 'Oryza sativa'
    }).persisted, true)
  }
  const revisit = service.recordRecentAssembly({ id: 4, accession: 'ACC4', assembly: 'asm-4' })

  assert.equal(revisit.items.length, 10)
  assert.equal(revisit.items[0].id, 4)
  assert.equal(revisit.items.filter((item) => item.id === 4).length, 1)
  assert.match(revisit.items[0].viewed_at, /Z$/)
})

test('removes and clears recent assemblies with recoverable write results', async () => {
  const storage = new MemoryStorage()
  const service = await loadService(storage)

  service.recordRecentAssembly({ id: 1, accession: 'IR64', assembly: 'v2-polish' })
  service.recordRecentAssembly({ id: 2, accession: '02428', assembly: 'default' })

  const removed = service.removeRecentAssembly(1)
  assert.equal(removed.persisted, true)
  assert.deepEqual(removed.items.map((item) => item.id), [2])

  const cleared = service.clearRecentAssemblies()
  assert.equal(cleared.persisted, true)
  assert.deepEqual(cleared.items, [])
})

test('handles malformed data and unavailable storage without throwing', async () => {
  const malformed = await loadService(new MemoryStorage({
    genedata_recent_assemblies_v1: '{broken'
  }))
  assert.deepEqual(malformed.getRecentAssemblies(), [])

  const failingStorage = {
    getItem() { throw new DOMException('blocked', 'SecurityError') },
    setItem() { throw new DOMException('blocked', 'SecurityError') }
  }
  const unavailable = await loadService(failingStorage)
  assert.deepEqual(unavailable.getRecentAssemblies(), [])
  assert.equal(unavailable.recordRecentAssembly({ id: 1, accession: 'IR64' }).persisted, false)
  assert.equal(unavailable.removeRecentAssembly(1).persisted, false)
  assert.equal(unavailable.clearRecentAssemblies().persisted, false)
})
