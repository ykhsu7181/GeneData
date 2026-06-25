import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(__dirname, '../src/components/GeoMapPanel.vue')
const source = fs.readFileSync(sourcePath, 'utf8')

test('GeoMapPanel removes the right-side point summary list', () => {
  for (const removedText of [
    'geo-side-panel',
    'geo-summary-card',
    'geo-list-head',
    'geo-point-list',
    'legend-card',
    'totalPointCount',
    'topPoints'
  ]) {
    assert.ok(
      !source.includes(removedText),
      `Expected GeoMapPanel.vue to remove ${removedText}`
    )
  }
})

test('GeoMapPanel keeps the dashboard map compact and fills the map shell', () => {
  assert.ok(
    source.includes('--geo-map-height: 460px'),
    'Expected dashboard map to be tall enough to fill the left shell'
  )
  assert.ok(
    source.includes('grid-template-columns: minmax(0, 1fr);'),
    'Expected the map layout to use the full card width after removing the side panel'
  )
  assert.ok(
    source.includes("layoutCenter: ['48%', '54%']"),
    'Expected ECharts geo layout to be centered inside the shell'
  )
  assert.ok(
    source.includes("layoutSize: '126%'"),
    'Expected ECharts geo layout to fill the shell'
  )
})

test('GeoMapPanel tooltip exposes accession names, species names, and coordinates', () => {
  for (const expectedText of ['Accession:', '物种名:', '经纬度:']) {
    assert.ok(
      source.includes(expectedText),
      `Expected tooltip to include ${expectedText}`
    )
  }
})
