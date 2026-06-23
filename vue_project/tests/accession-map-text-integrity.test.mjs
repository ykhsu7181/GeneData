import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const accessionMapViewPath = resolve('src/views/AccessionMapView.vue')
const accessionMapViewSource = readFileSync(accessionMapViewPath, 'utf8')

test('AccessionMapView source does not contain known mojibake markers', () => {
  const mojibakeMarkers = [
    '鏈煡',
    '鑾峰彇',
    '鍦板浘',
    '鏁版嵁',
    '绛涢€',
    '馃'
  ]

  for (const marker of mojibakeMarkers) {
    assert.equal(
      accessionMapViewSource.includes(marker),
      false,
      `Unexpected mojibake marker found: ${marker}`
    )
  }
})

test('AccessionMapView keeps key Chinese literals readable', () => {
  assert.match(accessionMapViewSource, /未知亚群/)
  assert.match(accessionMapViewSource, /获取亚群列表失败/)
  assert.match(accessionMapViewSource, /地图初始化失败/)
})
