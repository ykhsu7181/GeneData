import assert from 'node:assert/strict'
import test from 'node:test'

import {
  aggregateGeographicItems,
  buildGeographicMetrics,
  filterGeographicItems,
  getGeographicClusterColor,
  getGeographicViewport,
  getTopGeographicRegions,
  isValidCoordinate,
  normalizeGeographicItems,
  normalizeSubPopulation
} from '../src/services/accessionGeography.mjs'

const records = {
  IR64: { longitude: 120, latitude: 30, sub_population: 'XI', country: 'China' },
  ZERO: { longitude: 0, latitude: 0, sub_population: '', country: 'Ghana' },
  EDGE: { longitude: 180, latitude: 90, sub_population: '未知亚群', region: 'Boundary' },
  INVALID: { longitude: 181, latitude: 20, sub_population: 'GJ', country: 'China' },
  EMPTY: { longitude: '', latitude: '', sub_population: '-', country: 'China' }
}

test('shared geography contract accepts zero and legal boundaries but rejects missing and out-of-range coordinates', () => {
  assert.equal(isValidCoordinate(0, 0), true)
  assert.equal(isValidCoordinate(-180, -90), true)
  assert.equal(isValidCoordinate(180, 90), true)
  assert.equal(isValidCoordinate('', ''), false)
  assert.equal(isValidCoordinate(181, 0), false)
  assert.equal(isValidCoordinate(0, -91), false)
})

test('cluster colors follow the shared accession-count thresholds', () => {
  assert.equal(getGeographicClusterColor(1), '#1677e8')
  assert.equal(getGeographicClusterColor(2), '#16a34a')
  assert.equal(getGeographicClusterColor(5), '#16a34a')
  assert.equal(getGeographicClusterColor(6), '#7c3aed')
  assert.equal(getGeographicClusterColor(10), '#7c3aed')
  assert.equal(getGeographicClusterColor(11), '#f07818')
  assert.equal(getGeographicClusterColor(19), '#f07818')
  assert.equal(getGeographicClusterColor(20), '#eab308')
  assert.equal(getGeographicClusterColor(50), '#eab308')
  assert.equal(getGeographicClusterColor(100), '#eab308')
  assert.equal(getGeographicClusterColor(101), '#ec4899')
})

test('shared geography normalization keeps unique accessions and one unknown sub-population label', () => {
  const normalized = normalizeGeographicItems(records)
  assert.equal(normalized.length, 5)
  assert.equal(normalizeSubPopulation('未知亚群'), 'Unknown')
  assert.equal(normalizeSubPopulation('-'), 'Unknown')
  assert.equal(normalized.find((item) => item.accession === 'ZERO').longitude, 0)
})

test('shared geography metrics use total, valid, unmapped, grid, and sub-population definitions consistently', () => {
  const metrics = buildGeographicMetrics(records)
  assert.deepEqual(metrics, {
    totalAccessions: 5,
    mappedAccessions: 3,
    unmappedAccessions: 2,
    geographicRegions: 3,
    subPopulationCount: 2
  })
})

test('shared 2 degree aggregation clamps final longitude and latitude buckets', () => {
  const clusters = aggregateGeographicItems(records)
  assert.equal(clusters.length, 3)
  assert.ok(clusters.some((cluster) => cluster.key === '179:89'))
})

test('shared filtering applies accession, sub-population, and region to valid records only', () => {
  assert.deepEqual(filterGeographicItems(records, { accession: 'IR64' }).map((item) => item.accession), ['IR64'])
  assert.deepEqual(filterGeographicItems(records, { subPopulations: ['Unknown'] }).map((item) => item.accession), ['ZERO', 'EDGE'])
  assert.deepEqual(filterGeographicItems(records, { subPopulations: [] }), [])
  assert.deepEqual(filterGeographicItems(records, { region: 'china', subPopulations: ['XI', 'GJ'] }).map((item) => item.accession), ['IR64'])
})

test('overview helpers derive a bounded data viewport and ranked named regions', () => {
  const viewport = getGeographicViewport(records)
  assert.equal(viewport.center.length, 2)
  assert.ok(viewport.zoom >= 1.05 && viewport.zoom <= 5)
  assert.deepEqual(getTopGeographicRegions(records, 2), [
    { name: 'Boundary', count: 1 },
    { name: 'China', count: 1 }
  ])
  assert.deepEqual(getGeographicViewport([]), { center: [0, 15], zoom: 1.05 })
})
