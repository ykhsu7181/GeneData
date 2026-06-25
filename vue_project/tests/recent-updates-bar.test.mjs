import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(__dirname, '../src/components/RecentUpdatesBar.vue')

test('RecentUpdatesBar renders latest updates with a safe empty state', () => {
  assert.ok(fs.existsSync(sourcePath), 'RecentUpdatesBar.vue should exist')
  const source = fs.readFileSync(sourcePath, 'utf8')

  for (const expectedText of [
    '最近更新',
    '暂无最近更新',
    "emit('navigate'",
    'update-chip',
    '查看全部更新'
  ]) {
    assert.ok(source.includes(expectedText), `Expected RecentUpdatesBar.vue to include ${expectedText}`)
  }
})
