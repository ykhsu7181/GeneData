import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(__dirname, '../src/components/DataResourceSummary.vue')

test('DataResourceSummary renders resource cards that emit navigation targets', () => {
  assert.ok(fs.existsSync(sourcePath), 'DataResourceSummary.vue should exist')
  const source = fs.readFileSync(sourcePath, 'utf8')

  for (const expectedText of [
    '数据资源统计',
    'Data Resource Summary',
    "emit('navigate'",
    'resource-card',
    'resource.status ===',
    '建设中'
  ]) {
    assert.ok(source.includes(expectedText), `Expected DataResourceSummary.vue to include ${expectedText}`)
  }
})
