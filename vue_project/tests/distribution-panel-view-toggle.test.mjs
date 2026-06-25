import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(__dirname, '../src/components/DistributionPanel.vue')
const source = fs.readFileSync(sourcePath, 'utf8')

test('DistributionPanel supports chart and list view switching', () => {
  assert.match(source, /const viewMode = ref\('chart'\)/)
  assert.match(source, /setViewMode/)
  assert.match(source, /图表视图/)
  assert.match(source, /列表视图/)
  assert.match(source, /viewMode === 'chart'/)
  assert.match(source, /viewMode === 'list'/)
})

test('DistributionPanel renders list view as a bar chart instead of a plain list', () => {
  assert.match(source, /class="bar-list"/)
  assert.match(source, /class="bar-row"/)
  assert.match(source, /class="bar-track"/)
  assert.match(source, /class="bar-fill"/)
  assert.match(source, /getBarWidth/)
})
