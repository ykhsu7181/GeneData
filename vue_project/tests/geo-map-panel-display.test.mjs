import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const sourcePath = path.resolve(__dirname, '../src/components/GeoMapPanel.vue')
const source = fs.readFileSync(sourcePath, 'utf8')

test('GeoMapPanel side list identifies unknown locations by accession, species, and coordinates', () => {
  for (const expectedText of [
    '点位',
    '未标注地区',
    'Accession',
    '物种',
    '经纬度',
    'legend-title-row',
    'legend-detail-grid',
    'buildPointListText(point.accession_names',
    'buildPointListText(point.species_names'
  ]) {
    assert.ok(
      source.includes(expectedText),
      `Expected GeoMapPanel.vue to include ${expectedText}`
    )
  }
})

test('GeoMapPanel keeps the dashboard map compact and fills the map shell', () => {
  assert.ok(
    source.includes('--geo-map-height: 460px'),
    'Expected dashboard map to be tall enough to fill the left shell'
  )
  assert.ok(
    source.includes('--geo-column-height: 486px'),
    'Expected left and right columns to share a fixed visual height'
  )
  assert.ok(
    source.includes('align-items: start'),
    'Expected grid columns not to stretch the map shell taller than the map'
  )
  assert.ok(
    source.includes("layoutCenter: ['48%', '54%']"),
    'Expected ECharts geo layout to be centered inside the shell'
  )
  assert.ok(
    source.includes("layoutSize: '126%'"),
    'Expected ECharts geo layout to fill the shell'
  )
  assert.ok(
    source.includes('geo-point-list'),
    'Expected point cards to scroll inside the right column instead of stretching the panel'
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
