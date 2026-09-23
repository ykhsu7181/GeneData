import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import test from 'node:test'
import {
  ACCESSION_VIEW_COOLDOWN_MS,
  shouldRecordAccessionView
} from '../src/services/accessionViews.js'

const memoryStorage = (initial = {}) => {
  const values = new Map(Object.entries(initial))
  return {
    getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, value)
  }
}

test('accession view cooldown suppresses refreshes but expires after thirty minutes', () => {
  const now = 1_000_000
  const storage = memoryStorage({
    'genedata:accession-view-cooldowns:v1': JSON.stringify({ IR64: now })
  })

  assert.equal(shouldRecordAccessionView('IR64', now + ACCESSION_VIEW_COOLDOWN_MS - 1, storage), false)
  assert.equal(shouldRecordAccessionView('IR64', now + ACCESSION_VIEW_COOLDOWN_MS, storage), true)
  assert.equal(shouldRecordAccessionView('B73', now, storage), true)
  assert.equal(shouldRecordAccessionView('', now, storage), false)
})

test('accession detail records popularity only after its summary succeeds', () => {
  const source = readFileSync(resolve('src/views/AccessionDetailTableView.vue'), 'utf8')
  const summaryAssignment = source.indexOf('summaryData.value = response.data.data || {}')
  const viewCall = source.indexOf('recordAccessionView(loadedAccession)')
  assert.ok(summaryAssignment >= 0)
  assert.ok(viewCall > summaryAssignment)
  assert.match(source, /recordAccessionView\(loadedAccession\)\.catch/)
})
